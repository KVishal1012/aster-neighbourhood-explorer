# Planning release verification — 2026-10-22

## Qualified source snapshot

- Projects: 2,391 source rows; 1,849 located by exact unambiguous municipal-address coordinates; 542 unlocated.
- Applications: 26,648 source rows; 19,522 located; 7,126 unlocated. There are 8,622 distinct application numbers, so source rows are not counted as independent projects.
- Municipal address points: 525,371. Source single-member MultiPoint geometries are interpreted as their sole coordinate, with no averaging.
- Zoning: 11,719 input polygons, 11,697 accepted, 22 invalid geometries excluded.
- Height overlays: 2,528 input polygons, 2,479 accepted, 49 invalid geometries excluded.
- Neighbourhoods: 158; centreline reference features: 64,394 (includes non-road features; no routing claim).
- Illustrative building context: 427,029 source components, AVG_HEIGHT metres on a flat base. Existing independently verified component package SHA-256: 400a6227e33d74fe5c4fc4bd82ecf39784072bf95cec09fdeb3fd34bcbb25151.

GeoJSON explicitly declares OGC:CRS84. Analysis coordinates are EPSG:26917. Each input is archived by SHA-256. Row counts match publisher resource metadata; source IDs must be unique. Project categories are Under Review, Active and Built, with definitions from the City’s 2024 Development Pipeline bulletin (page 2). Every original status is retained. Application planning-stage interpretation is Unknown until definitions are independently qualified; the exact publisher status remains visible. Source modification dates are not feature observation dates.

Publisher dataset pages explicitly display the Toronto Open Government Licence; CKAN metadata is unspecified for several sources. Both facts and evidence hashes appear in receipts. Zoning catalogue notes refer to amendments through June 18, 2023; the February 2026 export timestamp is not represented as a 2026 legal consolidation.

## Completed checks

- Public production build succeeds; it contains no mobility API or Cesium dependency.
- Python contract tests cover checksum/schema/count failures, all-row field/type drift, duplicate IDs, unknown CRS, invalid geometry, ambiguous addresses, tile boundaries, unknown stages and interrupted atomic publication. The full local Python suite passes 50 tests.
- CSV/JSON evidence serialization tests cover snapshot identity, original statuses, dates, escaping and spreadsheet-formula prefixes. Compiled-worker tests cover unavailable historical snapshots and absence of mobility API calls.
- Browser projection control points agree with pyproj within 2 cm; polygon holes, exact radius edges, multipolygons and invalid-query rejection tested.
- Browser standalone static preview: default 800 m downtown query returns 63 project records. 100 Queen St W → Under Review returns 18 records. Selecting 191 Dundas St W shows original project attributes and source dates. Zoning query at that selected address returns 231 source polygons.

## Release-content review

Distribution is constructed with an explicit allowlist. Only the built site, referenced qualified data objects, isolated planning source code, tests, documentation and workflows are copied. No .env, account credentials, workspace Git history, private research files, raw acquisition archives, local databases, source emails or user memories are included. Source attributes remain publisher-supplied public records. Source strings render as escaped text; external links reject non-HTTP(S) schemes; CSV exports escape formula prefixes.

Display neighbourhood polygons are simplified by 10 m. Coverage calculations use the unsimplified union of source polygons; zoning selection also retains original geometry.

## Outstanding validation

- No independent resident sessions have occurred. On October 22, the owner chose documented developer walkthroughs plus optional self-guided public feedback instead of recruiting five residents. This is not equivalent evidence of resident usability or impact.
- Formal screen-reader and throttled mobile-network testing remain pending. Automated tests and browser inspection do not substitute for these evaluations.
- Source updates are snapshots, not live construction observations. GIS observations remain limited by publisher completeness and positional accuracy.

## Optional resident study protocol

With consent, ask each participant to choose a familiar Toronto location, find a project within 800 m, explain its status, locate its source date and identify an unlocated record. Record completion, help needed, confusion and suggested improvements; do not collect home addresses in study notes. Any approval-versus-completion misunderstanding blocks an award-ready claim until corrected and retested.

## Additional verified behavior

- Snapshot-pinned share link includes the selected location, radius, dataset and filters.
- Latest application evidence preserves Closed as the source status while explicitly showing Unknown for its unqualified planning-stage interpretation.
- Browser CSV export completed: 560 application rows for the downtown 800 m query, all pinned to snapshot f3a5f9ee996a0f10f91c, original statuses retained.
- Public package: 1,081 content-addressed objects, 351,854,075 compressed bytes across three retained snapshots.
- Local research production build still succeeds. Public build includes no mobility API or Cesium code.
