"""Validate official sources and build an immutable, API-free planning release."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.acquire_planning import now

VERSION = 'planning-1.2.0'
CONTRACT_PATH = Path(__file__).with_name('planning_contracts.json')
CONTRACTS = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))['sources']
STATUS_SOURCE = 'https://www.toronto.ca/wp-content/uploads/2025/06/964b-CityPlanning-Development-Pipeline-2024.pdf#page=2'
PROJECT_STAGES = {
    'Under Review': 'Awaiting a planning decision, or under appeal. Approval is not established by this category.',
    'Active': 'Includes planning approvals, permit applications and issued permits. This category does not independently confirm construction.',
    'Built': 'Recorded as ready for occupancy and/or completed within the reporting period; it does not necessarily mean all work is complete.',
}
TO_METRES = Transformer.from_crs(4326, 26917, always_xy=True)
TO_DISPLAY = Transformer.from_crs(26917, 4326, always_xy=True)
TILE = 2000
REQUIRED = {
    'projects': {'_id', 'Application Number', 'Pipeline Status', 'Address', 'Description'},
    'applications': {'_id', 'APPLICATION#', 'STATUS', 'STREET_NUM', 'STREET_NAME', 'STREET_TYPE', 'STREET_DIRECTION', 'DESCRIPTION'},
    'addresses': {'_id', 'ADDRESS_POINT_ID', 'ADDRESS_FULL', 'LINEAR_NAME_FULL'},
    'zoning': {'_id', 'ZN_STRING'}, 'heights': {'_id', 'HT_STRING'},
    'neighbourhoods': {'_id', 'AREA_NAME'}, 'streets': {'_id'},
}


def write_json(path: Path, value: Any) -> None:
    """Write strict compact UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')


def publish_latest(output: Path, snapshot_id: str) -> None:
    """Swap the pointer only after complete JSON is flushed beside its destination."""
    value = {'id': snapshot_id, 'checked_at': now(), 'status': 'ok'}
    payload = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    output.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='.latest-', suffix='.tmp',
                                         dir=output, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory replacement is atomic: readers see either complete pointer.
        os.replace(temporary, output / 'latest.json')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def normalize(value: str) -> str:
    """Normalize whitespace and case only; never fuzzy-match addresses."""
    return ' '.join(value.upper().split())


def sha(path: Path) -> str:
    """Hash bytes without loading large inputs into memory."""
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def value_category(value: Any) -> str:
    """Classify JSON values without conflating booleans with numbers."""
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, str):
        return 'string'
    return type(value).__name__


def validate_schema(rows: list[dict], key: str, contract: dict) -> None:
    """Freeze every qualified field and value category; null remains explicit missing data."""
    fields = contract['fields']
    if not rows:
        raise ValueError(f'Schema drift: {key}: empty source')
    for index, row in enumerate(rows):
        if set(row) != set(fields):
            raise ValueError(f'Schema drift: {key} row {index}: supplied fields changed')
        for field, value in row.items():
            if value is not None and value_category(value) not in fields[field]:
                raise ValueError(f'Schema drift: {key} row {index} field {field}: unexpected type')
        if not str(row.get('_id', '')).isdigit():
            raise ValueError(f'Invalid source row ID: {key} row {index}')


def normalized_status(kind: str, raw: str) -> dict:
    """Preserve exact publisher wording while interpreting only documented project categories."""
    status = raw.strip()
    if kind == 'projects' and status in PROJECT_STAGES:
        return {'status': status, 'original_status': raw,
                'status_definition': PROJECT_STAGES[status], 'status_definition_url': STATUS_SOURCE}
    return {'status': 'Unknown', 'original_status': raw,
            'status_definition': 'A verified stage definition is unavailable for this source status. The publisher wording is preserved; construction and completion are not inferred.'}


def read_source(directory: Path, receipt: dict) -> list:
    """Check digest, resource identity, declared CRS, complete count and all-row field contract."""
    path = directory / receipt['sha256']
    if sha(path) != receipt['sha256']:
        raise ValueError(f'Checksum mismatch: {receipt["key"]}')
    contract = CONTRACTS[receipt['key']]
    if receipt.get('resource_id') != contract['resource_id']:
        raise ValueError(f'Resource identity changed: {receipt["key"]}')
    if receipt['key'] in ('projects', 'applications'):
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        records = rows
    else:
        raw = json.loads(path.read_text(encoding='utf-8'))
        if raw.get('crs', {}).get('properties', {}).get('name') != 'urn:ogc:def:crs:OGC:1.3:CRS84':
            raise ValueError(f'Unknown CRS: {receipt["key"]}')
        if raw.get('type') != 'FeatureCollection':
            raise ValueError('Expected FeatureCollection')
        records = raw['features']
        rows = [f['properties'] for f in records]
    validate_schema(rows, receipt['key'], contract)
    expected = receipt.get('expected_records')
    if not isinstance(expected, int) or isinstance(expected, bool) or len(rows) != expected:
        raise ValueError(f'Incomplete or changed export: {receipt["key"]}: {len(rows)} != {expected}')
    ids = [str(r['_id']) for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f'Duplicate source row IDs: {receipt["key"]}')
    receipt['schema'] = list(rows[0])
    receipt['records_in'] = len(records)
    return records


