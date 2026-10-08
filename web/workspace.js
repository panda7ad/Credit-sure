const alertRegion = document.getElementById("workspace-alert");
const assessmentForm = document.getElementById("assessment-form");
let authClient;
let appConfig;

function showWorkspaceMessage(message, kind = "error") {
  alertRegion.textContent = message;
  alertRegion.className = `workspace-alert ${kind}`;
  alertRegion.hidden = false;
}

function addTableCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.append(cell);
  return cell;
}

function formatAssessmentDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

async function authenticatedFetch(url, options = {}) {
  const { data, error } = await authClient.auth.getSession();
  if (error) throw error;
  if (!data.session) {
    window.location.assign("/signin");
    throw new Error("Your session has ended. Sign in again to continue.");
  }
  return window.creditSureRequest(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${data.session.access_token}`
    }
  });
}

function showAssessment(result, applicantName) {
  document.getElementById("result-empty").hidden = true;
  document.getElementById("result-output").hidden = false;
  document.getElementById("result-name").textContent = applicantName;
  const bandCopy = {
    LOW: "Lower estimate",
    MEDIUM: "For further research review",
    HIGH: "Higher estimate"
  };
  document.getElementById("result-decision").textContent = bandCopy[result.risk_band] || "Research estimate";
  document.getElementById("result-score").textContent = result.credit_score;
  document.getElementById("result-probability").textContent =
    `${(result.default_probability * 100).toFixed(1)}%`;
  document.getElementById("result-band").textContent = result.risk_band;
  const factors = document.getElementById("result-factors");
  factors.replaceChildren();
  for (const factor of result.key_factors || []) {
    const item = document.createElement("li");
    item.textContent = factor;
    factors.append(item);
  }
}

async function loadHistory() {
  const rows = document.getElementById("history-rows");
  const date = document.getElementById("history-date").value;
  const query = new URLSearchParams();
  if (date) query.set("assessed_on", date);
  try {
    const records = await authenticatedFetch(`/api/history?${query}`);
    rows.replaceChildren();
    if (records.length === 0) {
      const row = document.createElement("tr");
      const cell = addTableCell(row, date ? "No assessments on this date." : "No saved assessments yet.");
      cell.colSpan = 5;
      cell.className = "empty-row";
      rows.append(row);
      return;
    }
    for (const record of records) {
      const row = document.createElement("tr");
      addTableCell(row, record.applicant_name);
      addTableCell(row, formatAssessmentDate(record.created_at));
      addTableCell(row, record.model_version ? String(record.result?.credit_score ?? "Unavailable") : "Unverified legacy record");
      const risk = record.model_version && ["LOW", "MEDIUM", "HIGH"].includes(record.result?.risk_band) ? record.result.risk_band : "UNKNOWN";
      const band = addTableCell(row, risk);
      band.className = `risk-cell ${risk.toLowerCase()}`;
      const actions = addTableCell(row, "");
      actions.className = "history-actions";
      const loadButton = document.createElement("button");
      loadButton.className = "row-action";
      loadButton.type = "button";
      loadButton.textContent = "Open";
      loadButton.addEventListener("click", () => openAssessment(record.id, loadButton));
      const deleteButton = document.createElement("button");
      deleteButton.className = "row-action delete-action";
      deleteButton.type = "button";
      deleteButton.textContent = "Delete";
      deleteButton.setAttribute("aria-label", `Delete assessment for ${record.applicant_name}`);
      deleteButton.addEventListener("click", () => removeAssessment(record.id, deleteButton));
      actions.append(loadButton, deleteButton);
      rows.append(row);
    }
  } catch (error) {
    showWorkspaceMessage(error.message);
  }
}

async function openAssessment(id, button) {
  button.disabled = true;
  try {
    const record = await authenticatedFetch(`/api/history/${id}`);
    for (const [name, value] of Object.entries(record.payload)) {
      const input = assessmentForm.elements.namedItem(name);
      if (input) input.value = value ?? "";
    }
    document.getElementById("research-confirm").checked = false;
    if (record.model_version) showAssessment(record.result, record.applicant_name);
    else showWorkspaceMessage("This legacy record predates protected saves. Its output is unverified; generate a new estimate using synthetic details.");
    assessmentForm.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showWorkspaceMessage(error.message);
  } finally {
    button.disabled = false;
  }
}

async function removeAssessment(id, button) {
  if (!window.confirm("Delete this saved assessment? This cannot be undone.")) return;
  button.disabled = true;
  try {
    await authenticatedFetch(`/api/history/${id}`, { method: "DELETE" });
    await loadHistory();
    showWorkspaceMessage("Assessment deleted.", "success");
  } catch (error) {
    showWorkspaceMessage(error.message);
    button.disabled = false;
  }
}

assessmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!assessmentForm.reportValidity()) return;
  const button = document.getElementById("assess-button");
  button.disabled = true;
  alertRegion.hidden = true;
  const payload = {};
  for (const field of assessmentForm.elements) {
    if (!field.name) continue;
    if (field.name === "applicant_name") payload[field.name] = field.value.trim();
    else if (field.tagName === "SELECT") payload[field.name] = field.value || null;
    else payload[field.name] = field.value === "" ? null : Number(field.value);
  }
  try {
    payload.research_confirmed = document.getElementById("research-confirm").checked;
    const serialized = JSON.stringify(payload);
    const hashBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(serialized));
    const fingerprint = Array.from(new Uint8Array(hashBytes), b => b.toString(16).padStart(2, "0")).join("");
    const { data } = await authClient.auth.getSession();
    const owner = data.session.user.id;
    let stored;
    try { stored = JSON.parse(sessionStorage.getItem("creditsure-pending")); } catch { stored = null; }
    if (!stored || stored.fingerprint !== fingerprint || stored.owner !== owner) {
      stored = { fingerprint, owner, key: crypto.randomUUID() };
      sessionStorage.setItem("creditsure-pending", JSON.stringify(stored));
    }
    const result = await authenticatedFetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": stored.key },
      body: serialized
    });
    sessionStorage.removeItem("creditsure-pending");
    showAssessment(result, payload.applicant_name);
    await loadHistory();
    showWorkspaceMessage("Research estimate saved to your private history.", "success");
  } catch (error) {
    showWorkspaceMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

document.getElementById("history-date").addEventListener("change", loadHistory);
document.getElementById("sign-out").addEventListener("click", async () => {
  try {
    const { error } = await authClient.auth.signOut({ scope: "global" });
    if (error) throw error;
    sessionStorage.removeItem("creditsure-pending");
    window.location.assign("/");
  } catch { showWorkspaceMessage("Sign-out could not be completed. Check your connection and try again."); }
});

document.getElementById("policy-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!event.target.reportValidity()) return;
  const button = document.getElementById("policy-submit"); button.disabled = true;
  try {
    await authenticatedFetch("/api/account/consent", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policy_version: appConfig.policy_version, accepted: true }) });
    document.getElementById("policy-panel").hidden = true;
    document.getElementById("assess-button").disabled = false;
  } catch (error) { showWorkspaceMessage(error.message); }
  finally { button.disabled = false; }
});

document.getElementById("export-account").addEventListener("click", async event => {
  const button = event.currentTarget; button.disabled = true;
  try {
    const data = await authenticatedFetch("/api/account/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "credit-sure-export.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { showWorkspaceMessage(error.message); }
  finally { button.disabled = false; }
});

document.getElementById("delete-account").addEventListener("click", async event => {
  if (!confirm("Delete your account and saved assessments permanently? Export first if you want a copy.")) return;
  const button = event.currentTarget; button.disabled = true;
  try {
    await authenticatedFetch("/api/account", { method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation: "DELETE MY ACCOUNT" }) });
    await authClient.auth.signOut({ scope: "local" });
    sessionStorage.removeItem("creditsure-auth"); sessionStorage.removeItem("creditsure-pending"); location.assign("/");
  } catch (error) { showWorkspaceMessage(error.message); }
  finally { button.disabled = false; }
});

window.creditSureReady.then(async (setup) => {
  if (!setup) {
    showWorkspaceMessage("Supabase is not configured yet. The site owner must complete the setup before accounts can be used.");
    return;
  }
  authClient = setup.client;
  appConfig = setup.config;
  const { data, error } = await authClient.auth.getSession();
  if (error) throw error;
  if (!data.session) {
    window.location.replace("/signin");
    return;
  }
  document.getElementById("account-email").textContent = data.session.user.email || "Signed in";
  document.getElementById("account-email").hidden = false;
  document.getElementById("sign-out").hidden = false;
  document.getElementById("workspace-content").hidden = false;
  document.getElementById("history").hidden = false;
  document.getElementById("account-controls").hidden = false;
  const account = await authenticatedFetch("/api/account");
  document.getElementById("policy-panel").hidden = account.accepted;
  document.getElementById("assess-button").disabled = !account.accepted;
  await loadHistory();
}).catch((error) => showWorkspaceMessage(error.message));
