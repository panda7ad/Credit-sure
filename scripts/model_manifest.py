"""Run only on YOUR trusted trained artifacts, before deployment."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "models"
manifest = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("credit_model.joblib", "metadata.json")}
(root / "manifest.json").write_text(json.dumps(manifest, indent=2))
print("Recorded trusted model artifact hashes; commit the model, metadata, and manifest together.")
