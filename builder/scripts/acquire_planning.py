"""Acquire fixed official resources with immutable bytes and licence-page evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id='
SPECS = {
    'projects': ('development-pipeline', 'Development Pipeline'),
    'applications': ('development-applications', 'Development Applications'),
    'addresses': ('address-points-municipal-toronto-one-address-repository', 'Address Points - 4326.geojson'),
    'zoning': ('zoning-by-law', 'Zoning Area - 4326.geojson'),
    'heights': ('zoning-by-law', 'Zoning Height Overlay - 4326.geojson'),
    'neighbourhoods': ('neighbourhoods', 'Neighbourhoods - 4326.geojson'),
    'streets': ('toronto-centreline-tcl', 'Centreline - Version 2 - 4326.geojson'),
}


def now() -> str:
    """Return an explicit UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def download(url: str, directory: Path) -> tuple[Path, str]:
    """Archive a complete response by content hash; never overwrite a prior input."""
    temporary = directory / 'download.tmp'
    if not url.startswith(('https://ckan0.cf.opendata.inter.prod-toronto.ca/', 'https://open.toronto.ca/')):
        raise ValueError('Resource host changed; source review required')
    digest = hashlib.sha256()
    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location', '--proto', '=https', '--proto-redir', '=https', '--max-time', '300', '--retry', '2', url, '--output', str(temporary)], check=True)
    with temporary.open('rb') as response:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
    value = digest.hexdigest()
    target = directory / value
    temporary.replace(target)
    return target, value


def acquire(directory: Path) -> dict:
    """Resolve named resources, archive publisher licence evidence and raw data."""
    directory.mkdir(parents=True, exist_ok=True)
    receipts, packages = {}, {}
    for key, (slug, name) in SPECS.items():
        logging.info('Acquiring %s', key)
        if slug not in packages:
            path, metadata_hash = download(CATALOG + slug, directory)
            payload = json.loads(path.read_text(encoding='utf-8'))
            if not payload.get('success'):
                raise ValueError(f'Catalogue lookup failed: {slug}')
            page = f'https://open.toronto.ca/dataset/{slug}/'
            licence_path, licence_hash = download(page, directory)
            html = licence_path.read_text(encoding='utf-8')
            if 'Open Government Licence' not in html or 'open-data-licence' not in html and 'open-data-license' not in html:
                raise ValueError(f'Publisher licence evidence needs review: {page}')
            packages[slug] = (payload['result'], metadata_hash, licence_hash)
        package, metadata_hash, licence_hash = packages[slug]
        matches = [r for r in package['resources'] if r['name'] == name]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one {name}; found {[r["name"] for r in package["resources"]]}')
        resource = matches[0]
        path, digest = download(resource['url'], directory)
        # The datastore source describes the count for its exported GeoJSON cache.
        parent = next((r for r in package['resources'] if r['name'] == name.split(' - 4326')[0]), resource)
        receipts[key] = {
            'key': key, 'name': name, 'publisher': 'City of Toronto', 'slug': slug,
            'page': f'https://open.toronto.ca/dataset/{slug}/', 'url': resource['url'],
            'resource_id': resource['id'], 'sha256': digest, 'metadata_sha256': metadata_hash,
            'licence_evidence_sha256': licence_hash, 'licence': 'Open Government Licence – Toronto',
            'api_licence': package.get('license_title'),
            'licence_basis': 'Publisher dataset page explicitly links Open Government Licence – Toronto; API metadata may be unspecified.',
            'retrieved_at': now(), 'source_modified_at': resource.get('last_modified') or parent.get('datastore_cache_last_update'),
            'refresh_rate': package.get('refresh_rate'), 'expected_records': parent.get('record_count'),
            'notes': package.get('notes'), 'path': path.name,
        }
    result = {'acquired_at': now(), 'sources': receipts}
    temporary = directory / 'acquisition.tmp'
    temporary.write_text(json.dumps(result, indent=2), encoding='utf-8')
    temporary.replace(directory / 'acquisition.json')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'data/planning-source')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    acquire(args.directory)
