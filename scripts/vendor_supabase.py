"""Download one vetted SDK asset; validate npm's tarball integrity first."""
import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from urllib.request import urlopen

VERSION = "2.117.3"
ROOT = Path(__file__).resolve().parents[1]


def main():
    metadata = json.load(urlopen(f"https://registry.npmjs.org/@supabase/supabase-js/{VERSION}", timeout=30))
    archive = urlopen(metadata["dist"]["tarball"], timeout=30).read(10_000_001)
    if len(archive) > 10_000_000:
        raise RuntimeError("Unexpected package size")
    expected = "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode()
    if expected != metadata["dist"]["integrity"]:
        raise RuntimeError("npm integrity verification failed")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        asset = bundle.extractfile("package/dist/umd/supabase.js").read()
        license_text = bundle.extractfile("package/LICENSE").read()
    target = ROOT / "web" / "vendor"
    target.mkdir(exist_ok=True)
    (target / "supabase.js").write_bytes(asset)
    (target / "supabase.LICENSE").write_bytes(license_text)
    integrity = "sha384-" + base64.b64encode(hashlib.sha384(asset).digest()).decode()
    (target / "manifest.json").write_text(json.dumps({"version": VERSION, "npm_integrity": expected, "script_integrity": integrity}, indent=2))
    old = f'<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@{VERSION}" defer></script>'
    new = f'<script src="/static/vendor/supabase.js" integrity="{integrity}" defer></script>'
    for page in (ROOT / "web").glob("*.html"):
        page.write_text(page.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    print(f"Vendored verified Supabase SDK {VERSION} ({len(asset)} bytes)")


if __name__ == "__main__":
    main()
