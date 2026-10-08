"""Publish the research-only policy text supplied for this project."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
contact = '<a href="mailto:youngseldon77@gmail.com">youngseldon77@gmail.com</a>'
policies = {
    "privacy": ("Privacy notice", [
        ("Operator and scope", f"Credit-Sure is a research demonstration operated by Adarsh-Patel. Contact {contact} for privacy questions or account assistance. It is intended for adults aged 18 or older. Use synthetic assessment details only; do not submit identifiable real applicant or customer financial information."),
        ("Information processed", "Supabase Authentication processes account email, password credentials and session information. Login passwords go directly to Supabase; the Credit-Sure backend does not receive them. We store synthetic assessment identifiers and inputs, model outputs and their model version, your account identifier, creation time, and server-timestamped acceptance of the current research policies."),
        ("Purpose and providers", "We use this information to authenticate accounts, calculate experimental outputs, save private history, prevent abuse and support deletion/export requests. Supabase provides authentication and database hosting; Render is the planned application host. If security checks are enabled, Cloudflare Turnstile processes challenge and technical request information. We do not add advertising or analytics tracking."),
        ("Browser storage and security", "The app stores its login session in this browser tab's session storage and a temporary request fingerprint to prevent duplicate saves. Closing the tab normally ends this local session; sign out explicitly on shared devices. Authentication providers manage their own token lifetimes. Authentication tokens remain accessible to scripts running on this origin, so browser and script security matter. We use access controls and HTTPS in production, but cannot promise absolute security."),
        ("Retention and deletion", "The configured retention job removes saved assessments older than 90 days daily; expired assessments are also hidden by the database read policy. Account and policy acceptance records remain until account deletion. Abuse counters expire automatically; daily assessment counters are cleaned after two days. You can delete individual assessments or your whole account in the workspace. Account deletion requires a recent password sign-in and removes associated assessment, consent and quota records from the live database. Provider backups and operational logs can retain older copies until their configured expiry; deleting a live record does not immediately erase backups."),
        ("Your choices", f"Use the workspace export button to download your account email, saved assessments and recorded policy acceptances. Use account deletion to close your account. Contact {contact} for correction, access, deletion assistance or questions. We may verify identity before acting on requests. Do not email financial information or passwords."),
        ("Location, logs and incidents", "Data is processed in the selected Supabase project region and the application's hosting region, and providers may process technical data elsewhere under their terms. Contact the operator for the configured regions and provider backup/log retention. Application error messages and logs are designed to omit passwords, bearer tokens and full assessment payloads; provider logs may include technical request metadata. If a security incident affects account information, the operator will assess it and communicate as required."),
        ("Policy changes", "This notice describes a research demonstration, not a regulated lending service. Material changes will be published and a new version of the research terms will require acceptance before new assessments. Version: 2026-10-08-research-v1. Last updated: 8 October 2026.")
    ]),
    "terms": ("Terms of use", [
        ("Operator and eligibility", f"Credit-Sure is operated by Adarsh-Patel. Contact {contact}. You must be at least 18 to use an account. These terms cover a personal research demonstration; the service does not offer, arrange, approve or price loans."),
        ("Research use only", "Use synthetic data only. Outputs are experimental estimates, not verified credit scores, validated predictions or guarantees of repayment. Do not use them to make or influence real decisions about lending, employment, insurance, housing or access to essential services."),
        ("Accounts and acceptable use", "Keep your password private and sign out on shared devices. Do not access another account, evade limits, introduce malicious input, attempt to replace model files, disrupt the service or use it for unlawful purposes. We may restrict access to protect the service and its users."),
        ("Saved records and limits", "Your assessments are associated with your account. The research service limits new saves to 100 per UTC day and 500 stored records per account, with additional request limits. Saved assessments expire after 90 days. You can export data, remove individual records or delete your account in the workspace. See the Privacy notice for provider backups and logs."),
        ("Availability and responsibility", "The service is experimental and provided as available. It may be interrupted, changed or withdrawn. You are responsible for using synthetic information and interpreting estimates cautiously. We do not promise that outputs are accurate or suitable for any real-world decision. Nothing in these terms excludes a right or liability that cannot lawfully be excluded."),
        ("Contact and changes", f"For assistance or concerns, contact {contact}. Material policy changes will require renewed acceptance before creating new assessments. Version: 2026-10-08-research-v1. Last updated: 8 October 2026.")
    ])
}
for name, (title, sections) in policies.items():
    page = ROOT / "web" / f"{name}.html"
    html = page.read_text(encoding="utf-8")
    main = f'<main class="wrap document-page legal-page"><p class="eyebrow">RESEARCH DEMONSTRATION</p><h1>{title}</h1><p class="document-lead">Adarsh-Patel · Updated 8 October 2026</p><div class="legal-warning"><strong>Synthetic data only.</strong> This service is an experimental portfolio project and must not be used for real credit decisions.</div>'
    main += "".join(f'<section class="legal-section"><h2>{i}. {heading}</h2><p>{content}</p></section>' for i,(heading,content) in enumerate(sections,1))
    main += '</main>'
    html, count = re.subn(r'<main\b.*?</main>', main, html, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Could not locate main section in {name}")
    html = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{title} for the Credit-Sure synthetic research demonstration, operated by Adarsh-Patel.">', html)
    page.write_text(html, encoding="utf-8")
print("Updated operator, contact, research terms, privacy notice and data lifecycle descriptions.")
