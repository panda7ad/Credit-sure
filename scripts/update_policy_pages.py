"""Publish the research-only policy text supplied for this project."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
contact = '<a href="mailto:youngseldon77@gmail.com">youngseldon77@gmail.com</a>'
policies = {
 "privacy": ("Privacy notice", [
  ("Operator and scope", f"Credit-Sure is a public research calculator operated by Adarsh-Patel. Contact {contact}. Adults aged 18 or older may explore synthetic scenarios. Do not enter real names or personal financial information."),
  ("Assessment processing", "Inputs are sent over HTTPS to the application server and processed in memory to calculate the estimate. New assessment inputs and outputs are not saved to a database or assessment history. Refreshing the page clears the displayed result. The app does not create accounts or send authentication emails."),
  ("Technical data and providers", "Render hosts the application. A Redis-compatible Render Key Value instance stores salted hashes of network identifiers and short-lived request counters to limit abuse. Counters expire automatically, normally within one hour. Hosting providers may retain IP addresses, timestamps and request metadata in operational logs under their own retention settings. The application is designed not to log assessment bodies. No advertising or analytics tracking is added."),
  ("Browser storage", "The calculator does not save assessment details, results or login sessions in cookies, local storage or session storage. Browser extensions, shared devices and hosting providers are outside this promise. Processing an estimate still involves sending the submitted synthetic inputs to the server."),
  ("Previously created accounts", f"Accounts and records created before this public calculator replaced the account workspace may remain in the former Supabase project and its backups. They are not exposed by the public calculator. Contact {contact} for access or deletion assistance; identity verification may be required. Changing the website does not itself delete old records."),
  ("Contact and changes", f"For privacy questions contact {contact}; do not send passwords or financial details. Last updated: 9 October 2026.")
 ]),
 "terms": ("Terms of use", [
  ("Operator and eligibility", f"This research demonstration is operated by Adarsh-Patel. Contact {contact}. You must be at least 18 to use the calculator. No signup is required."),
  ("Synthetic research only", "Use invented scenario details only. Estimates are experimental, not verified credit scores, loan offers or guarantees. Do not use results to make or influence real lending, employment, insurance, housing or eligibility decisions."),
  ("Use and limits", "Do not evade rate limits, submit malicious inputs or disrupt the service. Shared request budgets and limited model capacity may temporarily prevent estimates. We may restrict access to protect the service."),
  ("No saved history", "Inputs are processed to generate the current estimate and are not saved as assessment records. There are no new accounts, saved histories or database exports. Refreshing clears the displayed estimate. See the Privacy notice for technical logs and previously created accounts."),
  ("Availability", "The service is experimental and provided as available. It may be changed or withdrawn. We do not promise that estimates are accurate or suitable for any real decision. Nothing here excludes rights or liability that cannot lawfully be excluded."),
  ("Contact and changes", f"Contact {contact} for concerns. Last updated: 9 October 2026.")
 ])
}
for name, (title, sections) in policies.items():
    page = ROOT / "web" / f"{name}.html"
    html = page.read_text(encoding="utf-8")
    main = f'<main class="wrap document-page legal-page"><p class="eyebrow">RESEARCH DEMONSTRATION</p><h1>{title}</h1><p class="document-lead">Adarsh-Patel · Updated 9 October 2026</p><div class="legal-warning"><strong>Synthetic data only.</strong> This service is an experimental portfolio project and must not be used for real credit decisions.</div>'
    main += "".join(f'<section class="legal-section"><h2>{i}. {heading}</h2><p>{content}</p></section>' for i,(heading,content) in enumerate(sections,1))
    main += '</main>'
    html, count = re.subn(r'<main\b.*?</main>', main, html, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Could not locate main section in {name}")
    html = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{title} for the Credit-Sure synthetic research demonstration, operated by Adarsh-Patel.">', html)
    page.write_text(html, encoding="utf-8")
print("Updated operator, contact, research terms, privacy notice and data lifecycle descriptions.")
