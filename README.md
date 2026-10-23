# ASTER Toronto · Neighbourhood Planning Explorer

Public beta: https://kvishal1012.github.io/aster-neighbourhood-explorer/

Free public beta: discover recorded development and mapped zoning near a Toronto address. Guided browser-only queries, dated evidence, source attributes, exports and optional illustrative building context.

## Coverage and limitations

Toronto only. GTA coverage and energy layers are planned, not implemented. Project and application records are separate. Exact application statuses are preserved, with documented planning stage marked Unknown until their definitions are qualified. **Active does not confirm construction.** Exact municipal address matching leaves ambiguous or unmatched records unlocated and searchable. Zoning is informational, with source amendments and exceptions requiring official review. Building extrusions use source AVG_HEIGHT on a flat base; no proposed buildings, surveyed roof reconstruction or terrain alignment is claimed.

Data comes from the City's Development Pipeline, Development Applications, Zoning By-law, Municipal Address Points, neighbourhoods, Toronto Centreline and independently qualified 2025 massing components. Catalogue page licence evidence is retained even where CKAN licence fields are unspecified.

Contains information licensed under the **Open Government Licence – Toronto**. This independent application is not endorsed by the City. See the in-app Sources & dates page and snapshot manifests for provenance, dates, checksums, exclusions and qualifications.

## Repository layout

- `site/`: reviewed public distribution, immutable manifests and content-addressed compressed objects.
- `builder/`: isolated application source, validators and reproducible acquisition/build tooling; no original private workspace.
- `.github/workflows/`: Pages deployment and daily source checks at 10:00 UTC. GitHub scheduled runs may be delayed.

## Reproduce

From `builder/`, use Python 3.12, Node 22 and curl:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci
mkdir -p public
cp -a ../site/planning public/planning
.venv/bin/python scripts/refresh_planning.py
.venv/bin/python -m unittest discover -s tests -v
npm run test:planning
npm run build:public
npm run test:worker
python -m http.server 5174 --directory dist-public
```

Initial raw acquisition is approximately 700 MB; allow several GB of temporary storage. No cloud key, public database or application server is needed. Prequalified static building objects are retained from the distribution during refreshes; the local research GeoPackage is not required or published.

Failed acquisition preserves the prior verified snapshot and updates a visible delayed-refresh notice. Retained snapshots are never silently replaced. The package validator checks all referenced object hashes and enforces an 850 MB data budget; exceeding it requires a hosting migration, not deletion of evidence history. Raw refresh inputs are retained as workflow artifacts for 90 days; published derived snapshots and receipts remain in Git history and the site. Long-term raw archive hosting remains a future operational improvement.

The complete results list and evidence panels are available without WebGL. No analytics, account system, third-party geocoder or LLM. Standard hosting logs may record requested asset paths. The owner selected developer task walkthroughs plus optional self-guided public feedback instead of a recruited five-resident panel. No resident findings or impact claims are made. See [FEEDBACK.md](FEEDBACK.md). Formal screen-reader and physical-device CPU evaluation remain unverified. A controlled mobile-network emulation is documented in VALIDATION.md.
