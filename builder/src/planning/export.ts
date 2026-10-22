import type {PlanningFeature, PlanningQueryResult, PlanningSnapshot} from './types';

/** Keep source text literal when a CSV is opened by spreadsheet software. */
function csvCell(value: unknown): string {
  let text = String(value ?? '');
  if (/^[=+@\-\t\r]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}

/** Export the same source-record columns shown by the results list. */
export function serializeEvidenceCsv(snapshot: PlanningSnapshot, result: PlanningQueryResult): string {
  const rows = [
    ['snapshot_id', 'source', 'source_id', 'address_or_label', 'source_status', 'normalized_stage', 'distance_m', 'geometry_origin', 'missing'],
    ...result.rows.map(row => [snapshot.id, row.kind, row.source_id, row.label, row.original_status ?? row.status, row.status,
      row.distance ?? '', row.geometry_origin, row.missing || '']),
  ];
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n');
}

/** Retain the complete receipt ledger, actual query, and selected source evidence. */
export function serializeEvidenceJson(
  snapshot: PlanningSnapshot,
  result: PlanningQueryResult,
  selection: PlanningFeature | null,
): string {
  return JSON.stringify({snapshot, query: result.query, method: result.method,
    results: result.rows, selected_evidence: selection}, null, 2);
}
