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
const photosRootsEl = document.querySelector("#photos-roots");
const workspaceEl = document.querySelector("#workspace");
const formMessageEl = document.querySelector("#form-message");
const knownPeopleEl = document.querySelector("#known-people");
let hiddenLogLineCount = 0;
let lastStatus = "idle";

function formPayload() {
  return {
    person_id: document.querySelector("#person-id").value.trim(),
    reference_dir: referenceDirEl.value.trim(),
    photos_roots: photosRootsEl.value,
    workspace: workspaceEl.value.trim() || "outputs",
    cache_path: document.querySelector("#cache-path").value.trim(),
    high_threshold: document.querySelector("#high-threshold").value,
    review_threshold: document.querySelector("#review-threshold").value,
    max_image_size: document.querySelector("#max-image-size").value,
    chunk_size: document.querySelector("#chunk-size").value,
    min_reference_faces: document.querySelector("#min-reference-faces").value,
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
  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      throw new Error(`Unexpected response from the local GUI server (${response.status}).`);
    }
  }
  if (!response.ok && !body.error) {
    throw new Error(`Request failed with status ${response.status}.`);
  }
  return body;
}

async function refreshStatus() {
  let status;
  try {
    const response = await fetch("/api/status");
    status = await response.json();
  } catch {
    showFormMessage("Unable to reach the local GUI server.", "error");
    return;
  }

  const isRunning = status.status === "running" || status.status === "stopping";
  const wasRunning = lastStatus === "running" || lastStatus === "stopping";
  statusEl.textContent = capitalize(status.status);
  statusEl.dataset.status = status.status;
  statusNoteEl.textContent = status.command.length ? status.command.slice(0, 4).join(" ") : "";
  returnCodeEl.textContent =
    status.returncode === null || status.returncode === undefined
      ? ""
      : `exit ${status.returncode}`;
  renderLog(status.lines);
  startButton.disabled = isRunning;
  stopButton.disabled = !isRunning;

  if (isRunning || (wasRunning && (status.status === "completed" || status.status === "failed"))) {
    await refreshResults();
  }
  lastStatus = status.status;
}

async function refreshResults() {
  const personId = personIdEl.value.trim();
  const workspace = workspaceEl.value.trim() || "outputs";
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
        `<figure class="sheet">
          <img alt="Contact sheet ${escapeHtml(filename)}" src="${contactSheetUrl(filename)}" />
          <figcaption>${escapeHtml(filename)}</figcaption>
        </figure>`,
    )
    .join("");
}

function contactSheetUrl(filename) {
  const personId = personIdEl.value.trim();
  const workspace = workspaceEl.value.trim() || "outputs";
  return `/api/contact-sheet?person_id=${encodeURIComponent(
    personId,
  )}&workspace=${encodeURIComponent(workspace)}&filename=${encodeURIComponent(filename)}`;
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
  try {
    const response = await fetch("/api/reference-people");
    const payload = await response.json();
    knownPeopleEl.innerHTML = payload.people
      .map((person) => `<option value="${escapeHtml(person)}"></option>`)
      .join("");
  } catch {
    knownPeopleEl.innerHTML = "";
  }
}

function showFormMessage(message, type = "info") {
  formMessageEl.textContent = message;
  formMessageEl.dataset.type = type;
  formMessageEl.hidden = !message;
}

function renderLog(lines) {
  const visibleLines = lines.slice(hiddenLogLineCount);
  const distanceFromBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight;
  const shouldStickToBottom = distanceFromBottom < 24 || !logEl.textContent;
  logEl.textContent = visibleLines.join("\n");
  if (shouldStickToBottom) {
    logEl.scrollTop = logEl.scrollHeight;
  }
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

function tauriDialog() {
  return window.__TAURI__?.dialog;
}

async function chooseDirectory({ multiple = false } = {}) {
  const dialog = tauriDialog();
  if (!dialog?.open) {
    showFormMessage("Folder picker is available in the desktop app.", "info");
    return null;
  }

  const result = await dialog.open({
    directory: true,
    multiple,
    title: multiple ? "Choose photo folders" : "Choose folder",
  });
  if (!result) {
    return null;
  }
  return Array.isArray(result) ? result : [result];
}

async function handleDirectoryPicker(event) {
  const target = event.currentTarget.dataset.picker;
  try {
    if (target === "reference-dir") {
      const paths = await chooseDirectory();
      if (paths?.length) {
        referenceDirEl.value = paths[0];
      }
    } else if (target === "photos-roots") {
      const paths = await chooseDirectory({ multiple: true });
      if (paths?.length) {
        const existing = photosRootsEl.value
          .split("\n")
          .map((value) => value.trim())
          .filter(Boolean);
        photosRootsEl.value = [...new Set([...existing, ...paths])].join("\n");
      }
    } else if (target === "workspace") {
      const paths = await chooseDirectory();
      if (paths?.length) {
        workspaceEl.value = paths[0];
      }
    }
  } catch (error) {
    showFormMessage(error.message || "Unable to open folder picker.", "error");
  }
}

personIdEl.addEventListener("blur", defaultReferenceDir);
personIdEl.addEventListener("change", () => {
  referenceDirEl.value = "";
  defaultReferenceDir();
  refreshResults();
});

document
  .querySelectorAll("[data-picker]")
  .forEach((button) => button.addEventListener("click", handleDirectoryPicker));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  defaultReferenceDir();
  showFormMessage("");
  startButton.disabled = true;
  try {
    const result = await postJson("/api/start", formPayload());
    if (!result.ok) {
      showFormMessage(result.error || "Unable to start scan.", "error");
      startButton.disabled = false;
      return;
    }
    hiddenLogLineCount = 0;
    lastStatus = "idle";
    logEl.textContent = "";
    showFormMessage("Scan started.", "success");
    await refreshStatus();
  } catch (error) {
    showFormMessage(error.message || "Unable to start scan.", "error");
    startButton.disabled = false;
  }
});

stopButton.addEventListener("click", async () => {
  await postJson("/api/stop");
  await refreshStatus();
});

refreshButton.addEventListener("click", refreshResults);
clearLogButton.addEventListener("click", () => {
  hiddenLogLineCount += logEl.textContent ? logEl.textContent.split("\n").length : 0;
  logEl.textContent = "";
});

renderEmptyResults();
stopButton.disabled = true;
loadKnownPeople();
setInterval(refreshStatus, 1500);
refreshStatus();
