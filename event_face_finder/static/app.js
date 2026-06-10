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
const paginationEl = document.querySelector("#sheets-pagination");
const lightboxEl = document.querySelector("#lightbox");
const lightboxImageEl = document.querySelector("#lightbox-image");
const lightboxCloseEl = document.querySelector("#lightbox-close");
const progressBarEl = document.querySelector("#progress-bar");
const progressLabelEl = document.querySelector("#progress-label");
let hiddenLogLineCount = 0;
let lastStatus = "idle";
let lastStatusErrorShown = 0;
const STATUS_ERROR_THROTTLE_MS = 10000;
const SHEETS_PER_PAGE = 4;
let currentSheetList = [];
let currentSheetPage = 0;

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

let lastAutoReferenceDir = "";

function defaultReferenceDir({ force = false } = {}) {
  const value = personIdEl.value.trim();
  if (!value) {
    return;
  }
  if (!force && referenceDirEl.value.trim() && referenceDirEl.value.trim() !== lastAutoReferenceDir) {
    return;
  }
  const next = `reference_people/${value}`;
  referenceDirEl.value = next;
  lastAutoReferenceDir = next;
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
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    status = await response.json();
  } catch (error) {
    const now = Date.now();
    if (now - lastStatusErrorShown > STATUS_ERROR_THROTTLE_MS) {
      lastStatusErrorShown = now;
      showFormMessage("Lost connection to the local GUI server.", "error");
    }
    console.warn("refreshStatus failed:", error);
    return;
  }

  const isRunning = status.status === "running" || status.status === "stopping";
  const wasRunning = lastStatus === "running" || lastStatus === "stopping";
  statusEl.textContent = capitalize(status.status);
  statusEl.dataset.status = status.status;
  statusNoteEl.textContent = status.command.length ? formatCommandNote(status.command) : "";
  returnCodeEl.textContent =
    status.returncode === null || status.returncode === undefined
      ? ""
      : `exit ${status.returncode}`;
  renderLog(status.lines);
  renderProgress(status.progress, status.status);
  startButton.disabled = isRunning;
  stopButton.disabled = !isRunning;

  if (isRunning || (wasRunning && (status.status === "completed" || status.status === "failed"))) {
    await refreshResults();
  }
  lastStatus = status.status;
}

function renderProgress(progress, scanStatus) {
  if (!progressBarEl || !progressLabelEl) {
    return;
  }
  const total = progress?.total || 0;
  const done = progress?.done || 0;
  if (total > 0 && (scanStatus === "running" || scanStatus === "stopping")) {
    const pct = Math.min(100, Math.round((done / total) * 100));
    progressBarEl.value = pct;
    progressBarEl.max = 100;
    progressBarEl.hidden = false;
    progressLabelEl.hidden = false;
    progressLabelEl.textContent = `${done.toLocaleString()} / ${total.toLocaleString()} images (${pct}%)`;
  } else {
    progressBarEl.hidden = true;
    progressLabelEl.hidden = true;
    progressBarEl.value = 0;
  }
}

async function refreshResults() {
  const personId = personIdEl.value.trim();
  const workspace = workspaceEl.value.trim() || "outputs";
  if (!personId) {
    renderEmptyResults();
    return;
  }

  let response;
  try {
    response = await fetch(
      `/api/results?person_id=${encodeURIComponent(personId)}&workspace=${encodeURIComponent(
        workspace,
      )}`,
    );
  } catch (error) {
    showFormMessage("Unable to reach the local GUI server.", "error");
    return;
  }
  if (!response.ok) {
    showFormMessage(`Results request failed (HTTP ${response.status}).`, "error");
    return;
  }
  const results = await response.json();
  renderResults(results);
}

function renderResults(results) {
  const summary = results.summary;
  highCountEl.textContent = summary.high;
  reviewCountEl.textContent = summary.review;
  totalCountEl.textContent = summary.total;

  if (!results.exists) {
    pathsEl.innerHTML = "";
    sheetsEl.innerHTML =
      '<div class="empty-state">No results yet. Run a scan to populate this panel.</div>';
    paginationEl.hidden = true;
    return;
  }

  pathsEl.innerHTML = [
    pathRow("High matches", summary.high_dir, summary.high),
    pathRow("Review matches", summary.review_dir, summary.review),
    pathRow("Contact sheets", summary.contact_sheets_dir),
    pathRow("CSV", summary.csv_path),
  ].join("");

  currentSheetList = summary.contact_sheets || [];
  currentSheetPage = 0;
  if (!currentSheetList.length) {
    sheetsEl.innerHTML = '<div class="empty-state">No contact sheets found for this run.</div>';
    paginationEl.hidden = true;
    return;
  }
  renderSheetPage();
}

