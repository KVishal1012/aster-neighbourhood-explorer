"""Refresh source snapshots, retaining last verified evidence on any acquisition failure."""
from __future__ import annotations
import json
import logging
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.acquire_planning import acquire, now
from scripts.build_planning import build, write_json


def record_failure(output:Path,error:str)->None:
    """Update health only; never change the selected verified snapshot on failure."""
    latest=output/'latest.json'
    if latest.exists():
        health=json.loads(latest.read_text())
        health.update(status='delayed',attempted_at=now(),error=error)
        temporary=output/'health.tmp'
        write_json(temporary,health)
        temporary.replace(latest)


def main()->int:
    """Acquire, validate and prepare the next immutable static snapshot."""
    output=ROOT/'public/planning'
    try:
        acquire(ROOT/'data/planning-source')
        manifest=build(ROOT/'data/planning-source',output)
        logging.info('Verified snapshot %s',manifest['id'])
        return 0
    except (ValueError,OSError,KeyError,RuntimeError) as exc:
        logging.exception('Planning refresh failed')
        record_failure(output,'Source acquisition or validation failed; last verified data retained. See maintainer workflow logs.')
        return 1
    except Exception:
        # Unexpected errors still preserve last-good state, but remain visible and fail the job.
        logging.exception('Unexpected planning refresh failure')
        record_failure(output,'Unexpected refresh failure; last verified data retained. See maintainer workflow logs.')
        return 1

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
