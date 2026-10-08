# Security notes

Current scope: a public research calculator with no signup, login, account API, database writes, or saved assessment history. Removed account clients, SQL migrations, and SDK bundles are available in Git history if needed; removing code does not delete any old Supabase records.

## Active protections

- Strict request schemas, finite numeric bounds, research confirmation, and a 16 KiB request limit.
- Exact allowed hosts, restricted same-origin CSP, no inline scripts, frame protection, and no-store API responses.
- Shared Redis rate limiting in production, local limits in development, global prediction budgets, and two concurrent inference slots.
- Production readiness fails closed without Redis, a sufficiently long rate-limit salt, and completed launch configuration.
- Trusted SHA-256 model manifest; non-root Docker execution; verified official CPython backports tested inside the image.
- Sanitized failure responses, browser request timeouts, text-only result rendering, and no browser assessment persistence.

## Validation and limitations

Run the API/security tests, browser tests, release checks, and CI dependency/image scans before releasing. The blocking image scan uses `only-fixed: true`; a separate report shows unfixed OS vulnerabilities. Three version-based Python findings are scoped out only because their verified upstream patches are installed in the Docker image; see `vendor/cpython_security/README.md`.

The model is an educational experiment with synthetic alternative-credit signals. It is not validated for real lending or eligibility decisions. Use fictional inputs. Hosting providers can retain operational logs; Redis stores expiring hashed rate counters. Existing records in a previously configured Supabase project must be managed separately by its owner.

Production provider settings and remaining OS findings still require review as described in `LAUNCH_SETUP.md`. These controls are not a guarantee against every vulnerability.
