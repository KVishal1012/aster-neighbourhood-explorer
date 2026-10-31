# Public transportation module

Scope decision, October 29, 2026: transportation is part of ASTER Public. Energy profiles, energy benchmarking and retrofit experiments remain private ASTER Lab scope.

## Implemented scope

The optional “Transportation nearby” section uses the selected place and its 400/800/1600 metre radius. It reports TTC boarding-stop proximity, source route associations and hourly counts of regular-pickup published departure rows. It retains source stop attributes, route IDs, source retrieval dates, ZIP checksum, feed dates and a separate transportation snapshot identity. Export and transportation share links preserve the selected date/hour and both planning and transportation snapshot IDs.

This is not walking access, route planning, observed reliability, live arrival prediction or verified wheelchair journey accessibility. Cycling and other operators are not integrated. The TTC feed includes stops beyond Toronto; this does not qualify all transit in those municipalities.

## Source qualification

Official dataset: https://open.toronto.ca/dataset/merged-gtfs-ttc-routes-and-schedules/

Official licence: https://open.toronto.ca/open-data-licence/

The dataset page explicitly links Open Government Licence – Toronto. The API licence field is `notspecified`; the receipt retains that discrepancy and the archived official page/licence evidence. Attribution is displayed in the UI. No logos or endorsement are used.

Initial qualified feed: `S1000542`, September 30–October 31, 2026. The complete ZIP was downloaded twice with matching SHA-256 and stable catalogue resources. CRC, required files, unique identities, parent references, route/trip/service/stop references and trip/stop-sequence uniqueness were checked. All source stop/location records remain in the snapshot; only location_type 0 boarding stops enter radius results. Geometry is calculated in EPSG:26917 from original WGS84 coordinates.

Calendar exceptions override weekly service; after-midnight times use their originating service day. Counts exclude non-regular pickup rows and missing departure times, with accounting shown in the UI. Supplied estimated intermediate times remain supplied estimates. First-day overnight service may be partial. Outside feed dates, counts are unavailable, not zero. Neighbouring stops can count the same trip and must not be summed as unique vehicles.

## Refresh and rollback

1. Run `.venv/bin/python scripts/acquire_transport.py` to create an immutable dated source directory. A changing feed or source contract stops qualification.
2. Run `.venv/bin/python scripts/build_transport.py --source <acquisition directory>` to validate and create a content-addressed local snapshot. The latest pointer changes only after successful validation. Raw data stays ignored.
3. Run `npm run test:transport`, the public regression suites and `npm run build:public`. Packaging checks transport object hashes and the combined public size limit. No network acquisition runs at page startup.
4. Review the feed's date coverage before publishing. An expired feed stays available for historical queries with an explicit warning. No automatic refresh or external publication was enabled.

To roll back, restore the local `public/transport/latest.json` pointer to a retained validated snapshot and rebuild. Preserve historical manifests/objects so pinned links keep working. Hosts serving only an external planning data endpoint must also serve the packaged `planning/transport/` path alongside the app.

## Deferred

Cycling infrastructure, additional operators, real-time feeds and network-based travel times need their own source, licence and validation work. No energy feature belongs in this public module.
