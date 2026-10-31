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
    ...result.rows.map(row => [snapshot.id, row.source_key||row.kind, row.source_id, row.label, row.original_status ?? row.status, row.status,
      row.distance ?? '', row.geometry_origin, row.missing || '']),
  ];
  if(snapshot.regional){rows[0].push('jurisdiction_id','source_scope','source_snapshot','coverage_notes');result.rows.forEach((r,i)=>rows[i+1].push(r.jurisdiction_id||snapshot.sources[r.source_key||r.kind]?.jurisdiction_id||'',r.source_scope||'municipal',snapshot.source_refs?.[r.source_key||'']?.id||snapshot.source_snapshots?.[r.source_key||'toronto']||snapshot.id,(result.coverage_notes||[]).join(' | ')));}
  rows[0].push('source_publisher','source_retrieved_at','source_url','status_caveat');
  result.rows.forEach((row,i)=>{const source=snapshot.sources[row.source_key||row.kind];rows[i+1].push(source?.publisher||'',source?.retrieved_at||'',source?.page||'','Planning approval does not confirm construction has started or finished. Retrieval is not an observation date.');});
  return rows.map(row => row.map(csvCell).join(',')).join('\r\n');
}

/** Retain the complete receipt ledger, actual query, and selected source evidence. */
export function serializeEvidenceJson(
  snapshot: PlanningSnapshot,
  result: PlanningQueryResult,
  selection: PlanningFeature | null,
): string {
  return JSON.stringify({snapshot, query: result.query, method: result.method,
    coverage: result.coverage, coverage_notes: result.coverage_notes||[], jurisdictions: result.jurisdictions||[], results: result.rows, selected_evidence: selection}, null, 2);
}
