"""Pin the resolved serving dependency graph from the verified environment."""
import importlib.metadata as metadata
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parents[1]
queue = [Requirement(line).name for line in (root / "requirements.txt").read_text().splitlines()
         if line and not line.startswith(("#", "-"))]
resolved = {}
while queue:
    name = canonicalize_name(queue.pop())
    if name in resolved:
        continue
    distribution = metadata.distribution(name)
    resolved[name] = distribution.version
    for value in distribution.requires or []:
        requirement = Requirement(value)
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        queue.append(requirement.name)
(root / "requirements.lock").write_text("# Tested runtime versions; regenerate after dependency updates.\n" +
    "\n".join(f"{name}=={version}" for name,version in sorted(resolved.items())) + "\n")
print(f"Pinned {len(resolved)} resolved runtime packages; Linux image is separately checked in CI.")
