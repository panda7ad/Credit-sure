"""Install verified upstream backports in the pinned Python 3.14.8 image."""
import hashlib
import json
from pathlib import Path
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'vendor/cpython_security'
manifest = json.loads((SOURCE / 'manifest.json').read_text())
if sys.version_info[:3] != (3, 14, 8):
    raise RuntimeError('Re-review backports before changing Python 3.14.8')
stdlib = Path(sysconfig.get_path('stdlib'))
for name, hashes in manifest['modules'].items():
    for path, expected in ((SOURCE / name, hashes['patched']),
                           (stdlib / name, hashes['original'])):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Unexpected CPython source bytes: {path}')
for name in manifest['modules']:
    (stdlib / name).write_bytes((SOURCE / name).read_bytes())
    for cache in (stdlib / '__pycache__').glob(Path(name).stem + '.*.pyc'):
        cache.unlink()
print('Installed verified upstream fixes for all three Python CVEs')