function renderSheetPage() {
  const totalPages = Math.max(1, Math.ceil(currentSheetList.length / SHEETS_PER_PAGE));
  if (currentSheetPage >= totalPages) {
    currentSheetPage = totalPages - 1;
  }
  const start = currentSheetPage * SHEETS_PER_PAGE;
  const slice = currentSheetList.slice(start, start + SHEETS_PER_PAGE);

  sheetsEl.innerHTML = slice
    .map(
      (filename) =>
        `<figure class="sheet">
          <button class="sheet-button" type="button" data-sheet="${escapeHtml(filename)}"
            aria-label="Open ${escapeHtml(filename)} at full size">
            <img alt="${escapeHtml(filename)}" src="${contactSheetUrl(filename)}" loading="lazy" />
          </button>
          <figcaption>${escapeHtml(filename)}</figcaption>
        </figure>`,
    )
    .join("");

  if (totalPages <= 1) {
    paginationEl.hidden = true;
    paginationEl.innerHTML = "";
    return;
  }
  paginationEl.hidden = false;
  paginationEl.innerHTML = `
    <button class="ghost" type="button" id="sheets-prev" ${currentSheetPage === 0 ? "disabled" : ""}>
      Previous
    </button>
    <span class="muted">Page ${currentSheetPage + 1} of ${totalPages}</span>
    <button class="ghost" type="button" id="sheets-next" ${
      currentSheetPage >= totalPages - 1 ? "disabled" : ""
    }>
      Next
    </button>
  `;
  const prev = document.querySelector("#sheets-prev");
  const next = document.querySelector("#sheets-next");
  if (prev) {
    prev.addEventListener("click", () => {
      if (currentSheetPage > 0) {
        currentSheetPage -= 1;
        renderSheetPage();
      }
    });
  }
  if (next) {
    next.addEventListener("click", () => {
      if (currentSheetPage < totalPages - 1) {
        currentSheetPage += 1;
        renderSheetPage();
      }
    });
  }
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
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    knownPeopleEl.innerHTML = (payload.people || [])
      .map((person) => `<option value="${escapeHtml(person)}"></option>`)
      .join("");
  } catch (error) {
    knownPeopleEl.innerHTML = "";
    console.warn("Could not load known people list:", error);
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

function pathRow(label, value, count) {
  const target = value || "-";
  const openButton =
    value && value !== "-"
      ? `<button class="ghost path-open" type="button" data-open="${escapeHtml(value)}"
          aria-label="Open ${escapeHtml(label)} folder">Open</button>`
      : "";
  const countLabel =
    typeof count === "number" && count > 0
      ? `<span class="path-count">${count}</span>`
      : "";
  return `
    <div class="path-row">
      <span>${escapeHtml(label)}${countLabel}</span>
      <div class="path-line">
        <code>${escapeHtml(target)}</code>
        ${openButton}
      </div>
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

function formatCommandNote(command) {
  if (!Array.isArray(command) || !command.length) {
    return "";
  }
  const subcommandIndex = command.findIndex((arg) => arg === "run-person");
  const after = subcommandIndex >= 0 ? command.slice(subcommandIndex + 1) : [];
  const parts = [];
  for (let i = 0; i < after.length; i += 2) {
    const flag = after[i];
    const value = after[i + 1];
    if (flag && value !== undefined && value !== "") {
      parts.push(`${flag.replace(/^--/, "")} ${value}`);
    }
  }
  return parts.join("  ·  ");
}

function tauriDialog() {
  return window.__TAURI__?.dialog;
}

async function chooseDirectory({ multiple = false } = {}) {
  const dialog = tauriDialog();
  if (!dialog?.open) {
    showFormMessage(
      "Folder picker is only available in the desktop app. Type the path manually here.",
      "error",
    );
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
  defaultReferenceDir();
  refreshResults();
});

document
  .querySelectorAll("[data-picker]")
  .forEach((button) => button.addEventListener("click", handleDirectoryPicker));

function validateFormPayload() {
  const fields = formPayload();
  for (const el of [personIdEl, referenceDirEl, photosRootsEl]) {
    el.removeAttribute("aria-invalid");
  }
  if (!fields.person_id) {
    personIdEl.setAttribute("aria-invalid", "true");
    return "Person ID is required.";
  }
  if (!/^[A-Za-z0-9._-]+$/.test(fields.person_id)) {
    personIdEl.setAttribute("aria-invalid", "true");
    return "Person ID can only contain letters, numbers, dots, underscores, and hyphens.";
  }
  if (!fields.reference_dir) {
    referenceDirEl.setAttribute("aria-invalid", "true");
    return "Reference folder is required.";
  }
  if (!fields.photos_roots.trim()) {
    photosRootsEl.setAttribute("aria-invalid", "true");
    return "At least one photo folder is required.";
  }
  const high = Number(fields.high_threshold);
  const review = Number(fields.review_threshold);
  if (Number.isNaN(high) || Number.isNaN(review)) {
    return "Thresholds must be numbers.";
  }
  if (high < 0 || high > 1 || review < 0 || review > 1) {
    return "Thresholds must be between 0 and 1.";
  }
  if (review > high) {
    return "Review threshold must be less than or equal to High threshold.";
  }
  return null;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  defaultReferenceDir();
  const validationError = validateFormPayload();
  if (validationError) {
    showFormMessage(validationError, "error");
    return;
  }
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
  } finally {
    if (lastStatus !== "running" && lastStatus !== "stopping") {
      startButton.disabled = false;
    }
  }
});

stopButton.addEventListener("click", async () => {
  if (stopButton.disabled) {
    return;
  }
  stopButton.disabled = true;
  statusEl.textContent = "Stopping…";
  statusEl.dataset.status = "stopping";
  try {
    await postJson("/api/stop");
  } catch (error) {
    showFormMessage(error.message || "Unable to stop scan.", "error");
  }
  await refreshStatus();
});

refreshButton.addEventListener("click", refreshStatus);
clearLogButton.addEventListener("click", () => {
  const current = logEl.textContent;
  if (current) {
    const lines = current.split("\n");
    const trailing = lines.length > 0 && lines[lines.length - 1] === "" ? 1 : 0;
    hiddenLogLineCount += lines.length - trailing;
  }
  logEl.textContent = "";
});

sheetsEl.addEventListener("click", (event) => {
  const target = event.target.closest("[data-sheet]");
  if (!target) {
    return;
  }
  openLightbox(target.dataset.sheet);
});

pathsEl.addEventListener("click", (event) => {
  const target = event.target.closest("[data-open]");
  if (!target) {
    return;
  }
  openPath(target.dataset.open);
});

function openLightbox(filename) {
  if (!filename) {
    return;
  }
  lightboxImageEl.alt = filename;
  lightboxImageEl.classList.remove("lightbox-image-error");
  lightboxImageEl.src = contactSheetUrl(filename);
  lightboxEl.hidden = false;
  document.body.classList.add("lightbox-open");
}

lightboxImageEl.addEventListener("error", () => {
  lightboxImageEl.classList.add("lightbox-image-error");
  lightboxImageEl.alt = "Could not load contact sheet";
});

function closeLightbox() {
  lightboxEl.hidden = true;
  lightboxImageEl.src = "";
  lightboxImageEl.alt = "";
  document.body.classList.remove("lightbox-open");
}

lightboxCloseEl.addEventListener("click", closeLightbox);
lightboxEl.addEventListener("click", (event) => {
  if (event.target === lightboxEl) {
    closeLightbox();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !lightboxEl.hidden) {
    closeLightbox();
  }
});

async function openPath(path) {
  if (!path) {
    return;
  }
  try {
    await postJson("/api/open", { path });
  } catch (error) {
    showFormMessage(error.message || "Unable to open path.", "error");
  }
}

renderEmptyResults();
stopButton.disabled = true;
loadKnownPeople();
refreshStatus();

let pollHandle = setInterval(refreshStatus, 1500);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearInterval(pollHandle);
    pollHandle = 0;
  } else if (!pollHandle) {
    refreshStatus();
    pollHandle = setInterval(refreshStatus, 1500);
  }
});
