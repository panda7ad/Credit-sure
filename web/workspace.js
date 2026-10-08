const alertRegion = document.getElementById("workspace-alert");
const assessmentForm = document.getElementById("assessment-form");
function showWorkspaceMessage(message, kind = "error") {
  alertRegion.textContent = message;
  alertRegion.className = `workspace-alert ${kind}`;
  alertRegion.hidden = false;
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

assessmentForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (!assessmentForm.reportValidity()) return;
  const button = document.getElementById("assess-button");
  button.disabled = true;
  alertRegion.hidden = true;
  document.getElementById("result-output").hidden = true;
  document.getElementById("result-empty").hidden = false;
  const payload = {};
  for (const field of assessmentForm.elements) {
    if (!field.name) continue;
    if (field.name === "applicant_name") payload[field.name] = field.value.trim();
    else if (field.tagName === "SELECT") payload[field.name] = field.value || null;
    else payload[field.name] = field.value === "" ? null : Number(field.value);
  }
  payload.research_confirmed = document.getElementById("research-confirm").checked;
  try {
    const result = await window.creditSureRequest("/api/predict", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    showAssessment(result, payload.applicant_name);
    showWorkspaceMessage("Estimate generated. Nothing was saved; refreshing clears the result.", "success");
  } catch (error) {
    showWorkspaceMessage(error.retryAfter ? `${error.message} Retry after ${error.retryAfter} seconds.` : error.message);
  } finally { button.disabled = false; }
});