def valid_geometry(feature: dict, allowed: tuple[str, ...]) -> Any:
    """Validate source geometry without silently repairing or changing its CRS."""
    if not isinstance(feature.get('geometry'), dict):
        raise ValueError('Missing or malformed geometry')
    g = shape(feature['geometry'])
    if g.is_empty or not g.is_valid or g.geom_type not in allowed:
        raise ValueError('Empty, invalid or unsupported geometry')
    w, s, e, n = g.bounds
    if not (-80 < w <= e < -78 and 43 < s <= n < 45):
        raise ValueError('Coordinates outside Toronto validation envelope')
    return g


def tiles(bounds: tuple) -> list[str]:
    """Return all cells intersecting bounds, including boundary cells."""
    w, s, e, n = bounds
    return [f'{x}_{y}' for x in range(math.floor(w/TILE), math.floor(e/TILE)+1)
            for y in range(math.floor(s/TILE), math.floor(n/TILE)+1)]


def resolve_address(address: str, lookup: dict) -> tuple[dict | None, str | None]:
    """Accept only one distinct municipal coordinate for an exact address match."""
    matches = lookup.get(normalize(address), [])
    positions = {(r['lon'], r['lat']) for r in matches}
    if len(positions) != 1:
        return None, 'No exact municipal address match' if not matches else 'Ambiguous municipal address locations'
    return matches[0], None


