"""Contract and evidence failure cases for the public planning publisher."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.build_planning import read_source, resolve_address, valid_geometry, tiles, publish_latest, validate_schema, normalized_status
from scripts.refresh_planning import record_failure
from scripts.package_public import package


class PlanningContracts(unittest.TestCase):
    def setUp(self):
        fields = {'_id', 'Application Number', 'Pipeline Status', 'Address', 'Description'}
        self.contract = {'resource_id': 'test-resource', 'fields': {field: ['string'] for field in fields}}
        patched = patch('scripts.build_planning.CONTRACTS', {'projects': self.contract, 'zoning': self.contract})
        patched.start()
        self.addCleanup(patched.stop)

    def receipt(self, directory, content, key='projects', count=1):
        raw = content.encode()
        digest = hashlib.sha256(raw).hexdigest()
        (directory / digest).write_bytes(raw)
        return {'key': key, 'sha256': digest, 'expected_records': count, 'resource_id': 'test-resource'}

    def test_schema_drift_in_later_rows_and_unexpected_types(self):
        contract = {'fields': {'_id': ['number'], 'name': ['string']}}
        valid = {'_id': 1, 'name': 'A'}
        validate_schema([valid, {'_id': 2, 'name': None}], 'test', contract)
        for second in ({'_id': 2}, {'_id': 2, 'name': 'A', 'extra': 'x'}, {'_id': 2, 'name': 42}):
            with self.assertRaisesRegex(ValueError, 'Schema drift'):
                validate_schema([valid, second], 'test', contract)

    def test_undocumented_status_stays_unknown_with_raw_wording(self):
        for kind, raw in [('projects', 'Permit Issued'), ('projects', ''), ('applications', 'NOAC Issued')]:
            stage = normalized_status(kind, raw)
            self.assertEqual(stage['status'], 'Unknown')
            self.assertEqual(stage['original_status'], raw)
        active = normalized_status('projects', 'Active')
        self.assertEqual(active['status'], 'Active')
        self.assertIn('does not independently confirm construction', active['status_definition'])
        self.assertIn('toronto.ca', active['status_definition_url'])

    def test_missing_or_ambiguous_address_is_not_invented(self):
        row = {'lon': -79.4, 'lat': 43.7, 'id': '1'}
        self.assertEqual(resolve_address(' 100 queen st w ', {'100 QUEEN ST W': [row]})[0], row)
        self.assertIsNone(resolve_address('100 QUEEN', {})[0])
        second = {**row, 'lon': -79.41, 'id': '2'}
        self.assertEqual(resolve_address('A', {'A': [row, second]})[1], 'Ambiguous municipal address locations')

    def test_duplicate_coordinates_are_not_ambiguous(self):
        row = {'lon': -79.4, 'lat': 43.7}
        self.assertIsNotNone(resolve_address('A', {'A': [row, row]})[0])

    def test_count_schema_checksum_and_duplicate_ids_fail_closed(self):
        header = '_id,Application Number,Pipeline Status,Address,Description\n'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipt = self.receipt(root, header+'1,A,Active,100 Queen,Example\n')
            self.assertEqual(read_source(root, receipt)[0]['Pipeline Status'], 'Active')
            receipt['expected_records'] = 2
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                read_source(root, receipt)
            receipt = self.receipt(root, header+'1,A,Active,A,x\n1,B,Built,B,y\n', count=2)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                read_source(root, receipt)
            receipt = self.receipt(root, '_id,Address\n1,A\n')
            with self.assertRaisesRegex(ValueError, 'Schema'):
                read_source(root, receipt)
            (root / receipt['sha256']).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Checksum'):
                read_source(root, receipt)

    def test_unknown_crs_is_not_guessed(self):
        raw = {'type':'FeatureCollection','features':[],'crs':{'properties':{'name':'EPSG:3857'}}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            receipt=self.receipt(root,json.dumps(raw),'zoning',0)
            with self.assertRaisesRegex(ValueError,'Unknown CRS'):
                read_source(root,receipt)

    def test_invalid_polygon_is_quarantined_not_repaired(self):
        feature={'geometry':{'type':'Polygon','coordinates':[[[-79.4,43.6],[-79.3,43.7],[-79.4,43.7],[-79.3,43.6],[-79.4,43.6]]]}}
        with self.assertRaisesRegex(ValueError,'invalid'):
            valid_geometry(feature,('Polygon',))

    def test_cell_boundary_includes_both_sides(self):
        self.assertEqual(tiles((1999,1999,2000,2000)),['0_0','0_1','1_0','1_1'])


class PlanningReleaseTests(unittest.TestCase):
    def test_interrupted_pointer_swap_preserves_last_good_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = {'id':'a'*20, 'checked_at':'2026-10-22T00:00:00Z', 'status':'ok'}
            (root/'latest.json').write_text(json.dumps(old))
            original = (root/'latest.json').read_bytes()
            with patch('scripts.build_planning.os.replace', side_effect=OSError('interrupted publication')):
                with self.assertRaisesRegex(OSError, 'interrupted publication'):
                    publish_latest(root, 'b'*20)
            self.assertEqual((root/'latest.json').read_bytes(), original)
            self.assertEqual(json.loads((root/'latest.json').read_text()), old)
            self.assertEqual(list(root.glob('.latest-*.tmp')), [])
            publish_latest(root, 'b'*20)
            current = json.loads((root/'latest.json').read_text())
            self.assertEqual(current['id'], 'b'*20)
            self.assertEqual(current['status'], 'ok')
            self.assertEqual(list(root.glob('.latest-*.tmp')), [])

    def test_failure_retains_last_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'latest.json').write_text(json.dumps({'id':'a'*20,'checked_at':'2026-10-22T00:00:00Z','status':'ok'}))
            record_failure(root,'offline')
            result=json.loads((root/'latest.json').read_text())
            self.assertEqual(result['id'],'a'*20)
            self.assertEqual(result['checked_at'],'2026-10-22T00:00:00Z')
            self.assertEqual(result['status'],'delayed')

    def test_public_package_refuses_corrupt_objects(self):
        import gzip
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';destination=root/'site'
            (source/'objects').mkdir(parents=True)
            identifier='a'*20;digest='b'*64
            (source/identifier).mkdir()
            (source/'latest.json').write_text(json.dumps({'id':identifier}))
            (source/identifier/'manifest.json').write_text(json.dumps({'id':identifier,'validation':{'schema':True},'assets':{'projects.json':digest}}))
            (source/'objects'/f'{digest}.json.gz').write_bytes(gzip.compress(b'[]'))
            with self.assertRaisesRegex(ValueError,'checksum'):
                package(source,destination)
