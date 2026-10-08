# CPython 3.14.8 security backports

The Docker build installs four standard-library modules from official CPython v3.14.8
with exactly these merged upstream fixes applied, without manual edits:

- CVE-2025-15367: https://github.com/python/cpython/commit/b234a2b67539f787e191d2ef19a7cbdce32874e7
- CVE-2026-87910: https://github.com/python/cpython/commit/fb2f0bbc3b35264f09cc2cb2934b7987527a6bc2
- CVE-2026-12345: https://github.com/python/cpython/commit/5c20517a4fc56683efe63a7751020db9573f538d

manifest.json records original and patched SHA-256 hashes. Patch files retain the
standard-library portions of the official commits. LICENSE is the CPython license.
The installer refuses a different interpreter version or original/patched module hash.
All modules are verified before any installation, and stale bytecode is removed.

The Docker build then runs scripts/test_python_security.py as its non-root user.
The checks verify installed hashes, reject every POP3 control character, skip a tar
link fallback rejected by its filter, and trigger a real permission-error/symlink
race while checking that outside files and modes are preserved. A failed check
stops the image build before the vulnerability scan. Windows skips only the Linux
race test; that test is mandatory on the Linux deployment image.

Python still reports version 3.14.8, so Grype cannot infer these backports from its
version database. .grype.yaml exempts only these three CVE matches for Python
3.14.8 of type binary. It does not exempt other packages, CVEs or runtime versions.
The workflow retains its existing low threshold and only-fixed policy. This policy
excludes unfixed OS vulnerabilities and must not be interpreted as zero total risk.

Remove the backports and associated rules once an official compatible release fixes
all three findings. Re-review before any runtime digest change. Do not switch to
Python 3.15 until stable images and the required scientific dependency wheels exist.

Validation: all four regressions pass in the non-root Linux image. Application tests
(25), browser tests, dependency audits, model prediction smoke test and the blocking
container scan pass: https://github.com/panda7ad/Credit-sure/actions/runs/37820721876
The workflow also reports remaining findings without only-fixed filtering, separately
from the existing blocking gate, to keep unfixed OS issues visible.