def build(source_dir: Path, output: Path, components: bool = True) -> dict:
    """Publish only a fully validated snapshot; preserve previous releases on failure."""
    acquisition = json.loads((source_dir / 'acquisition.json').read_text())
    sources = acquisition['sources']
    if set(REQUIRED) != set(sources):
        raise ValueError('Required source missing')
    identity = {k: v['sha256'] for k, v in sources.items()}
    contracts_hash = sha(CONTRACT_PATH)
    identity['contracts'] = contracts_hash
    previous = None
    if (output / 'latest.json').exists():
        previous_id = json.loads((output / 'latest.json').read_text())['id']
        previous_path = output / previous_id / 'manifest.json'
        if previous_path.exists():
            previous = json.loads(previous_path.read_text())
    component_file = ROOT / 'data/components/toronto_citywide_internal.gpkg'
    if components and component_file.exists():
        identity['components'] = sha(component_file)
    elif components and previous and previous.get('buildings'):
        identity['components'] = previous['buildings']['sha256']
    snapshot_id = hashlib.sha256(json.dumps([VERSION, identity], sort_keys=True).encode()).hexdigest()[:20]
    destination = output / snapshot_id
    if destination.exists():
        manifest = json.loads((destination / 'manifest.json').read_text())
        for key, receipt in sources.items():
            if sha(source_dir / receipt['sha256']) != receipt['sha256']:
                raise ValueError(f'Checksum mismatch: {key}')
            if receipt.get('resource_id') != CONTRACTS[key]['resource_id']:
                raise ValueError(f'Resource identity changed: {key}')
            if receipt.get('expected_records') != manifest['sources'][key]['records_in']:
                raise ValueError(f'Incomplete or changed export: {key}')
        publish_latest(output, snapshot_id)
        return manifest
    staging = output / f'.{snapshot_id}.tmp'
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    counts, exclusions, address_lookup, addresses, street_names = {}, [], defaultdict(list), defaultdict(list), set()
    # Address rows are compacted into street-prefix shards; no remote geocoder.
    raw_addresses = read_source(source_dir, sources['addresses'])
    for feature in raw_addresses:
        p = feature['properties']
        try:
            g = valid_geometry(feature, ('Point', 'MultiPoint'))
            if g.geom_type == 'MultiPoint':
                if len(g.geoms) != 1:
                    raise ValueError('Address has multiple source coordinates')
                g = g.geoms[0]
            label = str(p['ADDRESS_FULL']).strip()
            street = normalize(str(p['LINEAR_NAME_FULL']))
            if not label or not street:
                raise ValueError('Missing address label')
            x, y = TO_METRES.transform(g.x, g.y)
            row = {'id': str(p['ADDRESS_POINT_ID']), 'label': label, 'street': street,
                   'lon': g.x, 'lat': g.y, 'xy': [x, y]}
            address_lookup[normalize(label)].append(row)
            key = hashlib.sha256(street.encode()).hexdigest()[:2]
            addresses[key].append(row)
            street_names.add((street, key))
        except (ValueError, TypeError, KeyError) as exc:
            exclusions.append({'source': 'addresses', 'id': str(p['_id']), 'reason': str(exc)})
    counts['addresses'] = sum(map(len, addresses.values()))
    if not counts['addresses']:
        raise ValueError('No usable municipal addresses; publication blocked')
    for key, rows in addresses.items():
        write_json(staging / 'addresses' / f'{key}.json', rows)
    write_json(staging / 'streets-search.json', sorted(street_names))
    del raw_addresses, addresses
    summaries = {}
    for kind in ('projects', 'applications'):
        rows = read_source(source_dir, sources[kind])
        index, details, missing, stages = [], defaultdict(dict), 0, Counter()
        for row in rows:
            identity = f'{kind}:{row["_id"]}'
            if kind == 'projects':
                address, status, number = row['Address'], row['Pipeline Status'], row['Application Number']
                description, link = row['Description'], row.get('Application Information Centre Link')
            else:
                address = ' '.join(row[k] for k in ('STREET_NUM', 'STREET_NAME', 'STREET_TYPE', 'STREET_DIRECTION')).strip()
                status, number = row['STATUS'], row['APPLICATION#']
                description, link = row['DESCRIPTION'], row.get('APPLICATION_URL')
            location, reason = resolve_address(address, address_lookup)
            stage = normalized_status(kind, status)
            source_status = stage['status']
            stages[source_status] += 1
            feature = {'id': identity, 'kind': kind, 'source_id': str(row['_id']), 'number': number,
                       'label': address.strip() or number, **stage,
                       'xy': location['xy'] if location else None,
                       'lon': location['lon'] if location else None, 'lat': location['lat'] if location else None,
                       'geometry_origin': 'address-derived point' if location else 'unlocated',
                       'missing': reason, 'detail': f'details/{kind}-{int(row["_id"])//250}.json'}
            index.append(feature)
            details[int(row['_id'])//250][identity] = {**feature, 'attributes': row, 'description': description,
                'official_url': link, 'address_source_ids': [r['id'] for r in address_lookup.get(normalize(address), [])],
                'repairs': [], 'limitations': ['Source row identity is snapshot-scoped.',
                    'Address match is not a project boundary or a building identity.',
                    'No project/application merging or inferred construction stage.']}
            if reason:
                missing += 1
                exclusions.append({'source': kind, 'id': identity, 'reason': reason})
        write_json(staging / f'{kind}.json', index)
        for key, value in details.items():
            write_json(staging / 'details' / f'{kind}-{key}.json', value)
        counts[kind] = len(index)
        if missing == len(index):
            raise ValueError(f'No located {kind}; publication blocked')
        summaries[kind] = {'records': len(index), 'located': len(index)-missing, 'unlocated': missing, 'stages': dict(stages),
                           'distinct_application_numbers': len({r['number'] for r in index})}
    del address_lookup
    tile_manifest, neighbourhoods, coverage_parts, context = {}, [], [], []
    for kind in ('zoning', 'heights', 'neighbourhoods', 'streets'):
        raw = read_source(source_dir, sources[kind])
        cells, accepted = defaultdict(list), 0
        for feature in raw:
            p = feature['properties']
            try:
                allowed = ('LineString', 'MultiLineString') if kind == 'streets' else ('Polygon', 'MultiPolygon')
                g = valid_geometry(feature, allowed)
                metric = transform(TO_METRES.transform, g)
                identity = f'{kind}:{p["_id"]}'
                if kind == 'neighbourhoods':
                    centre = g.representative_point()
                    coverage_parts.append(metric)
                    neighbourhoods.append({'id': identity, 'label': p['AREA_NAME'], 'lon': centre.x, 'lat': centre.y,
                                           'geometry': mapping(transform(TO_DISPLAY.transform, metric.simplify(10)))})
                elif kind == 'streets':
                    # Centreline includes non-road features; render as general reference lines, not a routable road network.
                    context.append({'type': 'Feature', 'geometry': mapping(transform(TO_DISPLAY.transform, metric.simplify(2))), 'properties': {}})
                else:
                    item = {'id': identity, 'kind': kind, 'source_id': str(p['_id']),
                            'label': p.get('ZN_STRING') or p.get('HT_STRING') or identity,
                            'status': 'Mapped zoning context', 'geometry_origin': 'source polygon',
                            'geometry': mapping(g), 'metric': mapping(metric), 'attributes': p, 'repairs': [],
                            'limitations': ['Reference zoning only; amendments, exceptions and appeals require official review.',
                                             'Negative numeric values are retained as source values, not interpreted as permitted dimensions.']}
                    for cell in tiles(metric.bounds):
                        cells[cell].append(item)
                accepted += 1
            except (ValueError, TypeError, KeyError) as exc:
                exclusions.append({'source': kind, 'id': str(p['_id']), 'reason': str(exc)})
        counts[kind] = accepted
        if not accepted:
            raise ValueError(f'No usable {kind}; publication blocked')
        if kind in ('zoning', 'heights'):
            tile_manifest[kind] = sorted(cells)
            for cell, items in cells.items():
                write_json(staging / kind / f'{cell}.json', items)
    write_json(staging / 'neighbourhoods.json', neighbourhoods)
    # Coverage selection retains full source boundaries. Only display polygons are simplified.
    write_json(staging / 'coverage.json', mapping(unary_union(coverage_parts)))
    write_json(staging / 'context.json', {'type': 'FeatureCollection', 'features': context})
    # Optional, independently qualified component context. Never use SURF_ELEV as ground.
    building_meta = None
    retained_assets = {}
    reuse_buildings = components and previous and previous.get('buildings') and (
        not component_file.exists() or previous['buildings']['sha256'] == sha(component_file))
    if reuse_buildings:
        building_meta = previous['buildings']
        tile_manifest['buildings'] = previous['tiles']['buildings']
        retained_assets = {k:v for k,v in previous['assets'].items() if k.startswith('buildings/')}
    if components and component_file.exists() and not reuse_buildings:
        from server.components import connect, geometry, metadata
        receipt = metadata()
        if receipt.get('checksums', {}).get('toronto_citywide_internal.gpkg') not in (None, sha(component_file)):
            raise ValueError('Component checksum mismatch')
        cells, total = defaultdict(list), 0
        with connect() as connection:
            for row in connection.execute('SELECT fid, geom, StructureID, AVG_HEIGHT, HEIGHT_SRC FROM structures'):
                p = dict(row)
                g = geometry(p.pop('geom'))
                height = p.get('AVG_HEIGHT')
                if height is None or not math.isfinite(float(height)) or float(height) <= 0:
                    continue
                metric = transform(TO_METRES.transform, g)
                item = {'type': 'Feature', 'id': p['StructureID'], 'geometry': mapping(g),
                        'properties': {'id': p['StructureID'], 'height': float(height), 'method': p.get('HEIGHT_SRC'),
                                       'label': 'Illustrative AVG_HEIGHT extrusion; flat base; source component, not whole building'}}
                for cell in tiles(metric.bounds):
                    cells[cell].append(item)
                total += 1
        for cell, rows in cells.items():
            write_json(staging / 'buildings' / f'{cell}.json', rows)
        tile_manifest['buildings'] = sorted(cells)
        building_meta = {'count': total, 'sha256': sha(component_file), 'page': 'https://open.toronto.ca/dataset/3d-massing/',
                         'height': 'AVG_HEIGHT metres; illustrative only, flat reference ground', 'vintage': '2025 release; observation dates vary'}
    write_json(staging / 'exclusions.json', exclusions)
    manifest = {'id': snapshot_id, 'version': VERSION, 'created_at': now(), 'coverage': 'Toronto only',
                'analysis_crs': 'EPSG:26917', 'display_crs': 'EPSG:4326', 'tile_size': TILE,
                'sources': sources, 'counts': counts, 'summaries': summaries, 'tiles': tile_manifest,
                'buildings': building_meta, 'exclusions': len(exclusions),
                'validation': {'checksums': True, 'source_counts': True, 'schema': True, 'crs': True},
                'contracts_sha256': contracts_hash,
                'method': 'Straight-line proximity in EPSG:26917. Features intersecting the selected radius are included. No walking, legal entitlement or causal prediction.'}
    for receipt in sources.values():
        receipt.pop('path', None)
        receipt['records_out'] = counts[receipt['key']]
        receipt['geometry_rejected'] = receipt['records_in'] - receipt['records_out']
    # Content-addressed gzip objects are reused across immutable snapshots.
    assets = dict(retained_assets)
    for asset in sorted(staging.rglob('*.json')):
        raw = asset.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        target = output / 'objects' / (digest + '.json.gz')
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
        assets[asset.relative_to(staging).as_posix()] = digest
        asset.unlink()
    manifest['assets'] = assets
    write_json(staging / 'manifest.json', manifest)
    staging.rename(destination)
    publish_latest(output, snapshot_id)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/planning-source')
    parser.add_argument('--output', type=Path, default=ROOT / 'public/planning')
    parser.add_argument('--no-buildings', action='store_true')
    args = parser.parse_args()
    result = build(args.source, args.output, not args.no_buildings)
    print(json.dumps({'snapshot': result['id'], 'counts': result['counts'], 'summaries': result['summaries']}))
