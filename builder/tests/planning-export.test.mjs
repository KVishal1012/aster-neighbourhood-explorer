import test from 'node:test';
import assert from 'node:assert/strict';
import {serializeEvidenceCsv, serializeEvidenceJson} from '../src/planning/export.ts';

const snapshot = {
  id: '3109928bc7881940611a', created_at: '2026-10-22T11:41:36Z',
  sources: {projects: {publisher: 'City of Toronto', retrieved_at: '2026-10-22T11:31:22Z',
    source_modified_at: '2026-10-08T07:24:50', sha256: 'a'.repeat(64)}},
};
const query = {lon: -79.3832, lat: 43.6532, radius: 800, kind: 'projects', stage: 'Active'};
const feature = {id: 'projects:7', kind: 'projects', source_id: '7', label: '100 Queen St W',
  status: 'Active', distance: 0, geometry_origin: 'address-derived point', missing: null};
const result = {snapshot_id: snapshot.id, query, rows: [feature], coverage: true,
  method: 'Straight-line proximity in EPSG:26917.'};

test('CSV preserves snapshot identity, exact status and measured zero distance', () => {
  const csv = serializeEvidenceCsv(snapshot, result);
  assert.equal(csv, '"snapshot_id","source","source_id","address_or_label","source_status","normalized_stage","distance_m","geometry_origin","missing"\r\n' +
    '"3109928bc7881940611a","projects","7","100 Queen St W","Active","Active","0","address-derived point",""');
  const missing = serializeEvidenceCsv(snapshot, {...result, rows: [{...feature, distance: undefined,
    geometry_origin: 'unlocated', missing: 'No exact municipal address match'}]});
  assert.ok(missing.endsWith('"","unlocated","No exact municipal address match"'));
});

test('CSV quotes commas, quotes and multiline text and neutralizes spreadsheet formula prefixes', () => {
  const values = ['=1+1', '+SUM(A1)', '-1+1', '@SUM(A1)', '\t=1+1', '\r=1+1'];
  for (const label of values) {
    const csv = serializeEvidenceCsv(snapshot, {...result, rows: [{...feature, label}]});
    assert.ok(csv.includes(',"\'' + label + '","Active",'), label);
  }
  const label = '100 "Queen", West\nsecond line';
  const csv = serializeEvidenceCsv(snapshot, {...result, rows: [{...feature, label}]});
  assert.ok(csv.includes(',"100 ""Queen"", West\nsecond line","Active",'));
});

test('JSON preserves query, source dates, original attributes and selected evidence without mutation', () => {
  const selected = {...feature, attributes: {'Pipeline Status': 'Active', Description: 'A "quoted" source\nrecord'},
    repairs: [], limitations: ['Address match is not a project boundary.']};
  const before = JSON.stringify({snapshot, result, selected});
  const evidence = JSON.parse(serializeEvidenceJson(snapshot, result, selected));
  assert.equal(evidence.snapshot.id, result.snapshot_id);
  assert.deepEqual(evidence.query, query);
  assert.equal(evidence.method, result.method);
  assert.deepEqual(evidence.results, result.rows);
  assert.deepEqual(evidence.selected_evidence, selected);
  assert.deepEqual(evidence.snapshot.sources.projects, snapshot.sources.projects);
  assert.equal(evidence.snapshot.created_at, snapshot.created_at);
  assert.equal(JSON.stringify({snapshot, result, selected}), before);
  assert.equal(JSON.parse(serializeEvidenceJson(snapshot, result, null)).selected_evidence, null);
});

test('CSV preserves publisher wording independently of an unknown normalized stage', () => {
 const csv = serializeEvidenceCsv(snapshot, {...result, rows: [{...feature, status: 'Unknown', original_status: 'NOAC Issued'}]});
 assert.ok(csv.includes('"NOAC Issued","Unknown"'));
});
