const form = document.querySelector("#scan-form");
const startButton = document.querySelector("#start-button");
const stopButton = document.querySelector("#stop-button");
const refreshButton = document.querySelector("#refresh-results");
const clearLogButton = document.querySelector("#clear-log");
const statusEl = document.querySelector("#status");
const statusNoteEl = document.querySelector("#status-note");
const highCountEl = document.querySelector("#high-count");
const reviewCountEl = document.querySelector("#review-count");
const totalCountEl = document.querySelector("#total-count");
const logEl = document.querySelector("#log");
const returnCodeEl = document.querySelector("#return-code");
const pathsEl = document.querySelector("#paths");
const sheetsEl = document.querySelector("#contact-sheets");
const personIdEl = document.querySelector("#person-id");
const referenceDirEl = document.querySelector("#reference-dir");
const formMessageEl = document.querySelector("#form-message");
const knownPeopleEl = document.querySelector("#known-people");

function formPayload() {
  return {
    person_id: document.querySelector("#person-id").value.trim(),
    reference_dir: document.querySelector("#reference-dir").value.trim(),
    photos_roots: document.querySelector("#photos-roots").value,
    workspace: document.querySelector("#workspace").value.trim() || "outputs",
    cache_path: document.querySelector("#cache-path").value.trim(),
    high_threshold: document.querySelector("#high-threshold").value,
    review_threshold: document.querySelector("#review-threshold").value,
    max_image_size: document.querySelector("#max-image-size").value,
    chunk_size: document.querySelector("#chunk-size").value,
    provider: document.querySelector("#provider").value,
    export_mode: document.querySelector("#export-mode").value,
  };
}

function defaultReferenceDir() {
  const value = personIdEl.value.trim();
  if (!value || referenceDirEl.value.trim()) {
    return;
  }
  referenceDirEl.value = `reference_people/${value}`;
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function refreshStatus() {
  const response = await fetch("/api/status");
  const status = await response.json();
  const isRunning = status.status === "running" || status.status === "stopping";
  statusEl.textContent = capitalize(status.status);
  statusEl.dataset.status = status.status;
  statusNoteEl.textContent = status.command.length ? status.command.slice(0, 4).join(" ") : "";
  returnCodeEl.textContent =
    status.returncode === null || status.returncode === undefined
      ? ""
      : `exit ${status.returncode}`;
  logEl.textContent = status.lines.join("\n");
  logEl.scrollTop = logEl.scrollHeight;
  startButton.disabled = isRunning;
  stopButton.disabled = !isRunning;

  if (status.status === "completed" || status.status === "failed") {
    await refreshResults();
  }
}

async function refreshResults() {
  const personId = personIdEl.value.trim();
  const workspace = document.querySelector("#workspace").value.trim() || "outputs";
  if (!personId) {
    renderEmptyResults();
    return;
  }

  const response = await fetch(
    `/api/results?person_id=${encodeURIComponent(personId)}&workspace=${encodeURIComponent(
      workspace,
    )}`,
  );
  const results = await response.json();
  renderResults(results);
}

function renderResults(results) {
  const summary = results.summary;
  highCountEl.textContent = summary.high;
  reviewCountEl.textContent = summary.review;
  totalCountEl.textContent = summary.total;

  if (!results.exists) {
    renderEmptyResults(false);
    return;
  }

  pathsEl.innerHTML = [
    pathRow("High matches", summary.high_dir),
    pathRow("Review matches", summary.review_dir),
    pathRow("Contact sheets", summary.contact_sheets_dir),
    pathRow("CSV", summary.csv_path),
  ].join("");

  if (!summary.contact_sheets.length) {
    sheetsEl.innerHTML = '<div class="empty-state">No contact sheets found for this run.</div>';
    return;
  }

  sheetsEl.innerHTML = summary.contact_sheets
    .map(
      (filename) =>
        `<img alt="Contact sheet" src="/api/contact-sheet?person_id=${encodeURIComponent(
          personIdEl.value.trim(),
        )}&workspace=${encodeURIComponent(
          document.querySelector("#workspace").value.trim() || "outputs",
        )}&filename=${encodeURIComponent(filename)}" />`,
    )
    .join("");
}

function renderEmptyResults(resetCounts = true) {
  if (resetCounts) {
    highCountEl.textContent = "0";
    reviewCountEl.textContent = "0";
    totalCountEl.textContent = "0";
  }
  pathsEl.innerHTML = "";
  sheetsEl.innerHTML = '<div class="empty-state">No results loaded.</div>';
}

async function loadKnownPeople() {
  const response = await fetch("/api/reference-people");
  const payload = await response.json();
  knownPeopleEl.innerHTML = payload.people
    .map((person) => `<option value="${escapeHtml(person)}"></option>`)
    .join("");
}

function showFormMessage(message, type = "info") {
  formMessageEl.textContent = message;
  formMessageEl.dataset.type = type;
  formMessageEl.hidden = !message;
}

function pathRow(label, value) {
  return `
    <div class="path-row">
      <span>${escapeHtml(label)}</span>
      <code>${escapeHtml(value || "-")}</code>
    </div>
  `;
}

function capitalize(value) {
  if (!value) {
    return "Idle";
  }
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

personIdEl.addEventListener("blur", defaultReferenceDir);
personIdEl.addEventListener("change", () => {
  referenceDirEl.value = "";
  defaultReferenceDir();
  refreshResults();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  defaultReferenceDir();
  showFormMessage("");
  startButton.disabled = true;
  const result = await postJson("/api/start", formPayload());
  if (!result.ok) {
    showFormMessage(result.error || "Unable to start scan.", "error");
    startButton.disabled = false;
    return;
  }
  showFormMessage("Scan started.", "success");
  await refreshStatus();
});

stopButton.addEventListener("click", async () => {
  await postJson("/api/stop");
  await refreshStatus();
});

refreshButton.addEventListener("click", refreshResults);
clearLogButton.addEventListener("click", () => {
  logEl.textContent = "";
});

renderEmptyResults();
stopButton.disabled = true;
loadKnownPeople();
setInterval(refreshStatus, 1500);
refreshStatus();
