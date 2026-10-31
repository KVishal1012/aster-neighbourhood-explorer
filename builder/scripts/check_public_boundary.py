"""Fail if the public build contains private entry points or non-public files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check(root: Path) -> None:
    manifest = json.loads((root / '.vite/manifest.json').read_text())
    allowed = {'index.html', 'src/main-public.tsx'}
    for key, entry in manifest.items():
        source = entry.get('src', key)
        if not (source in allowed or source.startswith('src/planning/') or source.startswith('_')):
            raise ValueError(f'Non-public module in public build: {source}')
    for file in root.rglob('*'):
        if not file.is_file():
            continue
        path = file.relative_to(root).as_posix()
        if not (path in {'index.html', '.nojekyll', 'release-validation.json', '.vite/manifest.json'} or path.startswith(('assets/', 'planning/'))):
            raise ValueError(f'Non-public file in distribution: {path}')
        if file.suffix == '.js':
            content = file.read_text()
            for marker in ('Photorealistic 3D', 'Opening local research workspace', 'VITE_GOOGLE_MAPS_API_KEY', 'TerrainScene'):
                if marker in content:
                    raise ValueError(f'Private research marker in {path}: {marker}')
    print('Public boundary passed: isolated planning entry and public file allowlist.')

if __name__ == '__main__':
    check(ROOT / 'dist-public')
