"""Check deployment assets, script integrity, and accidental tracked secrets."""
import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "models/manifest.json").read_text())
for name in ("credit_model.joblib", "metadata.json"):
    assert hashlib.sha256((ROOT / "models" / name).read_bytes()).hexdigest() == manifest[name], f"Model manifest mismatch: {name}"
sdk = ROOT / "web/vendor/supabase.js"
integrity = "sha384-" + base64.b64encode(hashlib.sha384(sdk.read_bytes()).digest()).decode()
for page in (ROOT / "web").glob("*.html"):
    text = page.read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" not in text, "Unvendored browser dependency"
    assert "supabase.js" not in text, "Retired account SDK is loaded"
    assert not re.search(r'\son(?:click|load|submit|error)\s*=', text), "Inline script conflicts with CSP"
try:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().split("\0")
except (subprocess.CalledProcessError, FileNotFoundError):
    tracked = [str(p.relative_to(ROOT)) for folder in ("app", "web", "scripts", "supabase") for p in (ROOT/folder).rglob("*") if p.is_file()]
for name in tracked:
    if not name:
        continue
    assert not (Path(name).name == ".env" or (Path(name).name.startswith(".env.") and Path(name).name != ".env.example")), "Environment file is tracked"
    path = ROOT / name
    if path.suffix in (".pyc", ".joblib", ".png") or not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    assert not re.search(r'sb_secret_[A-Za-z0-9_-]{20,}', text), f"Possible secret key in {name}"
    for token in re.findall(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', text):
        try:
            part = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(part+"="*(-len(part)%4)))
        except (ValueError, TypeError):
            continue
        assert not isinstance(claims, dict) or claims.get("role") != "service_role", f"Possible service-role key in {name}"
print("PASS model hashes, retired account SDK, CSP-compatible HTML and tracked-secret checks")
