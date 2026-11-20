// ==========================================================
// ArchitectOS Workspace Client — PROJECT_WORKSPACE_UI_06
//
// Project-based workspace: home screen, three-column layout,
// chat, asset gallery, details, mode / quality / seed controls,
// truthful persistence + render status.
//
// All calls are same-origin and go through the UI proxy, which in
// turn uses the Core API URL from runtime_config.
// ==========================================================


// CODER-05.2 — the launcher places a one-shot bootstrap secret in the URL
// fragment. Fragments are not sent in HTTP requests or access logs. Exchange
// it for an HttpOnly/SameSite signed session, then erase it from browser
// history. Approval capabilities themselves remain in the UI server process.
(async function bootstrapTrustedLocalSession() {
  const prefix = "#local-bootstrap=";
  if (!window.location.hash.startsWith(prefix)) return;
  const token = decodeURIComponent(window.location.hash.slice(prefix.length));
  history.replaceState(null, "", window.location.pathname + window.location.search);
  try {
    await fetch("/api/local-session/bootstrap", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
  } catch (_error) {
    // Fail closed: ordinary UI features remain available, coder writes do not.
  }
})();


const state = {
  view: "home",
  projectId: null,
  project: null,
  projects: { recent: [], archived: [] },
  assets: [],
  galleryFilter: "all",
  selectedAssetId: null,
  activeAssetId: null,
  modes: null,
  attachFile: null,
  // FACADE-02 — ordered A/B attachments. Index 0 = IMAGE A
  // (facade style reference), index 1 = IMAGE B (target building /
  // geometry authority). `attachFile` mirrors the first entry so all
  // existing single-image behaviour is preserved unchanged.
  attachFiles: [],
  polling: null,
  // IMAGE_TURN_TRANSPORT_RECOVERY_01 — the stored message count as the
  // server last reported it, so a turn whose HTTP response was lost can
  // be recovered from the project instead of being dropped.
  messageCount: null,
  lastAssistantText: null,
  // ARCHITECTURAL_LEARNING_UI_01 — UI-ONLY interaction state.
  // `uiState` is derived on the client (mode + attachment + teaching +
  // in-flight turn); `turn` holds the AbortController so Stop/Cancel can
  // halt an in-flight request; `lastSent` backs Retry.
  uiState: "CHAT",
  teaching: false,
  turn: null,
  lastSent: null,
};


// ==========================================================
// SMALL HELPERS
// ==========================================================

function $(id) { return document.getElementById(id); }

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

function timeAgo(seconds) {
  if (!seconds) return "—";
  const diff = Math.max(0, Date.now() / 1000 - seconds);
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

function clock(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const m = String(Math.floor(total / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return m + ":" + s;
}

function toast(message, ms) {
  const node = $("toast");
  node.textContent = message;
  node.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => node.classList.add("hidden"), ms || 2600);
}


// ==========================================================
// OPERATION_VISIBILITY_UI_01 — CENTRALIZED ACTIVITY ENGINE
//
// ONE place that knows what ArchitectOS is currently doing. Every
// long-running operation calls begin()/update()/finish()/fail() and
// the single header pill renders the truth. It never writes to the
// chat transcript, and it never fabricates completion: `finish()` is
// only called when the real promise settles.
//
// The engine is intentionally tiny. It is NOT a job queue: the UI
// only ever runs one foreground user operation at a time (a single
// `state.turn`, a single recorder, a single upload), so a small
// primary/secondary stack is enough and no speculative concurrency
// is added.
// ----------------------------------------------------------

const ACTIVITY_LABELS = {
  voice_upload:  "در حال ارسال صدا…",
  stt:           "در حال تشخیص گفتار…",
  chat:          "در حال تحلیل درخواست…",
  response:      "در حال پردازش پاسخ…",
  tts:           "در حال ساخت صدا…",
  file_upload:   "در حال آپلود فایل…",
  file_process:  "در حال پردازش فایل…",
  render:        "در حال رندر…",
  image:         "در حال پردازش تصویر…",
  save:          "در حال ذخیره اطلاعات…",
  assets:        "در حال بروزرسانی فایل‌ها…",
  project:       "در حال پردازش پروژه…",
};

const ACTIVITY_DONE_LABEL = "انجام شد";
const ACTIVITY_FAIL_LABEL = "عملیات ناموفق بود";

// Per-operation Persian failure text, so the user learns WHICH
// operation failed instead of a bare "خطا".
const ACTIVITY_FAIL_LABELS = {
  voice_upload: "ارسال صدا ناموفق بود.",
  stt:          "تشخیص گفتار انجام نشد.",
  chat:         "پردازش درخواست انجام نشد.",
  response:     "پردازش پاسخ انجام نشد.",
  tts:          "ساخت صدا ناموفق بود.",
  file_upload:  "آپلود فایل ناموفق بود.",
  file_process: "پردازش فایل ناموفق بود.",
  render:       "رندر ناموفق بود.",
  image:        "پردازش تصویر ناموفق بود.",
  save:         "ذخیره اطلاعات ناموفق بود.",
  assets:       "بروزرسانی فایل‌ها ناموفق بود.",
  project:      "عملیات پروژه ناموفق بود.",
};

// How long a successful operation stays visible before it fades.
// Long enough to be seen, short enough not to linger.
const ACTIVITY_DONE_MS = 1800;
// A failure stays longer so it cannot be missed.
const ACTIVITY_FAIL_MS = 6000;

const activity = {
  current: null,   // { key, label, startedAt, detail }
  stack: [],       // secondary operations started while one is active
  timer: null,     // elapsed ticker
  clearTimer: null, // scheduled hide after done/fail
};

function _activityRender() {
  const pill = $("activityStatus");
  if (!pill) return;

  const label = pill.querySelector(".activity-label");
  const elapsed = pill.querySelector(".activity-elapsed");
  const op = activity.current;

  if (!op) {
    pill.classList.add("hidden");
    pill.className = "activity-pill activity-idle hidden";
    return;
  }

  pill.classList.remove("hidden");
  pill.className = "activity-pill activity-" + (op.state || "running");
  if (label) label.textContent = op.detail
    ? op.label + " · " + op.detail
    : op.label;

  if (elapsed) {
    if (op.state === "running") {
      elapsed.textContent = clock((Date.now() - op.startedAt) / 1000);
    } else {
      elapsed.textContent = "";
    }
  }
}

function _activityStopTicker() {
  if (activity.timer) clearInterval(activity.timer);
  activity.timer = null;
}

function _activityScheduleClear(ms) {
  if (activity.clearTimer) clearTimeout(activity.clearTimer);
  activity.clearTimer = setTimeout(() => {
    // Only clear if the operation is still the one we scheduled for
    // (a newer operation must not be wiped by an older timer).
    if (activity.current && activity.current.state !== "running") {
      activity.current = null;
      _activityRender();
      // Promote a waiting secondary operation, if any.
      if (activity.stack.length && !activity.current) {
        activity.current = activity.stack.shift();
        activity.current.state = "running";
        activity.current.startedAt = Date.now();
        _activityStartTicker();
        _activityRender();
      }
    }
    activity.clearTimer = null;
  }, ms);
}

function _activityStartTicker() {
  _activityStopTicker();
  activity.timer = setInterval(() => {
    if (activity.current && activity.current.state === "running") {
      _activityRender();
    } else {
      _activityStopTicker();
    }
  }, 1000);
}

// Start (or replace) the visible operation. Returns a handle the
// caller MUST settle with finish()/fail(), so nothing is ever left
// permanently stuck.
function activityBegin(key, detail) {
  if (activity.clearTimer) { clearTimeout(activity.clearTimer); activity.clearTimer = null; }

  const label = ACTIVITY_LABELS[key] || key;

  if (activity.current && activity.current.state === "running") {
    // A genuine second operation: keep the first as primary and let the
    // newest wait. In practice the UI serialises operations, so this is
    // a safety net rather than a queue.
    activity.stack.push({ key, label, detail: detail || "", startedAt: Date.now(), state: "queued" });
  }

  activity.current = {
    key,
    label,
    detail: detail || "",
    startedAt: Date.now(),
    state: "running",
  };
  _activityStartTicker();
  _activityRender();

  let settled = false;
  return {
    update: (newDetail) => {
      if (!activity.current || activity.current.key !== key) return;
      activity.current.detail = newDetail || "";
      _activityRender();
    },
    finish: (detail) => {
      if (settled) return;
      settled = true;
      if (!activity.current || activity.current.key !== key) return;
      activity.current.state = "completed";
      activity.current.label = detail || ACTIVITY_DONE_LABEL;
      // UI_FINAL_POLISH_ACTIVITY_V1 — a TERMINAL label must not carry the
      // last transient detail. `detail` is the live, per-operation
      // readout ("دریافت نتیجه", "گام 7 / 20", "42% · 1.2 MB / 2.9 MB");
      // once the operation has completed it describes a phase that no
      // longer exists, and `_activityRender()` joins the two, producing
      // "رندر انجام شد · دریافت نتیجه". Clearing it here is the whole
      // fix: the label stays, the finished operation's phase does not.
      activity.current.detail = "";
      _activityStopTicker();
      _activityRender();
      _activityScheduleClear(ACTIVITY_DONE_MS);
    },
    fail: (detail) => {
      if (settled) return;
      settled = true;
      if (!activity.current || activity.current.key !== key) return;
      activity.current.state = "failed";
      activity.current.label = detail || ACTIVITY_FAIL_LABELS[key] || ACTIVITY_FAIL_LABEL;
      // Deliberately NOT cleared here (unlike `finish`): on a failure the
      // last real readout ("گام 7 / 20", "42% · 1.2 MB / 2.9 MB") is the
      // only diagnostic the user has, so it stays attached to the error.
      _activityStopTicker();
      _activityRender();
      _activityScheduleClear(ACTIVITY_FAIL_MS);
    },
  };
}

// Relabel the CURRENT running operation in place, without settling it.
// Used when one request moves through distinct real phases (e.g.
// upload → processing). If the key is already the current operation the
// detail is just refreshed.
function activityRelabel(key, detail) {
  if (!activity.current || activity.current.state !== "running") {
    activityBegin(key, detail);
    return;
  }
  activity.current.key = key;
  activity.current.label = ACTIVITY_LABELS[key] || key;
  if (detail !== undefined) activity.current.detail = detail || "";
  _activityRender();
}

// Convenience wrapper: run an async operation under one visible status.
// The status ALWAYS clears on settle (success or failure) — never on a
// timer, so completion is never faked.
async function withActivity(key, detail, fn) {
  const handle = activityBegin(key, detail);
  try {
    const result = await fn();
    handle.finish();
    return result;
  } catch (error) {
    handle.fail();
    throw error;
  }
}


// ==========================================================
// REAL_RENDER_LIFECYCLE_V1 — backend-confirmed render stages
//
// The ONLY source of these stages is GET /api/render/status, which
// derives them from the real ComfyUI queue/history for the exact
// prompt id this project submitted. Nothing here estimates, and no
// percentage is ever shown.
// ==========================================================

const RENDER_STAGE_LABELS = {
  preparing:  "آماده‌سازی",
  queued:     "در صف رندر",
  executing:  "در حال اجرای رندر",
  retrieving: "دریافت نتیجه",
  completed:  "تکمیل شد",
  failed:     "خطا در رندر",
  cancelled:  "لغو شد",
  unknown:    "وضعیت نامشخص",
};

const RENDER_STATUS_POLL_MS = 1200;

// Watches the read-only status endpoint while ONE chat turn is in flight.
//
// CORRECTION (B+ independent review): the previous version only started
// for turns the CLIENT already classified as a render (`isGenerating`)
// or that carried an image. A text-only approved-design follow-up is
// classified as ordinary chat by the client but still submits a ComfyUI
// job on the server, so its progress was never shown.
//
// The fix is NOT to guess that a chat message is a render. The watcher
// now runs for EVERY in-flight turn and stays completely SILENT until
// the server reports a real, correctly correlated render for THIS
// project. Only then does it take over the pill.
//
//   * `expectRender: true`  — the client has a strong reason to expect a
//                             render, so "preparing" is shown while the
//                             workflow is still being built.
//   * `expectRender: false` — ordinary chat. The label is left to the
//                             chat operation until real evidence arrives.
//
// It is otherwise deliberately conservative:
//   * tied to the operation object that started it (`opRef`)
//   * never overlaps its own requests
//   * drops a response from an older generation
//   * stops on settle, replacement, or an explicit stop()
//   * a transport failure never invents progress
function startRenderWatcher(handle, projectId, opRef, options) {
  const opts = options || {};
  const expectRender = !!opts.expectRender;
  const intervalMs = typeof opts.intervalMs === "number"
    ? opts.intervalMs
    : RENDER_STATUS_POLL_MS;

  let stopped = false;
  let inFlight = false;
  let timer = null;
  let lastGeneration = -1;
  let sawActive = false;

  function stop() {
    stopped = true;
    if (timer) clearInterval(timer);
    timer = null;
  }

  function paint(label) {
    if (stopped) return;
    if (!opRef || activity.current !== opRef) return;
    handle.update(label);
  }

  async function tick() {
    if (stopped || inFlight) return;
    if (!opRef || activity.current !== opRef) { stop(); return; }

    inFlight = true;

    try {
      const { ok, data } = await api(
        "/api/render/status?project_id=" + encodeURIComponent(projectId || ""),
        { method: "GET" }
      );

      if (stopped || activity.current !== opRef) return;

      if (!ok || !data || data.status === "error") {
        // Only speak up if this turn is actually tracking a render.
        if (sawActive || expectRender) paint(RENDER_STAGE_LABELS.unknown);
        return;
      }

      const generation = typeof data.generation === "number" ? data.generation : -1;

      // A reply about an older render must never repaint this one.
      if (generation >= 0 && lastGeneration >= 0 && generation < lastGeneration) return;
      if (generation >= 0) lastGeneration = generation;

      if (!data.active) {
        // A record existed and then disappeared: the job is finished and
        // the response is on its way. Never step back to "preparing".
        if (sawActive) { paint(RENDER_STAGE_LABELS.retrieving); return; }

        // No record yet. For an expected render this is the build phase.
        if (expectRender) { paint(RENDER_STAGE_LABELS.preparing); return; }

        // Ordinary chat with no server evidence of a render: stay silent
        // so the chat operation keeps its own label.
        return;
      }

      // REAL, CORRECTLY CORRELATED RENDER EVIDENCE.
      sawActive = true;

      const stage = String(data.stage || "unknown");
      let label = RENDER_STAGE_LABELS[stage] || RENDER_STAGE_LABELS.unknown;

      // Verified sampler steps only — never an overall percentage.
      if (stage === "executing"
          && typeof data.sampling_step === "number"
          && typeof data.sampling_max === "number"
          && data.sampling_max > 0) {
        label = "گام " + data.sampling_step + " / " + data.sampling_max;
      }

      paint(label);

    } catch (error) {
      if (!stopped && activity.current === opRef && (sawActive || expectRender)) {
        handle.update(RENDER_STAGE_LABELS.unknown);
      }
    } finally {
      inFlight = false;
    }
  }

  timer = setInterval(tick, intervalMs);
  tick();

  return { stop };
}

// Backwards-compatible alias for call sites that know a render is coming.
function startRenderStatusPoller(handle, projectId, opRef) {
  return startRenderWatcher(handle, projectId, opRef, { expectRender: true });
}

async function api(path, options) {
  const response = await fetch(path, Object.assign({
    headers: { "Content-Type": "application/json" },
  }, options || {}));
  let payload = null;
  try { payload = await response.json(); } catch (e) { payload = null; }
  return { ok: response.ok, status: response.status, data: payload };
}


// ==========================================================
// REAL_OPERATION_PROGRESS_V1 — PART A
// Genuine upload progress for the multipart transport.
//
// `fetch()` cannot report upload progress: there is no equivalent of
// XMLHttpRequest.upload.onprogress. The JSON/revision paths stay on
// `fetch()` exactly as before; ONLY the multipart body uses this.
//
// The contract is deliberately identical to `api()`:
//     { ok, status, data }
// so every existing caller keeps working unchanged.
//
// Nothing here estimates. A percentage is produced ONLY from a real
// ProgressEvent where `lengthComputable` is true and `total` is a
// positive number. Otherwise the caller is told the length is unknown
// and the operation stays indeterminate.
// ==========================================================

function _abortError() {
  try {
    return new DOMException("Aborted", "AbortError");
  } catch (e) {
    const error = new Error("Aborted");
    error.name = "AbortError";
    return error;
  }
}

function uploadWithProgress(path, form, options) {
  const opts = options || {};
  const signal = opts.signal || null;
  const onProgress = typeof opts.onProgress === "function" ? opts.onProgress : null;
  const onUploaded = typeof opts.onUploaded === "function" ? opts.onUploaded : null;

  return new Promise((resolve, reject) => {
    // A request that was already cancelled must never start on the wire.
    if (signal && signal.aborted) {
      reject(_abortError());
      return;
    }

    const xhr = new XMLHttpRequest();
    xhr.open("POST", path, true);

    let settled = false;
    let uploadedAnnounced = false;

    // Every listener is detached on settle, so a late progress event
    // from a cancelled or superseded request can never reach the UI.
    function cleanup() {
      if (signal) signal.removeEventListener("abort", handleAbort);
      xhr.upload.onprogress = null;
      xhr.upload.onload = null;
      xhr.upload.onerror = null;
      xhr.onload = null;
      xhr.onerror = null;
      xhr.onabort = null;
    }

    function settle(fn, value) {
      if (settled) return;
      settled = true;
      cleanup();
      fn(value);
    }

    function handleAbort() {
      try { xhr.abort(); } catch (e) { /* already finished */ }
      settle(reject, _abortError());
    }

    xhr.upload.onprogress = (event) => {
      if (settled || !onProgress) return;
      onProgress({
        loaded: event.loaded,
        total: event.total,
        lengthComputable: !!event.lengthComputable,
      });
    };

    xhr.upload.onload = () => {
      if (settled || uploadedAnnounced) return;
      uploadedAnnounced = true;
      if (onUploaded) onUploaded();
    };

    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch (e) {
        // Same failure mode as `await response.json()` on the fetch path.
        settle(reject, new Error("Invalid JSON response"));
        return;
      }
      settle(resolve, {
        ok: xhr.status >= 200 && xhr.status < 300,
        status: xhr.status,
        data,
      });
    };

    xhr.onerror = () => settle(reject, new Error("Network error"));
    xhr.onabort = () => settle(reject, _abortError());

    if (signal) signal.addEventListener("abort", handleAbort, { once: true });

    try {
      xhr.send(form);
    } catch (error) {
      settle(reject, error);
    }
  });
}

function _formatBytes(bytes) {
  if (typeof bytes !== "number" || !isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
}

// Returns the detail line for the activity pill. A percentage appears
// ONLY when the browser actually reported a computable total. When the
// length is unknown, only the real transferred byte count is shown —
// never a guessed figure.
function formatUploadProgress(progress) {
  const loaded = progress && progress.loaded;
  if (progress && progress.lengthComputable && progress.total > 0) {
    const percent = Math.min(100, Math.floor((loaded / progress.total) * 100));
    return percent + "% · " + _formatBytes(loaded) + " / " + _formatBytes(progress.total);
  }
  const sent = _formatBytes(loaded);
  return sent || "";
}


// ==========================================================
// MODAL
// ==========================================================

function openModal(opts) {
  return new Promise((resolve) => {
    $("modalTitle").textContent = opts.title || "";
    $("modalBody").textContent = opts.body || "";

    const input = $("modalInput");
    if (opts.input) {
      input.classList.remove("hidden");
      input.value = opts.inputValue || "";
      input.placeholder = opts.inputPlaceholder || "";
      setTimeout(() => input.focus(), 30);
    } else {
      input.classList.add("hidden");
    }

    $("modalConfirm").textContent = opts.confirmLabel || "Confirm";
    $("modalConfirm").className = "btn " + (opts.danger ? "btn-danger-ghost" : "btn-primary");
    $("modalCancel").textContent = opts.cancelLabel || "Cancel";
    $("modalBackdrop").classList.remove("hidden");

    function done(value) {
      $("modalBackdrop").classList.add("hidden");
      $("modalConfirm").onclick = null;
      $("modalCancel").onclick = null;
      resolve(value);
    }

    $("modalConfirm").onclick = () => done(opts.input ? input.value.trim() : true);
    $("modalCancel").onclick = () => done(null);
  });
}


// ==========================================================
// CODER MVP V1 — EXPLICIT SAVED-FILE EXECUTION REVIEW
//
// This flow is intentionally separate from chat and file-save approval.
// The browser never receives or stores an execution capability. The UI
// server owns the signed action fields and the Core owns the capability.
// ==========================================================

let executionPreviewState = null;

function closeExecutionModal() {
  executionPreviewState = null;
  $("executionModal").classList.add("hidden");
  $("executionPreview").classList.add("hidden");
  $("confirmRunBtn").classList.add("hidden");
  $("executionStatus").textContent = "";
}

function openExecutionModal() {
  if (!state.projectId) {
    toast("Open a project before reviewing a Python file.");
    return;
  }
  executionPreviewState = null;
  $("executionPreview").classList.add("hidden");
  $("confirmRunBtn").classList.add("hidden");
  $("executionStatus").textContent = "No execution has been approved.";
  $("executionModal").classList.remove("hidden");
  $("executionFilename").focus();
}

// ==========================================================
// CODER — UNSAVED DRAFT VERIFICATION
//
// A separate approval from saving. The server custodies the capability token;
// this client only ever sends { project_id, source_sha256 } and then
// { project_id }. Verdicts are rendered exactly as the server reports them, so
// an unsupported or unexecuted scenario can never look like a pass.
// ==========================================================

let draftVerifyState = null;

function draftShow(value) {
  if (value === undefined || value === null || value === "") return "—";
  return String(value);
}

function closeDraftVerifyModal() {
  draftVerifyState = null;
  $("draftVerifyModal").classList.add("hidden");
  $("draftVerifyVerdicts").classList.add("hidden");
  $("confirmDraftVerifyBtn").classList.add("hidden");
  $("draftVerifyStatus").textContent = "";
}

function openDraftVerifyModal() {
  if (!state.projectId) {
    toast("Open a project before verifying a draft.");
    return;
  }
  draftVerifyState = null;
  $("draftVerifyVerdicts").classList.add("hidden");
  $("confirmDraftVerifyBtn").classList.add("hidden");
  $("draftDigest").textContent = "—";
  $("draftFilename").textContent = "—";
  $("draftSyntax").textContent = "—";
  $("draftStatic").textContent = "—";
  $("draftFunctional").textContent = "—";
  $("draftVerifyStatus").textContent = "Nothing has been verified yet.";
  $("draftVerifyModal").classList.remove("hidden");
}

async function loadPendingDraft() {
  draftVerifyState = null;
  $("confirmDraftVerifyBtn").classList.add("hidden");
  $("draftVerifyVerdicts").classList.add("hidden");
  $("draftVerifyStatus").textContent = "Reading the pending draft…";

  const result = await api("/api/coder/draft-verification/pending", {
    method: "POST",
    body: JSON.stringify({ project_id: state.projectId }),
  });
  const data = result.data || {};
  if (!result.ok || data.ok !== true) {
    $("draftVerifyStatus").textContent =
      "Refused: " + String(data.reason || "request_failed");
    return;
  }
  if (!data.pending) {
    $("draftVerifyStatus").textContent =
      "No draft is waiting for approval in this project.";
    return;
  }

  draftVerifyState = {
    project_id: state.projectId,
    source_sha256: data.source_sha256,
  };
  $("draftDigest").textContent = draftShow(data.source_sha256);
  $("draftFilename").textContent = draftShow(data.filename);
  $("draftSyntax").textContent = draftShow(data.syntax);
  $("draftStatic").textContent = draftShow(data.static_review);
  $("draftFunctional").textContent = draftShow(data.functional);
  $("draftVerifyStatus").textContent =
    "This is the draft that would run. Verifying it does not save it.";
  $("confirmDraftVerifyBtn").classList.remove("hidden");
}

function renderDraftScenarios(scenarios) {
  const list = $("draftScenarioList");
  clear(list);
  (scenarios || []).forEach((item) => {
    const row = el("li", "draft-scenario");
    row.dataset.status = String(item.status || "NOT_RUN");
    row.appendChild(el("span", "draft-scenario-name", String(item.id || "?")));
    row.appendChild(el("span", "draft-scenario-status", String(item.status || "NOT_RUN")));
    if (item.detail) {
      row.appendChild(el("span", "draft-scenario-detail", String(item.detail)));
    }
    list.appendChild(row);
  });
}

async function confirmDraftVerification() {
  if (!draftVerifyState) {
    $("draftVerifyStatus").textContent = "Load the pending draft first.";
    return;
  }
  const button = $("confirmDraftVerifyBtn");
  button.disabled = true;
  $("draftVerifyVerdicts").classList.add("hidden");
  $("draftVerifyStatus").textContent = "Requesting isolated verification…";

  try {
    const consent = await api("/api/coder/draft-verification/consent", {
      method: "POST",
      body: JSON.stringify({
        project_id: draftVerifyState.project_id,
        source_sha256: draftVerifyState.source_sha256,
      }),
    });
    const consentData = consent.data || {};
    if (!consent.ok || consentData.ok !== true) {
      $("draftVerifyStatus").textContent =
        "Verification refused: " + String(consentData.reason || "request_failed");
      return;
    }

    $("draftVerifyStatus").textContent = "Running the isolated verification…";
    const run = await api("/api/coder/draft-verification/run", {
      method: "POST",
      body: JSON.stringify({ project_id: draftVerifyState.project_id }),
    });
    const data = run.data || {};

    $("draftSandbox").textContent = draftShow(data.sandbox);
    $("draftIntegrity").textContent = draftShow(data.integrity);
    $("draftFunctionalVerdict").textContent = draftShow(data.functional);
    $("draftResultDigest").textContent = data.source_sha256
      ? "Verdicts apply to source " + String(data.source_sha256)
      : "";
    renderDraftScenarios(data.scenarios);
    $("draftVerifyVerdicts").classList.remove("hidden");

    if (!run.ok && !data.stage) {
      $("draftVerifyStatus").textContent =
        "Verification did not run: " + String(data.reason || "request_failed");
    } else {
      $("draftVerifyStatus").textContent =
        "Verification finished. This did not save the file.";
    }
  } finally {
    button.disabled = false;
  }
}

function executionLimitsText(limits) {
  // The server sends the canonical DEFAULT_RESOURCE_LIMITS keys, which are
  // prefixed `max_`. The short form is still accepted so an older payload
  // renders instead of degrading to question marks.
  const value = limits || {};
  const pick = (canonical, legacy) => (
    value[canonical] === undefined || value[canonical] === null
      ? value[legacy]
      : value[canonical]
  );
  const show = (item) => String(
    item === undefined || item === null ? "?" : item
  );
  return [
    "runtime " + show(pick("max_runtime_seconds", "runtime_seconds")) + "s",
    "memory " + show(pick("max_memory_mb", "memory_mb")) + "MB",
    "CPU " + show(pick("max_cpus", "cpus")),
    "PIDs " + show(pick("max_pids", "pids_limit")),
    "output " + show(pick("max_output_bytes", "output_bytes")) + " bytes",
  ].join(" · ");
}

async function loadExecutionPreview() {
  const filename = $("executionFilename").value.trim();
  executionPreviewState = null;
  $("confirmRunBtn").classList.add("hidden");
  $("executionPreview").classList.add("hidden");
  $("executionStatus").textContent = "Loading the exact saved bytes…";

  const result = await api("/api/coder/execution/preview", {
    method: "POST",
    body: JSON.stringify({ project_id: state.projectId, filename }),
  });
  const data = result.data || {};
  const preview = data.preview || {};
  if (!result.ok || data.ok !== true) {
    $("executionStatus").textContent = "Preview refused: "
      + String(data.reason || "request_failed");
    return;
  }

  executionPreviewState = {
    project_id: state.projectId,
    proposal_id: data.proposal_id,
    filename: preview.filename,
    source_sha256: preview.source_sha256,
  };
  $("executionDigest").textContent = preview.source_sha256 || "—";
  $("executionNetwork").textContent = preview.network_policy || "none";
  $("executionLimits").textContent = executionLimitsText(preview.resource_limits);
  $("executionExpiry").textContent = preview.approval_expires_at
    ? new Date(preview.approval_expires_at * 1000).toLocaleString() : "—";
  $("executionSource").textContent = preview.source || "";
  $("executionPreview").classList.remove("hidden");
  $("confirmRunBtn").classList.remove("hidden");
  $("executionStatus").textContent = data.execution_enabled
    ? "Ready for a separate, single-use execution approval."
    : "Execution is disabled by the server owner.";
}

function executionResultText(data) {
  const run = data.execution || {};
  const lines = [
    data.ok ? "Python execution completed." : "Python execution failed.",
    "Reason: " + String(data.reason || "none"),
    "Exit code: " + String(run.exit_code === undefined ? "unknown" : run.exit_code),
    "Source digest verified: " + String(run.source_digest_verified === true),
    "Container removal verified: " + String(run.removal_verified === true),
  ];
  if (run.stdout) lines.push("stdout:\n" + run.stdout);
  if (run.stderr) lines.push("stderr:\n" + run.stderr);
  return lines.join("\n");
}

async function confirmExecutionRun() {
  const approved = executionPreviewState;
  if (!approved) {
    $("executionStatus").textContent = "Load a fresh preview before approval.";
    return;
  }
  executionPreviewState = null;
  $("confirmRunBtn").classList.add("hidden");
  $("loadExecutionPreviewBtn").disabled = true;
  $("executionStatus").textContent = "Execution approval submitted…";

  let result;
  try {
    result = await api("/api/coder/execution/consent", {
      method: "POST",
      body: JSON.stringify(Object.assign({}, approved, { confirm_run: true })),
    });
  } finally {
    $("loadExecutionPreviewBtn").disabled = false;
  }
  const data = (result && result.data) || {};
  $("executionStatus").textContent = data.ok
    ? "Execution completed; the approval was consumed."
    : "Execution refused or failed: " + String(data.reason || "request_failed");
  const chat = $("chatScroll");
  chat.appendChild(messageNode("assistant", executionResultText(data)));
  chat.scrollTop = chat.scrollHeight;
}


// ==========================================================
// CODER — WINDOWS EXE PACKAGING (separate consent, sandbox only)
// ==========================================================

let packageState = null;

function closePackageModal() {
  $("packageModal").classList.add("hidden");
  $("packagePreview").classList.add("hidden");
  $("checkPackageBtn").classList.add("hidden");
  $("preparePackageBtn").disabled = false;
  $("packageStatus").textContent = "";
  packageState = null;
}

function openPackageModal() {
  closePackageModal();
  $("packageModal").classList.remove("hidden");
  $("packageFilename").focus();
}

async function preparePackageJob() {
  const filename = $("packageFilename").value.trim();
  packageState = null;
  $("checkPackageBtn").classList.add("hidden");
  $("packagePreview").classList.add("hidden");
  $("preparePackageBtn").disabled = true;
  $("packageStatus").textContent = "Preparing an isolated sandbox job…";

  const result = await api("/api/coder/package/prepare", {
    method: "POST",
    body: JSON.stringify({
      project_id: state.projectId,
      filename,
      confirm_package: true,
    }),
  });
  $("preparePackageBtn").disabled = false;
  const data = result.data || {};
  if (!result.ok || data.ok !== true) {
    $("packageStatus").textContent = "Packaging refused: "
      + String(data.reason || "request_failed");
    return;
  }

  packageState = {
    project_id: state.projectId,
    job_id: data.job_id,
    exe_name: data.exe_name,
  };
  $("packageDigest").textContent = data.source_sha256 || "—";
  $("packageNetwork").textContent = data.sandbox_network || "disabled";
  $("packageHostBuild").textContent = data.host_build_available === true
    ? "available" : "not available";
  $("packageWsb").textContent = "Sandbox file: " + String(data.wsb_path || "");
  $("packagePreview").classList.remove("hidden");
  $("checkPackageBtn").classList.remove("hidden");
  $("packageStatus").textContent = data.manual_launch_required
    ? "Open that .wsb file to run the isolated build, then click Check build result."
    : "Sandbox started.";
}

async function checkPackageResult() {
  const job = packageState;
  if (!job) {
    $("packageStatus").textContent = "Prepare a sandbox job first.";
    return;
  }
  $("checkPackageBtn").disabled = true;
  $("packageStatus").textContent = "Checking the sandbox result…";
  let result;
  try {
    result = await api("/api/coder/package/status", {
      method: "POST",
      body: JSON.stringify({
        project_id: job.project_id,
        job_id: job.job_id,
      }),
    });
  } finally {
    $("checkPackageBtn").disabled = false;
  }
  const data = (result && result.data) || {};
  if (!result.ok || data.ok !== true) {
    $("packageStatus").textContent = "Build not delivered: "
      + String(data.reason || "request_failed");
    return;
  }
  if (data.stage === "awaiting_sandbox") {
    $("packageStatus").textContent = "No result yet — run the .wsb file first.";
    return;
  }
  $("packageStatus").textContent = "EXE delivered: " + String(data.exe_name || "");
  const chat = $("chatScroll");
  const lines = [
    "Windows EXE built inside the sandbox.",
    "File: " + String(data.exe_name || ""),
    "Size: " + String(data.exe_size || 0) + " bytes",
    "EXE SHA-256: " + String(data.exe_sha256 || ""),
    "Source SHA-256: " + String(data.source_sha256 || ""),
    "Download: " + String(data.artifact_url || ""),
  ];
  chat.appendChild(messageNode("assistant", lines.join("\n")));
  chat.scrollTop = chat.scrollHeight;
}


// ==========================================================
// VIEW SWITCHING
// ==========================================================

function showHome() {
  state.view = "home";
  document.body.dataset.view = "home";
  $("homeView").classList.remove("hidden");
  $("workspaceView").classList.add("hidden");
  loadProjects();
}

function showWorkspace() {
  state.view = "workspace";
  document.body.dataset.view = "workspace";
  $("homeView").classList.add("hidden");
  $("workspaceView").classList.remove("hidden");
}


// ==========================================================
// PROJECTS
// ==========================================================

async function loadProjects() {
  const { data } = await api("/api/projects?limit=24");
  if (!data) return;
  state.projects = {
    recent: data.recent || [],
    archived: data.archived || [],
  };
  renderHomeProjects();
  renderSideProjects();
}

function projectCard(project) {
  const card = el("button", "project-card");
  card.type = "button";
  if (state.projectId === project.project_id) card.classList.add("is-open");

  card.appendChild(el("h4", null, project.project_name || "Untitled"));

  const meta = el("div", "pc-meta");
  meta.appendChild(el("span", null, "edited " + timeAgo(project.updated_at)));
  if (project.status === "archived") {
    meta.appendChild(el("span", "badge badge-archived", "archived"));
  }
  if (project.message_count) {
    meta.appendChild(el("span", null, project.message_count + " msgs"));
  }
  if (project.asset_count) {
    meta.appendChild(el("span", null, project.asset_count + " assets"));
  }
  card.appendChild(meta);

  card.appendChild(el("div", "pc-id", project.project_id));

  card.onclick = () => openProject(project.project_id);
  return card;
}

function renderHomeProjects() {
  const recent = $("recentProjects");
  clear(recent);
  state.projects.recent.forEach((p) => recent.appendChild(projectCard(p)));
  $("recentCount").textContent = state.projects.recent.length;
  $("recentEmpty").classList.toggle("hidden", state.projects.recent.length > 0);

  const archived = $("archivedProjects");
  clear(archived);
  state.projects.archived.forEach((p) => archived.appendChild(projectCard(p)));
  $("archivedEmpty").classList.toggle("hidden", state.projects.archived.length > 0);
}

function sideItem(project) {
  const item = el("button", "side-item");
  item.type = "button";
  if (state.projectId === project.project_id) item.classList.add("is-open");
  item.appendChild(el("span", null, project.project_name || "Untitled"));
  item.appendChild(el("span", "si-sub", timeAgo(project.updated_at)));
  item.onclick = () => openProject(project.project_id);

  // PROJECT_CONTEXT_MENU_V1 — the menu acts on THIS item's id, never on
  // whichever project happened to be open. Left-click behaviour above is
  // untouched.
  item.setAttribute("aria-haspopup", "menu");
  item.title = (project.project_name || "Untitled")
    + " — right-click, or Shift+F10, for project actions";

  item.oncontextmenu = (event) => {
    if (Date.now() < _ctxKeyboardGuardUntil) return;
    event.preventDefault();
    openProjectMenu(project.project_id, event.clientX, event.clientY, item);
  };

  // Shift+F10 / the dedicated Menu key. Chromium already fires
  // `contextmenu` for Shift+F10, so this path is guarded to avoid opening
  // the menu twice.
  item.addEventListener("keydown", (event) => {
    const isMenuKey = event.key === "ContextMenu"
      || (event.shiftKey && event.key === "F10");
    if (!isMenuKey) return;
    event.preventDefault();
    _ctxKeyboardGuardUntil = Date.now() + 250;
    const rect = item.getBoundingClientRect();
    openProjectMenu(project.project_id, rect.left + 16, rect.top + 16, item);
  });

  return item;
}

function renderSideProjects() {
  const recent = $("sideProjects");
  clear(recent);
  state.projects.recent.forEach((p) => recent.appendChild(sideItem(p)));

  const archived = $("sideArchived");
  clear(archived);
  if (!state.projects.archived.length) {
    archived.appendChild(el("p", "muted tiny", "none"));
  } else {
    state.projects.archived.forEach((p) => archived.appendChild(sideItem(p)));
  }
}

async function createProject() {
  const name = await openModal({
    title: "New Project",
    body: "Give this architectural project a name. You can rename it later.",
    input: true,
    inputPlaceholder: "Modern Villa",
    confirmLabel: "Create Project",
  });
  if (!name) return;

  const { data } = await api("/api/projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });

  if (!data || data.status !== "success") {
    toast("Could not create the project.");
    return;
  }

  state.projectId = data.project.project_id;
  state.project = data.project;
  toast("Project created");
  await enterWorkspace();
}

async function openProject(projectId) {
  const { data } = await api("/api/projects/" + projectId + "/open", {
    method: "POST",
    body: JSON.stringify({}),
  });

  if (!data || data.status !== "success") {
    toast("Could not open the project.");
    return;
  }

  state.projectId = projectId;
  state.project = data.project;

  // UNCERTAIN_TRANSCRIPT_REVIEW_V1 — a candidate belongs to the project it
  // was captured in and must not survive a project change.
  clearVoiceReview();

  await enterWorkspace();
}

async function enterWorkspace() {
  showWorkspace();
  updateProjectHeader();
  await loadModes();
  applyProjectUiState();
  await loadVoiceCapability();
  // OFFLINE_DEGRADED_STATUS_UI_V1 — the capability payload was just
  // refreshed, so re-derive the visible connectivity state from it.
  renderConnectivity(
    deriveConnectivity(state.connectivityRuntime, state.voice.capability, true)
  );
  await loadAssets();
  await loadConversation();
  // KROCKI_SITE_UPLOAD_V27 — the active parcel belongs to the project, so it
  // is re-read on every workspace entry rather than cached across projects.
  await refreshKrockiState();
  startSaveStatePolling();
  await loadProjects();
}

function updateProjectHeader() {
  const project = state.project || {};
  $("wsProjectName").textContent = project.project_name || "—";
}

async function renameProject(projectId) {
  // PROJECT_CONTEXT_MENU_V1 — the target defaults to the OPEN project so
  // every existing caller (the header button) behaves exactly as before.
  // A right-click passes the project it was opened on, which may not be
  // the active one.
  const target = projectId || state.projectId;
  if (!target) return;

  const project = projectById(target) || (target === state.projectId ? state.project : null) || {};

  const name = await openModal({
    title: "Rename Project",
    body: "The project id never changes, so renaming can never collide with another project.",
    input: true,
    inputValue: project.project_name || "",
    confirmLabel: "Rename",
  });
  if (!name) return;

  const { data } = await api("/api/projects/" + target + "/rename", {
    method: "POST",
    body: JSON.stringify({ name }),
  });

  if (data && data.status === "success") {
    if (target === state.projectId) {
      state.project = data.project;
      updateProjectHeader();
    }
    await loadProjects();
    toast("Renamed");
  } else {
    toast("Rename failed");
  }
}

async function archiveProject(projectId) {
  const target = projectId || state.projectId;
  if (!target) return;

  const { data } = await api("/api/projects/" + target + "/archive", {
    method: "POST",
    body: JSON.stringify({}),
  });

  if (data && data.status === "success") {
    toast("Project archived — files kept");
    if (target === state.projectId) {
      state.projectId = null;
      state.project = null;
      stopSaveStatePolling();
      showHome();
    } else {
      await loadProjects();
    }
  }
}

// PROJECT_CONTEXT_MENU_V1 — Restore. The endpoint already existed
// (`/api/projects/<id>/restore` -> core `restore_project`); only the UI
// entry point was missing.
async function restoreProject(projectId) {
  const target = projectId || state.projectId;
  if (!target) return;

  const { data } = await api("/api/projects/" + target + "/restore", {
    method: "POST",
    body: JSON.stringify({}),
  });

  if (data && data.status === "success") {
    toast("Project restored");
    await loadProjects();
  } else {
    toast("Restore failed");
  }
}

async function deleteProject(projectId) {
  const target = projectId || state.projectId;
  if (!target) return;

  const project = projectById(target) || (target === state.projectId ? state.project : null) || {};

  // Deletion is never a one-click destructive action.
  const confirmed = await openModal({
    title: "Delete Project",
    body: 'Delete "' + (project.project_name || "") + '"?\n\n'
      + "This will remove this project and its managed project files.\n"
      + "Files are moved to a quarantine folder, not erased.",
    confirmLabel: "Delete Project",
    cancelLabel: "Cancel",
    danger: true,
  });
  if (!confirmed) return;

  const { data } = await api("/api/projects/" + target + "/delete", {
    method: "POST",
    body: JSON.stringify({ confirmed: true, hard: false }),
  });

  if (data && data.status === "success") {
    toast("Project deleted (files quarantined)");
    if (target === state.projectId) {
      state.projectId = null;
      state.project = null;
      stopSaveStatePolling();
      showHome();
    } else {
      await loadProjects();
    }
  } else {
    toast("Delete failed");
  }
}

async function exportProject(projectId) {
  const target = projectId || state.projectId;
  if (!target) return;

  const { data } = await api("/api/projects/" + target + "/export", {
    method: "POST",
    body: JSON.stringify({}),
  });

  if (data && data.status === "success") {
    toast("Exported " + ((data.export || {}).asset_count || 0) + " assets");
  } else {
    toast("Export failed");
  }
}


// ==========================================================
// PROJECT_CONTEXT_MENU_V1
//
// One menu, one dispatcher, no second project controller: every action
// below calls the SAME functions the header buttons call, with the id
// of the item the menu was opened on.
//
// The target is captured in `_ctxProjectId` at open time and cleared on
// close, so an action can never fall back to `state.projectId`.
// ==========================================================

let _ctxProjectId = null;
let _ctxAnchor = null;
// Set briefly after a keyboard open so the browser's own `contextmenu`
// event for Shift+F10 cannot open the same menu a second time.
let _ctxKeyboardGuardUntil = 0;

function projectById(projectId) {
  const groups = state.projects || {};
  return (groups.recent || []).concat(groups.archived || [])
    .find((p) => p && p.project_id === projectId) || null;
}

function projectMenuNode() {
  return $("projectMenu");
}

function closeProjectMenu() {
  const menu = projectMenuNode();
  if (!menu) return;
  menu.classList.add("hidden");
  if (_ctxAnchor) _ctxAnchor.classList.remove("ctx-target");
  _ctxAnchor = null;
  _ctxProjectId = null;
}

function openProjectMenu(projectId, clientX, clientY, anchor) {
  const menu = projectMenuNode();
  if (!menu) return;

  const project = projectById(projectId) || {};
  const archived = project.status === "archived";

  // Archive and Restore are mutually exclusive: only the action that is
  // valid for THIS project's state is offered. Both stay in the DOM so
  // the menu shape is stable, but the invalid one is disabled.
  menu.querySelectorAll(".ctx-item").forEach((item) => {
    const action = item.dataset.action;
    item.disabled = (action === "archive" && archived)
      || (action === "restore" && !archived);
  });

  closeProjectMenu();

  _ctxProjectId = projectId;
  _ctxAnchor = anchor || null;
  if (_ctxAnchor) _ctxAnchor.classList.add("ctx-target");

  menu.classList.remove("hidden");

  // Measure AFTER showing, then clamp into the viewport so the menu can
  // never open off-screen at the bottom or right edge.
  const rect = menu.getBoundingClientRect();
  const margin = 8;
  const maxX = window.innerWidth - rect.width - margin;
  const maxY = window.innerHeight - rect.height - margin;
  const x = Math.max(margin, Math.min(clientX, maxX));
  const y = Math.max(margin, Math.min(clientY, maxY));
  menu.style.left = x + "px";
  menu.style.top = y + "px";

  const first = menu.querySelector(".ctx-item:not([disabled])");
  if (first) first.focus();
}

async function runProjectMenuAction(action) {
  const projectId = _ctxProjectId;
  if (!projectId) return;

  // Capture before closing: closeProjectMenu() clears the target.
  const project = projectById(projectId) || {};

  closeProjectMenu();

  if (action === "open") {
    await openProject(projectId);
  } else if (action === "rename") {
    await renameProject(projectId);
  } else if (action === "archive") {
    await archiveProject(projectId);
  } else if (action === "restore") {
    await restoreProject(projectId);
  } else if (action === "export") {
    await exportProject(projectId);
  } else if (action === "delete") {
    await deleteProject(projectId);
  } else {
    toast("Unknown action: " + action);
  }
}

function projectMenuKeydown(event) {
  const menu = projectMenuNode();
  if (!menu || menu.classList.contains("hidden")) return;

  const items = Array.from(menu.querySelectorAll(".ctx-item:not([disabled])"));
  if (!items.length) return;

  const index = items.indexOf(document.activeElement);

  if (event.key === "ArrowDown") {
    event.preventDefault();
    items[(index + 1) % items.length].focus();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    items[(index - 1 + items.length) % items.length].focus();
  } else if (event.key === "Home") {
    event.preventDefault();
    items[0].focus();
  } else if (event.key === "End") {
    event.preventDefault();
    items[items.length - 1].focus();
  } else if (event.key === "Tab") {
    // A menu is not a tab stop chain: close instead of tabbing out of it.
    closeProjectMenu();
  }
}

function wireProjectMenu() {
  const menu = projectMenuNode();
  if (!menu) return;

  menu.querySelectorAll(".ctx-item").forEach((item) => {
    item.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      runProjectMenuAction(item.dataset.action);
    });
  });

  menu.addEventListener("keydown", projectMenuKeydown);

  // Close on Escape from anywhere, on any outside click, and whenever
  // the viewport moves under the menu (scroll/resize would otherwise
  // leave it detached from its anchor).
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeProjectMenu();
  });
  document.addEventListener("mousedown", (event) => {
    const node = projectMenuNode();
    if (!node || node.classList.contains("hidden")) return;
    if (!node.contains(event.target)) closeProjectMenu();
  });
  window.addEventListener("resize", closeProjectMenu);
  window.addEventListener("scroll", closeProjectMenu, true);
}



// ==========================================================
// SAVE STATE
// ==========================================================

function applySaveState(save) {
  const pill = $("saveState");
  const label = pill.querySelector(".save-label");
  pill.className = "save-pill";

  const value = (save || {}).state || "unknown";

  if (value === "saved") {
    pill.classList.add("save-saved");
    label.textContent = "Saved";
  } else if (value === "failed") {
    pill.classList.add("save-failed");
    label.textContent = "Save failed";
  } else {
    pill.classList.add("save-saving");
    label.textContent = "Saving…";
  }

  $("lastSaved").textContent = save && save.last_saved_at
    ? "last saved " + timeAgo(save.last_saved_at)
    : "";
}

function startSaveStatePolling() {
  stopSaveStatePolling();
  // LOG_ROTATION_FIX_01 — poll cadence is bounded by page
  // visibility. The former unconditional 2500 ms interval kept
  // firing for every open/abandoned/backgrounded tab, 24/7, and
  // each tick is one Core API request (one Werkzeug log line).
  // With several tabs left open that was the dominant source of
  // unbounded core_api.log growth.
  //
  // Policy: visible tab -> SAVE_STATE_POLL_ACTIVE_MS.
  //         hidden tab  -> SAVE_STATE_POLL_IDLE_MS (much slower,
  //                        and skipped entirely while no project
  //                        is open).
  if (document.hidden) {
    state.polling = setInterval(saveStatePollTick, SAVE_STATE_POLL_IDLE_MS);
  } else {
    state.polling = setInterval(saveStatePollTick, SAVE_STATE_POLL_ACTIVE_MS);
  }
  if (!startSaveStatePolling._visibilityWired) {
    startSaveStatePolling._visibilityWired = true;
    document.addEventListener("visibilitychange", () => {
      if (state.polling) startSaveStatePolling();
    });
  }
}

// Poll interval while the tab is visible and a project is open.
const SAVE_STATE_POLL_ACTIVE_MS = 5000;
// Poll interval while the tab is hidden/backgrounded. Kept slow so
// abandoned tabs stop dominating Core API request volume.
const SAVE_STATE_POLL_IDLE_MS = 60000;

async function saveStatePollTick() {
  // Never poll without an open project, and never poll a hidden
  // tab at the active cadence.
  if (!state.projectId) return;
  if (document.hidden && (Date.now() % 2)) return;
  const { data } = await api(
    "/api/projects/" + state.projectId + "/save-state"
  );
  if (data && data.save_state) applySaveState(data.save_state);
}

function stopSaveStatePolling() {
  if (state.polling) clearInterval(state.polling);
  state.polling = null;
}


// ==========================================================
// MODES / QUALITY / SEED
// ==========================================================

async function loadModes() {
  if (state.modes) return state.modes;

  const { data } = await api("/api/render/modes");
  state.modes = data || null;
  if (!state.modes) return null;

  const modeSelect = $("modeSelect");
  clear(modeSelect);
  (state.modes.active || []).forEach((m) => {
    const option = el("option", null, m.label);
    option.value = m.value;
    modeSelect.appendChild(option);
  });
  // Reserved modes are visible but disabled — they never silently
  // execute another route.
  (state.modes.reserved || []).forEach((m) => {
    const option = el("option", null, m.label + " (soon)");
    option.value = m.value;
    option.disabled = true;
    modeSelect.appendChild(option);
  });

  const qualitySelect = $("qualitySelect");
  clear(qualitySelect);
  (state.modes.quality || []).forEach((q) => {
    const option = el("option", null, q.label);
    option.value = q.value;
    qualitySelect.appendChild(option);
  });

  const seedSelect = $("seedModeSelect");
  clear(seedSelect);
  (state.modes.seed || []).forEach((s) => {
    const option = el("option", null, s.label);
    option.value = s.value;
    seedSelect.appendChild(option);
  });

  modeSelect.onchange = () => { persistUiState(); applyTeachingSafety(); refreshUiState(); };
  qualitySelect.onchange = () => { persistUiState(); updateQualityHint(); };
  seedSelect.onchange = persistUiState;

  // ARCHITECTURAL_LEARNING_UI_01 — re-apply teaching safety after a rebuild.
  applyTeachingSafety();
  refreshUiState();

  return state.modes;
}

function updateQualityHint() {
  const value = $("qualitySelect").value;
  const hint = $("qualityHint");
  if (value === "QUALITY" || value === "FINAL") {
    hint.textContent = "Production resolution — explicit override.";
  } else {
    hint.textContent = "Preview keeps renders fast; the original asset is untouched.";
  }
}

function applyProjectUiState() {
  const ui = (state.project || {}).ui || {};
  if (ui.mode) $("modeSelect").value = ui.mode;
  if (ui.render_profile) $("qualitySelect").value = ui.render_profile;
  if (ui.seed_mode) $("seedModeSelect").value = ui.seed_mode;
  if (ui.seed_value) $("seedValue").value = ui.seed_value;
  updateQualityHint();
}

async function persistUiState() {
  if (!state.projectId) return;
  await api("/api/projects/" + state.projectId + "/ui", {
    method: "POST",
    body: JSON.stringify({
      mode: $("modeSelect").value,
      render_profile: $("qualitySelect").value,
      seed_mode: $("seedModeSelect").value,
      seed_value: $("seedValue").value || null,
    }),
  });
}


// ==========================================================
// CHAT
// ==========================================================

// PROJECT_HISTORY_RESTORATION_V1 — one transcript status row.
function transcriptRow(text, variant) {
  const row = el("div", "status-row " + (variant || "status-completed"));
  row.appendChild(el("span", "status-dot"));
  row.appendChild(el("span", null, text));
  return row;
}

async function loadConversation() {
  if (!state.projectId) return;

  // UNCERTAIN_TRANSCRIPT_REVIEW_V1 — a candidate belongs to the conversation
  // it was captured in and must not survive a conversation change.
  clearVoiceReview();

  const { data } = await api("/api/projects/" + state.projectId);
  if (!data) return;

  const chat = $("chatScroll");
  clear(chat);

  const recovery = data.recovery || {};
  const transcript = Array.isArray(data.transcript) ? data.transcript : [];

  // IMAGE_TURN_TRANSPORT_RECOVERY_01 — the baseline the next turn is
  // compared against.
  state.messageCount = recovery.message_count || 0;
  state.lastAssistantText = null;

  // PROJECT_HISTORY_RESTORATION_V1 — a reopened project must show its REAL
  // conversation, not only a count. Every stored turn is rendered through
  // the same `messageNode` path a live turn uses, so restored history gets
  // identical RTL/Markdown formatting. An entry with no usable role or no
  // text is skipped: nothing is invented and no placeholder bubble is made.
  let rendered = 0;
  let unavailable = 0;
  const history = document.createDocumentFragment();

  transcript.forEach((entry) => {
    if (!entry || typeof entry !== "object") return;
    const role = entry.role === "assistant" ? "assistant"
      : (entry.role === "user" ? "user" : null);
    if (!role) return;
    const text = typeof entry.text === "string" ? entry.text : "";
    const attachments = Array.isArray(entry.attachments) ? entry.attachments : [];
    // A turn is worth showing when it has text OR an attachment. An
    // image-only turn is a real turn and keeps its chronological position.
    if (!text.trim() && !attachments.length) return;
    // SENT_MESSAGE_EDIT_V1 — the stored reference and supersede mark are
    // carried into the bubble so the pencil can target the EXACT stored
    // message (never an array position) and a replaced branch is visible.
    history.appendChild(messageNode(role, text, attachments, {
      messageRef: entry.message_ref || null,
      supersededBy: entry.superseded_by || null,
    }));
    rendered += 1;
    attachments.forEach((item) => {
      if (!attachmentImageUrl(item)) unavailable += 1;
    });
  });

  if (rendered) {
    // Distinguish SAVED from VISIBLE, and report attachment availability
    // rather than implying every image was recovered.
    const stored = recovery.message_count || rendered;
    let line = "Restored " + rendered
      + (rendered === stored ? "" : " of " + stored + " saved")
      + " messages and " + (recovery.asset_count || 0)
      + " assets from this project";
    if (unavailable) {
      line += " · " + unavailable + " attachment"
        + (unavailable === 1 ? "" : "s") + " unavailable";
    }
    chat.appendChild(transcriptRow(line));
    chat.appendChild(history);

    if (recovery.ordinals && recovery.ordinals.length) {
      chat.appendChild(transcriptRow(
        "Image ordinals restored: " + recovery.ordinals.join(", ")
        + " · active #" + (recovery.active_asset_id ? "yes" : "none")));
    }

    // A restored transcript can be long — open on the most recent turn.
    chat.scrollTop = chat.scrollHeight;

  } else if (recovery.message_count) {
    // Stored messages exist but none could be rendered. Say so plainly
    // rather than reporting a successful restore.
    chat.appendChild(transcriptRow(
      recovery.message_count + " saved messages are stored for this project "
      + "but could not be loaded.", "status-failed"));

  } else {
    const empty = $("chatEmpty");
    empty.classList.remove("hidden");
    chat.appendChild(empty);
  }

  // MATERIAL_REVIEW_READONLY_UI_V1 — render a compact, READ-ONLY summary
  // of each pending material-correction review carried by the project.
  // This is visibility and continuity only: no confirm, no reject, no
  // learning.  Every field is rendered as textContent via `el()`, so no
  // user-supplied text is ever parsed as HTML.
  const reviews = Array.isArray(data.material_reviews) ? data.material_reviews : [];
  if (reviews.length) {
    chat.appendChild(renderMaterialReviews(reviews));
    chat.scrollTop = chat.scrollHeight;
  }
}

// ==========================================================
// MATERIAL_REVIEW_READONLY_UI_V1 — READ-ONLY REVIEW CARDS
//
// Renders a compact card for each pending material-correction review.
// All text is set through `el(tag, className, text)` which uses
// `textContent`, so no user-provided correction text or material label
// can inject markup.
//
// MATERIAL_REVIEW_UI_SECURITY_ACCEPTANCE_V1 — the card consumes the
// MINIMIZED display contract the Core now emits (flat fields only; the
// Core no longer sends whole carrier sub-objects).  Older nested shapes
// are still tolerated as a fallback so a stale Core cannot render an
// empty card, but nothing here requires them.
//
// The card explicitly states: "This correction has not been confirmed
// or permanently learned."  No button, no action, no endpoint.
// ==========================================================

function renderMaterialReviews(reviews) {
  const wrap = el("div", "material-reviews-wrap");

  const heading = el("div", "material-reviews-heading");
  heading.appendChild(el("span", "material-reviews-icon", "◆"));
  heading.appendChild(el("span", null, "بازبینی اصلاحات مصالح معلق"));
  wrap.appendChild(heading);

  reviews.forEach((review) => {
    if (!review || typeof review !== "object") return;
    const card = el("div", "material-review-card");

    // --- Previous observed material ---
    const prevLabel = review.previous_material_label
      || (review.previous_observation && (review.previous_observation.material_label
          || review.previous_observation.label
          || review.previous_observation.identity))
      || "—";
    card.appendChild(_reviewField("مصالح مشاهده‌شده (قبلی)", prevLabel));

    // --- Original observation confidence ---
    // Flattened `observation_confidence` is authoritative; the nested
    // shape is only a compatibility fallback.
    const observed = review.original_observation || {};
    const matObs = (observed.material_observations
      && Array.isArray(observed.material_observations)
      && observed.material_observations[0]) || {};
    const confidence = review.observation_confidence
      || matObs.confidence || "—";
    card.appendChild(_reviewField("اعتماد مشاهده", confidence));

    // --- Original observation provenance ---
    const provenance = review.observation_provenance || {};
    const provText = [
      provenance.provider,
      provenance.model,
      provenance.image_id,
    ].filter(Boolean).join(" · ") || "—";
    card.appendChild(_reviewField("منبع مشاهده", provText));

    // --- User's exact correction ---
    const correctionText = review.original_correction_text || "—";
    card.appendChild(_reviewField("اصلاح کاربر", correctionText));

    // --- Proposed corrected material ---
    const correctedLabel = review.corrected_material_label
      || (review.corrected_material && (review.corrected_material.material_label
          || review.corrected_material.label
          || review.corrected_material.identity))
      || "—";
    card.appendChild(_reviewField("مصالح اصلاح‌شده (پیشنهادی)", correctedLabel));

    // --- Review ID ---
    const reviewId = review.review_id || "—";
    card.appendChild(_reviewField("شناسه بازبینی", reviewId));

    // --- Originating project and image reference ---
    const origin = review.origin || {};
    const originProject = review.project_id || origin.project_id;
    const originImage = review.image_id
      || (origin.image_identity && origin.image_identity.image_id);
    const originText = [
      originProject ? ("پروژه: " + originProject) : null,
      originImage ? ("تصویر: " + originImage) : null,
    ].filter(Boolean).join(" · ") || "—";
    card.appendChild(_reviewField("منبع", originText));

    // --- Spatial grounding status ---
    const spatial = review.spatial_grounding || {};
    const spatialText = review.spatial_grounding_status
      || spatial.status || spatial.grounding || "UNKNOWN";
    card.appendChild(_reviewField("وضعیت مکانی", spatialText));

    // --- Execution capability status ---
    const exec = review.execution_capability || {};
    const execText = review.execution_capability_status
      || exec.status || exec.capability || "NOT_YET_AVAILABLE";
    card.appendChild(_reviewField("قابلیت اجرا", execText));

    // --- Pending-review status ---
    const lifecycle = review.lifecycle || {};
    const stateText = review.state || lifecycle.state || "pending_review";
    card.appendChild(_reviewField("وضعیت", stateText));

    // --- Explicit non-confirmation notice ---
    const notice = el("div", "material-review-notice");
    notice.textContent = "این اصلاح تأیید نشده و به‌طور دائمی یاد گرفته نشده است.";
    card.appendChild(notice);

    wrap.appendChild(card);
  });

  return wrap;
}

function _reviewField(label, value) {
  const row = el("div", "review-field-row");
  row.appendChild(el("span", "review-field-label", label));
  row.appendChild(el("span", "review-field-value", String(value)));
  return row;
}

// ==========================================================
// CHAT-02B — SAFE RTL-AWARE RICH TEXT IN THE TRANSCRIPT
//
// The bubble used to be filled with `textContent`, so an assistant
// reply arrived as one plain blob: `**bold**` showed its asterisks, a
// numbered list had no markers, no indentation and no right-aligned
// Persian layout, and a wrapped item did not line up under its text.
//
// This renders a SMALL, FIXED subset of Markdown — paragraphs, ordered
// and unordered lists, bold, italic — by BUILDING DOM NODES. `innerHTML`
// is never used and no string is ever parsed as HTML, so untrusted model
// text cannot inject markup.
//
// Every block gets `dir="auto"`, so the browser decides direction per
// block: Persian flows RTL with its markers on the right, English flows
// LTR, and a mixed Persian/English paragraph keeps both runs correct.
// ==========================================================

// `**bold**` or `*italic*` inside one line.
const RICH_INLINE = /\*\*([^*\n]+)\*\*|\*([^*\n]+)\*/g;

// Strong-directional characters. Digits and punctuation are NOT strong, so
// `۱.` alone never decides the direction of a block.
const RICH_RTL = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]/;
const RICH_LTR = /[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF]/;

function detectDirection(text) {
  // The FIRST strong character decides — exactly the bidi rule a reader
  // applies. A Persian sentence with an embedded English word stays RTL, an
  // English sentence with an embedded Persian word stays LTR.
  //
  // `dir="auto"` was tried first and is NOT sufficient here: on a list
  // container it resolved to LTR for Persian items, which put the ordered
  // marker on the left while the text sat on the right.
  const s = String(text === undefined || text === null ? "" : text);
  for (let i = 0; i < s.length; i += 1) {
    const ch = s.charAt(i);
    if (RICH_RTL.test(ch)) return "rtl";
    if (RICH_LTR.test(ch)) return "ltr";
  }
  return "rtl";   // the interface's primary language
}

// `۱. ` / `1) ` — Persian (U+06F0..U+06F9) or ASCII digits.
const RICH_ORDERED = /^\s*([0-9\u06F0-\u06F9]+)\s*[.)\u06D4]\s+(.+)$/;
// `- ` / `* ` / `• `
const RICH_BULLET = /^\s*[-*\u2022\u25CF\u00B7]\s+(.+)$/;
// a thematic break: `***`, `---`, `___` (3 or more, spaces allowed)
const RICH_RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;

function richInline(text) {
  const nodes = [];
  let last = 0;
  let match;
  RICH_INLINE.lastIndex = 0;
  while ((match = RICH_INLINE.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(document.createTextNode(text.slice(last, match.index)));
    }
    const tag = match[1] !== undefined ? "strong" : "em";
    const node = document.createElement(tag);
    node.textContent = match[1] !== undefined ? match[1] : match[2];
    nodes.push(node);
    last = RICH_INLINE.lastIndex;
  }
  if (last < text.length) nodes.push(document.createTextNode(text.slice(last)));
  return nodes;
}

function richBlock(tag, text) {
  const node = document.createElement(tag);
  node.setAttribute("dir", detectDirection(text));   // per-block bidi
  richInline(text).forEach(function (child) { node.appendChild(child); });
  return node;
}

function richList(tag) {
  const node = document.createElement(tag);
  return node;   // direction is taken from the first item added
}

// ==========================================================
// CODER-04 — SAFE FENCED CODE BLOCKS
//
// A fenced block (``` … ``` or ~~~ … ~~~) is rendered as a real
// <pre><code> so every original line, leading space and blank line is
// preserved. The body is set with `textContent`, so no Markdown emphasis is
// interpreted inside code and no string is ever parsed as HTML. The block is
// forced LTR with its own horizontal scroll. An UNCLOSED fence is not an
// error: the remaining lines become the code block (no crash).
// ==========================================================

const RICH_FENCE = /^\s*(```+|~~~+)\s*([A-Za-z0-9_+#.-]*)\s*$/;

function copyCodeText(text, button) {
  const done = function (ok) {
    if (!button) return;
    const original = button.textContent;
    button.textContent = ok ? "Copied" : "Copy failed";
    setTimeout(function () { button.textContent = original; }, 1200);
  };

  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { done(true); },
        function () { done(false); }
      );
      return;
    }
  } catch (e) { /* fall through to the legacy path */ }

  // Legacy fallback: a temporary textarea + execCommand. No innerHTML.
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand && document.execCommand("copy");
    document.body.removeChild(area);
    done(!!ok);
  } catch (e) { done(false); }
}

function renderCodeBlock(codeLines, lang) {
  const wrap = el("div", "msg-code");

  const head = el("div", "msg-code-head");
  head.appendChild(el("span", "msg-code-lang", (lang || "code")));
  const copy = el("button", "msg-code-copy", "Copy");
  copy.type = "button";
  head.appendChild(copy);
  wrap.appendChild(head);

  const pre = el("pre", "msg-code-pre");
  const code = el("code", "msg-code-body");
  code.setAttribute("dir", "ltr");
  // The EXACT source text: no fences, no trailing transform, every blank line.
  code.textContent = codeLines.join("\n");
  pre.appendChild(code);
  wrap.appendChild(pre);

  copy.addEventListener("click", function () {
    copyCodeText(code.textContent || "", copy);
  });

  return wrap;
}

function renderRichText(text) {
  const frag = document.createDocumentFragment();
  const lines = String(text === undefined || text === null ? "" : text)
    .split(/\r?\n/);
  let list = null;
  let listTag = null;

  function closeList() {
    if (list) { frag.appendChild(list); list = null; listTag = null; }
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].replace(/\s+$/, "");

    // CODER-04 — a fenced code block is collected verbatim and rendered as
    // <pre><code>. Tested BEFORE the blank / rule / bullet / paragraph logic.
    const fence = line.match(RICH_FENCE);
    if (fence) {
      closeList();
      const marker = fence[1];
      const lang = (fence[2] || "").trim();
      const code = [];
      i += 1;
      for (; i < lines.length; i += 1) {
        const closing = lines[i].match(RICH_FENCE);
        if (closing && closing[1] === marker && !(closing[2] || "").trim()) break;
        code.push(lines[i]);   // RAW line: leading indentation + blanks kept
      }
      frag.appendChild(renderCodeBlock(code, lang));
      continue;   // the loop's own i += 1 steps past the closing fence
    }

    if (!line.trim()) { closeList(); continue; }

    // A thematic break must be tested BEFORE the bullet test, because `***`
    // also starts with a bullet character.
    if (RICH_RULE.test(line)) {
      closeList();
      frag.appendChild(document.createElement("hr"));
      continue;
    }

    const ordered = line.match(RICH_ORDERED);
    const bullet = ordered ? null : line.match(RICH_BULLET);

    if (ordered || bullet) {
      const tag = ordered ? "ol" : "ul";
      const itemText = ordered ? ordered[2] : bullet[1];
      if (!list || listTag !== tag) {
        closeList();
        list = richList(tag);
        listTag = tag;
      }
      // The list takes the direction of its FIRST item, so the marker and
      // the hanging indent land on that side.
      if (!list.firstChild) list.setAttribute("dir", detectDirection(itemText));
      list.appendChild(richBlock("li", itemText));
      continue;
    }

    closeList();
    frag.appendChild(richBlock("p", line));
  }

  closeList();
  return frag;
}

// ==========================================================
// CHAT-02C.2 — ATTACHMENT TURNS IN THE TRANSCRIPT
//
// An image-only turn has no text, so `if (text)` dropped it from the
// timeline. The turn is real and its asset is real, so it now gets a bubble
// of its own, in its original chronological position.
//
// The message record is NOT trusted with a path. An attachment becomes an
// <img> only when its kind is an image kind AND its URL is a same-origin
// `/artifacts/...` path with no `..` and no scheme (our own `blob:` preview
// is the one exception, and it is created by this page). Anything else — or
// an image that fails to load — becomes a plain "unavailable" placeholder.
// No raw HTML, no inline SVG, never a fabricated image.
// ==========================================================

const ATTACHMENT_IMAGE_KINDS = ["image", "render"];

function safeAttachmentUrl(url) {
  if (typeof url !== "string") return null;
  const value = url.trim();
  if (!value) return null;
  if (value.indexOf("..") !== -1) return null;                 // no traversal
  if (/^[a-zA-Z][a-zA-Z0-9+.\-]*:/.test(value)) {              // has a scheme
    return value.slice(0, 5) === "blob:" ? value : null;       // only our blob:
  }
  if (value.charAt(0) !== "/") return null;                    // must be rooted
  if (value.slice(0, 11) !== "/artifacts/") return null;       // only the artifact route
  return value;
}

function attachmentImageUrl(attachment) {
  if (!attachment || typeof attachment !== "object") return null;
  if (ATTACHMENT_IMAGE_KINDS.indexOf(attachment.kind) === -1) return null;
  return safeAttachmentUrl(attachment.thumbnail_url || attachment.url);
}

function attachmentPlaceholder(name) {
  const box = el("div", "attach-missing");
  box.appendChild(el("span", "attach-missing-dot"));
  box.appendChild(el("span", null,
    (name || "attachment") + " — attachment unavailable"));
  return box;
}

function attachmentPreview(attachment) {
  const wrap = el("div", "attach-turn");
  const name = (attachment && (attachment.display_name || attachment.filename))
    || "attachment";
  const url = attachmentImageUrl(attachment);

  if (!url) {
    wrap.appendChild(attachmentPlaceholder(name));
    return wrap;
  }

  const img = el("img", "attach-image");
  img.alt = name;
  img.loading = "lazy";
  img.onerror = () => {
    // The asset is gone: say so, never pretend it was recovered.
    img.remove();
    wrap.appendChild(attachmentPlaceholder(name));
  };
  img.src = url;
  if (url.slice(0, 5) === "blob:") {
    img.onload = () => URL.revokeObjectURL(url);
  }
  wrap.appendChild(img);
  return wrap;
}

function attachmentNodes(attachments) {
  const nodes = [];
  const list = Array.isArray(attachments) ? attachments : [];
  list.forEach((item) => {
    if (item && typeof item === "object") nodes.push(attachmentPreview(item));
  });
  return nodes;
}

function messageNode(role, text, attachments, meta) {
  const info = meta || {};
  const wrap = el("div", "msg msg-" + role);

  if (info.supersededBy) wrap.classList.add("msg-superseded");

  const body = typeof text === "string" ? text : "";

  // SENT_MESSAGE_EDIT_V1 — the role line now also carries the revision
  // affordance. It is a real <button>, so it is reachable by Tab and
  // activatable by Enter/Space, and it is only ever offered on a USER
  // turn that has a stable server reference.
  const head = el("div", "msg-head");
  head.appendChild(el("div", "msg-role", role === "user" ? "You" : "ArchitectOS"));

  if (info.supersededBy) {
    const badge = el("span", "msg-badge", "superseded");
    badge.title = "This branch was replaced by a later revision. "
      + "It is kept for reference and is not used as active context.";
    head.appendChild(badge);
  }

  if (role === "user" && info.messageRef) {
    const pencil = el("button", "msg-edit", "✎");
    pencil.type = "button";
    pencil.title = "Edit and resubmit this message";
    pencil.setAttribute("aria-label", "Edit and resubmit this message");
    pencil.onclick = () => beginMessageEdit(wrap, info.messageRef, body);
    head.appendChild(pencil);
  }

  wrap.appendChild(head);

  const bubble = el("div", "msg-bubble");
  // CHAT-02E — only a real string is ever rendered. A structured value
  // (an object) used to reach the DOM through String() and appear as
  // "[object Object]"; it is dropped here and shown by the panel that
  // owns it instead.

  if (body.trim()) {
    if (role === "assistant") {
      // Assistant replies may contain Markdown; render the safe subset.
      bubble.appendChild(renderRichText(body));
    } else {
      // A user turn is shown verbatim.
      bubble.textContent = body;
    }
  }

  // An attachment renders even when the turn carries no text at all.
  attachmentNodes(attachments).forEach((node) => bubble.appendChild(node));

  wrap.appendChild(bubble);
  return wrap;
}


// ==========================================================
// SENT_MESSAGE_EDIT_V1 — INLINE MESSAGE REVISION
//
// The editor is built from the ALREADY RENDERED bubble, so the original
// text is what the user actually sees. Cancel restores it untouched.
// Nothing is deleted on save: the server appends a revision and marks
// the replaced branch, and the transcript is re-read from the server.
// ==========================================================

function newRevisionNonce() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return "rev-" + Date.now() + "-" + Math.random().toString(16).slice(2);
}

function beginMessageEdit(wrap, ref, originalText) {
  if (!wrap || wrap.querySelector(".msg-editor")) return;

  // The existing single-flight guard: one turn at a time, app-wide.
  if (state.turn) {
    toast("Please wait for the current turn to finish.");
    return;
  }

  const bubble = wrap.querySelector(".msg-bubble");
  if (bubble) bubble.classList.add("hidden");

  const editor = el("div", "msg-editor");

  const area = document.createElement("textarea");
  area.className = "msg-editor-input";
  area.value = originalText;
  area.rows = Math.min(8, Math.max(2, originalText.split("\n").length + 1));
  area.setAttribute("aria-label", "Edit message");

  const actions = el("div", "msg-editor-actions");
  const status = el("span", "msg-editor-status", "");
  const cancel = el("button", "btn btn-ghost btn-small", "Cancel");
  cancel.type = "button";
  const save = el("button", "btn btn-primary btn-small", "Save & Resubmit");
  save.type = "button";

  actions.appendChild(status);
  actions.appendChild(cancel);
  actions.appendChild(save);

  editor.appendChild(area);
  editor.appendChild(actions);
  wrap.appendChild(editor);

  area.focus();
  area.setSelectionRange(area.value.length, area.value.length);

  function close() {
    editor.remove();
    if (bubble) bubble.classList.remove("hidden");
  }

  cancel.onclick = close;

  area.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      submit();
    }
  });

  let busy = false;

  async function submit() {
    // Duplicate clicks and Ctrl+Enter are collapsed into ONE request.
    if (busy) return;

    const value = area.value.trim();

    if (!value) {
      status.textContent = "The message is empty.";
      return;
    }

    busy = true;
    save.disabled = true;
    cancel.disabled = true;
    area.disabled = true;
    status.textContent = "Submitting…";

    const handle = activityBegin("chat", "revision");

    try {
      // SENT_MESSAGE_EDIT_V1 — the revision has its own gateway route
      // (`/api/revise` -> Core `POST /api/revise`). It is NOT a chat turn:
      // the Core contract returns 400/404/409 for the cases the editor has
      // to report truthfully, and those codes only survive on this path.
      const { ok, data } = await api("/api/revise", {
        method: "POST",
        body: JSON.stringify({
          text: value,
          project_id: state.projectId,
          // Text-only is enforced by the SERVER; this only avoids asking
          // for something that would be refused.
          mode: "chat",
          revise_ref: ref,
          revision_nonce: newRevisionNonce(),
        }),
      });

      if (!ok || !data || data.status !== "success") {
        const reason = (data && (data.message || data.error)) || "Revision failed";
        throw new Error(reason);
      }

      handle.finish();
      close();
      await loadConversation();
      toast("Message revised");
    } catch (error) {
      handle.fail();
      status.textContent = String((error && error.message) || error);
      save.disabled = false;
      cancel.disabled = false;
      area.disabled = false;
      busy = false;
    }
  }

  save.onclick = submit;
}

// OPERATION_VISIBILITY_UI_01 — the old in-transcript render row was
// replaced by the centralized header activity pill (see the ACTIVITY
// ENGINE above). The transcript is reserved for real conversation: the
// status of a long operation is shown once, in the header, and is
// cleared on settle. `renderStatusRow` is therefore no longer used.


// ==========================================================
// ARCHITECTURAL_LEARNING_UI_01 — VISIBLE STATE + TEACHING SAFETY
// ==========================================================
//
// UI-ONLY. The state is derived on the client from the selected mode,
// an attached image, the explicit teaching toggle and whether a turn is
// in flight. No backend call and no route change: the UI never guesses a
// Core route, and TEACHING can never enter GENERATING.

const UI_STATES = ["CHAT", "TEACHING", "OBSERVATION", "LEARNING", "GENERATING"];

// The mode values the backend already exposes (render_strategy_controller_v1).
// Kept local so the UI classifies without a backend change.
const GENERATION_MODES = [
  "text_to_image", "image_to_image", "text_to_video", "image_to_video",
];
const OBSERVATION_MODES = ["analyze_image"];

const STATE_HINTS = {
  CHAT: "",
  TEACHING: "Teaching — stored as a candidate, never a design.",
  OBSERVATION: "Observation — reading the image, not designing.",
  LEARNING: "Learning — extracting knowledge.",
  GENERATING: "Generating — a design turn.",
};

const OPERATION_LABELS = {
  CHAT: "در حال تحلیل درخواست",
  TEACHING: "در حال یادگیری",
  OBSERVATION: "در حال پردازش تصویر",
  LEARNING: "در حال یادگیری",
  GENERATING: "در حال رندر",
};

function currentMode() {
  const node = $("modeSelect");
  return node ? node.value : "chat";
}

function setUiState(name, hint) {
  if (UI_STATES.indexOf(name) === -1) name = "CHAT";
  state.uiState = name;
  const chip = $("stateChip");
  if (chip) {
    chip.textContent = name;
    chip.className = "state-chip state-" + name.toLowerCase();
  }
  const hintNode = $("stateHint");
  if (hintNode) hintNode.textContent = hint || "";
}

// The single source of truth for the visible state.
function deriveUiState() {
  const mode = currentMode();
  if (state.turn) {
    if (state.teaching) return "LEARNING";
    if (state.attachFile || OBSERVATION_MODES.indexOf(mode) !== -1) return "OBSERVATION";
    if (GENERATION_MODES.indexOf(mode) !== -1) return "GENERATING";
    return "CHAT";
  }
  if (state.teaching) return "TEACHING";
  if (state.attachFile || OBSERVATION_MODES.indexOf(mode) !== -1) return "OBSERVATION";
  return "CHAT";
}

function refreshUiState() {
  const name = deriveUiState();
  setUiState(name, STATE_HINTS[name] || "");
}

// TEACHING SAFETY (UI-ONLY): while teaching, the composer must not be on a
// generation mode, and the generation options are disabled. The user's
// explicit mode is remembered and restored when teaching is turned off.
// Each option THIS toggle disabled is MARKED, so re-applying the safety
// (e.g. after loadModes rebuilds the select) stays idempotent, and the
// backend's own "reserved" (already-disabled) modes are never enabled.
let _modeBeforeTeaching = null;

function applyTeachingSafety() {
  const sel = $("modeSelect");
  if (!sel) return;
  const options = Array.from(sel.options || []);
  if (state.teaching) {
    if (_modeBeforeTeaching === null) _modeBeforeTeaching = sel.value;
    options.forEach((o) => {
      if (GENERATION_MODES.indexOf(o.value) !== -1 && !o.disabled) {
        o.disabled = true;
        o._teachingDisabled = true;
      }
    });
    if (GENERATION_MODES.indexOf(sel.value) !== -1) sel.value = "chat";
  } else {
    options.forEach((o) => {
      if (o._teachingDisabled) {
        o.disabled = false;
        o._teachingDisabled = false;
      }
    });
    if (_modeBeforeTeaching) {
      const exists = options.some((o) => o.value === _modeBeforeTeaching);
      if (exists) sel.value = _modeBeforeTeaching;
    }
    _modeBeforeTeaching = null;
  }
}

function toggleTeaching() {
  state.teaching = !state.teaching;
  const btn = $("teachToggle");
  if (btn) btn.classList.toggle("active", state.teaching);
  applyTeachingSafety();
  refreshUiState();
}

// ---- turn controls (Stop / Cancel / Retry) ----

function showTurnControls(on) {
  const row = $("turnControls");
  if (row) row.classList.toggle("hidden", !on);
}

function setTurnState(text) {
  const node = $("turnState");
  if (node) node.textContent = text;
}

function setRetryVisible(on) {
  const node = $("retryBtn");
  if (node) node.classList.toggle("hidden", !on);
}

// Auto-grow the composer textarea (UI-ONLY).
function autoGrowMessage() {
  const node = $("message");
  if (!node || node.tagName !== "TEXTAREA") return;
  node.style.height = "auto";
  const max = 240;
  node.style.height = Math.min(node.scrollHeight, max) + "px";
  node.style.overflowY = node.scrollHeight > max ? "auto" : "hidden";
}

function stopTurn() {
  if (!state.turn) return;
  const turn = state.turn;
  // Restore the draft so the user can edit / retry after stopping.
  const input = $("message");
  if (input && turn.text) input.value = turn.text;
  if (turn.files && turn.files.length) {
    state.attachFiles = turn.files;
    state.attachFile = turn.files[0];
  } else if (turn.file) {
    state.attachFile = turn.file;
  }
  if (typeof autoGrowMessage === "function") autoGrowMessage();
  try { turn.controller.abort(); } catch (e) { /* ignore */ }
}

function cancelTurn() {
  if (!state.turn) return;
  const turn = state.turn;
  try { turn.controller.abort(); } catch (e) { /* ignore */ }
  const input = $("message");
  if (input) input.value = "";
  if (typeof autoGrowMessage === "function") autoGrowMessage();
  state.attachFile = null;
  state.attachFiles = [];
  if (typeof clearAttachment === "function") clearAttachment();
}

function retryTurn() {
  if (!state.lastSent) return;
  const input = $("message");
  if (input) input.value = state.lastSent.text || "";
  if (state.lastSent.files && state.lastSent.files.length) {
    state.attachFiles = state.lastSent.files;
    state.attachFile = state.lastSent.files[0];
  } else if (state.lastSent.file) {
    state.attachFile = state.lastSent.file;
  }
  if (typeof autoGrowMessage === "function") autoGrowMessage();
  sendMessage();
}


function renderCard(attachment, meta) {
  const card = el("div", "render-card");

  const img = el("img");
  img.src = attachment.thumbnail_url || attachment.url;
  img.alt = attachment.display_name || "render";
  card.appendChild(img);

  const body = el("div", "render-card-body");

  body.appendChild(el("div", "render-card-title", meta.title || "Render"));

  const parts = [];
  if (meta.ordinal) parts.push("Image #" + meta.ordinal);
  if (meta.parentOrdinal) parts.push("Derived from Image #" + meta.parentOrdinal);
  if (meta.profile) parts.push(meta.profile);
  if (meta.mode) parts.push(meta.mode);
  body.appendChild(el("div", "render-card-sub", parts.join(" · ")));

  const actions = el("div", "render-card-actions");

  const detailsBtn = el("button", "btn btn-ghost btn-small", "Details");
  detailsBtn.onclick = () => showAssetDetails(meta.assetId);
  actions.appendChild(detailsBtn);

  if (meta.assetId) {
    const activeBtn = el("button", "btn btn-ghost btn-small", "Set Active");
    activeBtn.onclick = () => setActiveAsset(meta.assetId);
    actions.appendChild(activeBtn);

    const finalBtn = el("button", "btn btn-ghost btn-small", "Mark Final");
    finalBtn.onclick = () => markFinal(meta.assetId, true);
    actions.appendChild(finalBtn);
  }

  body.appendChild(actions);
  card.appendChild(body);

  return card;
}

async function sendMessage() {
  if (state.turn) return; // one turn at a time

  const input = $("message");
  const text = input.value.trim();
  const file = state.attachFile;
  // FACADE-02 — ordered A/B attachments (index 0 = A style reference,
  // index 1 = B target building). Falls back to the legacy single file.
  const files = (state.attachFiles && state.attachFiles.length)
    ? state.attachFiles.slice(0, MAX_ATTACH)
    : (file ? [file] : []);

  if (!text && !files.length) return;

  // PRECISE_EDIT_UI_V1 — a localized edit without a mask would fall through
  // to a whole-image redesign. Refuse it here and say why, instead of letting
  // the user believe a precise change was requested.
  const localizedToggle = $("localizedEditToggle");
  const maskInput = $("maskFile");
  const wantsLocalized = !!(localizedToggle && localizedToggle.checked);
  const maskFile = (wantsLocalized && maskInput && maskInput.files)
    ? (maskInput.files[0] || null)
    : null;

  if (wantsLocalized && !maskFile) {
    toast("Choose a mask image, or untick “Localized edit (mask)”.", 4200);
    return;
  }

  if (maskFile && !files.length) {
    toast("A mask needs the image it belongs to — attach that image too.", 4200);
    return;
  }

  // PERSIAN_VOICE_QUALITY_V2 / PHASE 1 — the dictated transcript is now
  // being sent through the normal path, so the "ready to edit" notice
  // has served its purpose. This is the ONLY place it clears via send;
  // the transcript itself is untouched and already on the DOM node.
  if (state.voice.status === "dictated") clearVoiceState();

  // ARCHITECTURAL_LEARNING_UI_01 — remember this turn so Retry works.
  state.lastSent = { text, file, files };

  const chat = $("chatScroll");
  const empty = $("chatEmpty");
  if (empty) empty.classList.add("hidden");

  // CHAT-02C.2 — a live image turn with no caption is still a real turn, so
  // it gets the same bubble contract as a restored one. The preview comes
  // from a page-owned object URL, never from a server path.
  // FACADE-02 — both A/B images are previewed, each labelled with its role.
  const liveAttachments = files.map((f, i) => ({
    kind: "image",
    display_name: files.length > 1
      ? ((i === 0 ? "A (style): " : "B (target): ") + f.name)
      : f.name,
    url: URL.createObjectURL(f),
  }));
  if (text || liveAttachments.length) {
    chat.appendChild(messageNode("user", text, liveAttachments));
  }

  input.value = "";
  autoGrowMessage();
  $("sendBtn").disabled = true;

  // ARCHITECTURAL_LEARNING_UI_01 — an AbortController lets Stop/Cancel
  // halt the request; the state engine shows what the turn IS.
  const controller = new AbortController();
  state.turn = { controller, text, file, files };
  applyTeachingSafety();
  refreshUiState();

  showTurnControls(true);
  setRetryVisible(false);
  setTurnState((OPERATION_LABELS[state.uiState] || "در حال انجام") + "…");

  // IMAGE_TURN_TRANSPORT_RECOVERY_01 — a vision turn can run for tens of
  // seconds. Remember how much the server had stored BEFORE this turn so
  // a lost response can be told apart from an answer to an older turn.
  const beforeCount = state.messageCount;

  // OPERATION_VISIBILITY_UI_01 — the visible operation is derived from
  // what the turn IS, so the user sees the truth in the header pill for
  // the ENTIRE duration (a render turn shows "در حال رندر…" until the
  // synchronous render request actually settles). Elapsed time is owned
  // by the activity engine.
  const isGenerating = GENERATION_MODES.indexOf(currentMode()) !== -1;
  const attachIsImage = files.length > 0
    && String(files[0].type || "").indexOf("image") === 0;

  const chatKey = isGenerating ? "render"
    : attachIsImage ? "file_process"
    : "chat";
  const chatDetail = $("qualitySelect").value;
  const handle = activityBegin(chatKey, chatDetail);

  // REAL_SAMPLING_PROGRESS_B_PLUS — CHAT-MODE RENDER COVERAGE (CORRECTED)
  //
  // The server can submit a ComfyUI job from ordinary chat mode:
  // approved-design follow-ups, dual-image generation, and image
  // editing classified from natural language. A TEXT-ONLY approved
  // design follow-up carries no image and is not a generation mode,
  // so the previous `isGenerating || attachIsImage` test missed it.
  //
  // The watcher therefore runs for EVERY in-flight turn. It never
  // classifies a message as a render job: it stays silent until the
  // server reports a real render for THIS project, and only then takes
  // over the pill. `expectRender` only decides whether "preparing" is
  // shown during the build phase before the job exists.
  //
  // We deliberately do NOT wait for a `render_expected` flag in the
  // final response — by then the render has already finished.
  const expectsRenderEvidence = isGenerating || attachIsImage;

  const statusPoller = startRenderWatcher(
    handle,
    state.projectId,
    activity.current,
    {
      expectRender: expectsRenderEvidence,
      // A speculative watcher polls more slowly: it is only waiting for
      // server evidence, so there is nothing to gain from a tight loop.
      intervalMs: expectsRenderEvidence ? RENDER_STATUS_POLL_MS : 2000,
    }
  );

  try {
    let data = null;

    // RENDER_RUNTIME_RECOVERY_V1 — the HTTP outcome must be captured.
    // `data` alone cannot distinguish a failed render from a completed
    // one: the Core returns HTTP 200 with a `status: "error"` envelope,
    // and a transport failure returns no envelope at all. Both used to
    // reach the success branch.
    let httpOk = true;

    if (files.length) {
      const form = new FormData();
      // FACADE-02 — explicit role-bearing fields. Two images are sent as
      // image_a (style reference) + image_b (target building); a single
      // image keeps the legacy `image` field unchanged.
      if (files.length >= 2) {
        form.append("image_a", files[0]);
        form.append("image_b", files[1]);
      } else {
        form.append("image", files[0]);
      }
      form.append("text", text);
      form.append("project_id", state.projectId);
      form.append("mode", $("modeSelect").value);
      form.append("quality", $("qualitySelect").value);
      form.append("seed_mode", $("seedModeSelect").value);
      if ($("seedValue").value) form.append("seed_value", $("seedValue").value);

      // I2I_CONCEPTUAL_ADMISSION_V1 — explicit per-request consent for a
      // CONCEPTUAL architectural appearance edit. Only this control can send
      // it; message text never can.
      const conceptualToggle = $("conceptualToggle");
      if (conceptualToggle && conceptualToggle.checked) {
        form.append("conceptual_edit", "1");
      }

      // FACADE-04D.3C-0 — EXPLICIT user opt-in for the CONDITIONED facade
      // render. Sent ONLY when the user ticked the control AND both role
      // images are present. It is never inferred from message text, and the
      // server re-validates it independently.
      //
      // REFERENCE_TRANSFER_POLICY_V1 — TRI-STATE, and only when the user has
      // actually expressed a choice. An untouched toggle sends nothing, which
      // authorises the server to derive the graph from the reference-transfer
      // intent; ticking sends "1"; ticking then unticking sends an explicit
      // "0" that suppresses derivation.
      const conditionedToggle = $("conditionedToggle");
      if (conditionedToggle && files.length >= 2 && conditionedToggle.dataset.touched === "1") {
        form.append("conditioned_render", conditionedToggle.checked ? "1" : "0");
      }

      // PRECISE_EDIT_UI_V1 — the mask travels as BYTES under a field the
      // server owns; the client never names a path. `kontext_edit` selects
      // the GPU-verified Kontext graph that honours the mask.
      if (maskFile) {
        form.append("mask", maskFile, maskFile.name || "mask.png");
        form.append("kontext_edit", "1");
      }

      // VISUAL_REFERENCE_UX_V2 — the selected reference travels as an ID.
      // The browser never names a path; the Core resolves it through the
      // accepted index and re-verifies the file digest.
      if (state.referenceId) form.append("reference_id", state.referenceId);

      // OPERATION_VISIBILITY_UI_01 — an attached file is uploaded AND
      // then processed. The upload is a genuinely distinct phase, so it
      // is shown first and the SAME operation is relabelled to
      // "processing" once the request body has been handed to the
      // transport (after which the server is processing, not the client
      // uploading). Only one operation is ever visible.
      //
      // REAL_OPERATION_PROGRESS_V1 — the upload now reports the bytes the
      // browser actually transmitted. `opRef` pins this turn to the
      // activity object that was created for it: if a newer operation
      // has replaced it, a late progress event is dropped instead of
      // repainting somebody else's progress.
      const opRef = activity.current;
      if (!isGenerating) activityRelabel("file_upload");
      const response = await uploadWithProgress("/api/chat", form, {
        signal: controller.signal,
        onProgress: (progress) => {
          if (activity.current !== opRef) return; // superseded
          const detail = formatUploadProgress(progress);
          if (isGenerating) {
            handle.update(detail);
          } else {
            activityRelabel("file_upload", detail);
          }
        },
        onUploaded: () => {
          if (activity.current !== opRef) return;
          // The body is on the wire. From here the wait is the SERVER's,
          // and it is genuinely indeterminate — no percentage is shown.
          const detail = "ارسال شد — در انتظار پاسخ سرور";
          if (isGenerating) {
            activityRelabel("render", detail);
          } else {
            activityRelabel("file_process", detail);
          }
        },
      });
      httpOk = !!response.ok;
      data = response.data;
      clearAttachment();
    } else {
      const result = await api("/api/chat", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          text,
          project_id: state.projectId,
          mode: $("modeSelect").value,
          quality: $("qualitySelect").value,
          seed_mode: $("seedModeSelect").value,
          seed_value: $("seedValue").value || null,
          // I2I_CONCEPTUAL_ADMISSION_V1
          conceptual_edit: !!($("conceptualToggle") && $("conceptualToggle").checked),
          // VISUAL_REFERENCE_UX_V2 — explicit reference selection (ID only).
          reference_id: state.referenceId || null,
        }),
      });
      httpOk = !!result.ok;
      data = result.data;
    }

    const routing = data && data.routing ? data.routing : {};
    if (routing.mode) handle.update(routing.mode);

    // ==================================================
    // RENDER_RUNTIME_RECOVERY_V1 — TRUTHFUL COMPLETION
    //
    // The previous version finished every non-aborted turn with the
    // render success label as soon as `isGenerating` was true. A render
    // that the Core reported as `status: "error"` (HTTP 200) was
    // therefore announced as «رندر انجام شد», and a transport failure
    // with no envelope was announced the same way.
    //
    // A render is now reported successful ONLY when the transport
    // succeeded AND the server did not report an error. Anything else
    // settles through the SAME activity engine's failure path, which
    // already owns the per-operation failure label.
    // ==================================================
    const responseStatus = String((data && data.status) || "").toLowerCase();
    const serverError = responseStatus === "error" || !!(data && data.error);
    const renderFailed = !httpOk || serverError;

    if (renderFailed) {
      // `fail()` resolves its own label from ACTIVITY_FAIL_LABELS for the
      // current operation key — "رندر ناموفق بود." for a render.
      handle.fail();
    } else if (isGenerating) {
      handle.finish("رندر انجام شد");
    } else {
      handle.finish();
    }

    // OFFLINE_DEGRADED_STATUS_UI_V1 — a reply carries the truthful
    // degraded metadata when the local reasoning engine was unavailable.
    // Surface it in the persistent pill (never in the transcript).
    noteChatConnectivity(data);

    await handleChatResponse(data, chat);

    // ---- TTS reply (PERSIAN_TTS_V1 — language-aware) ----
    // A Persian reply is spoken by the server-side Persian provider; an
    // English reply keeps the browser's own speechSynthesis. Gated by the
    // same `voice_reply` setting as the microphone path.
    const typedReply = ((data || {}).response || {}).result
      || ((data || {}).response || {}).message || "";
    if (typedReply) {
      maybeSpeak(typedReply);
    }

  } catch (error) {
    // ARCHITECTURAL_LEARNING_UI_01 — an ABORTED turn is a NON-EVENT:
    // nothing is written, so the draft was restored by stopTurn() and
    // there is nothing to recover. Report it plainly and stop.
    if (error && (error.name === "AbortError" || controller.signal.aborted)) {
      handle.finish("لغو شد");
      return;
    }

    // OPERATION_VISIBILITY_UI_01 — a truthful per-operation failure.
    handle.fail();

    // ==================================================
    // IMAGE_TURN_TRANSPORT_RECOVERY_01
    //
    // The Core stores every turn it answers. A lost HTTP response (a
    // long vision turn is the usual case) used to surface as a bare
    // "Request failed" while the answer sat in the project — the turn
    // looked unread. Re-read the project and show what the server
    // actually recorded; report the transport failure only when there
    // is genuinely nothing recorded for this turn.
    // ==================================================
    let recovered = false;

    try {
      recovered = await recoverLostTurn(chat, beforeCount);
    } catch (e) {
      recovered = false;
    }

    if (!recovered) {
      chat.appendChild(messageNode("assistant", "Request failed: " + error));
    }

    // A failed turn can be retried.
    setRetryVisible(true);

  } finally {
    state.turn = null;
    // REAL_RENDER_LIFECYCLE_V1 — the turn is over (success, failure or
    // abort), so nothing may keep polling for it.
    if (statusPoller) statusPoller.stop();
    $("sendBtn").disabled = false;
    showTurnControls(false);
    refreshUiState();
    chat.scrollTop = chat.scrollHeight;

    // The refresh must never turn a completed turn into an unhandled
    // rejection, and must never hide a recovery that already happened.
    try { await loadAssets(); } catch (e) { /* transient — retried on demand */ }
    try { await refreshProjectMeta(); } catch (e) { /* transient — retried on demand */ }
  }
}


// ==========================================================
// IMAGE_TURN_TRANSPORT_RECOVERY_01
// ==========================================================

async function recoverLostTurn(chat, beforeCount) {
  if (!state.projectId) return false;
  if (typeof beforeCount !== "number") return false;

  // A dropped connection is often momentary, so the read-back is tried
  // a few times before the turn is reported as failed.
  let data = null;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const result = await api("/api/projects/" + state.projectId);
      if (result && result.data) { data = result.data; break; }
    } catch (e) {
      data = null;
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }

  if (!data) return false;

  const recovery = (data && data.recovery) || {};
  const count = recovery.message_count;

  // Only a turn the server recorded AFTER this send counts. Anything
  // else could be an answer to an older question.
  if (typeof count !== "number" || count <= beforeCount) return false;

  const reply = recovery.last_assistant_message;
  if (!reply) return false;
  if (reply === state.lastAssistantText) return false;

  state.messageCount = count;
  state.lastAssistantText = reply;

  chat.appendChild(messageNode("assistant", reply));
  chat.appendChild(noteNode(
    "The connection dropped while this turn was being delivered. "
    + "The answer above was recorded by ArchitectOS and restored from "
    + "this project — nothing was lost."
  ));

  return true;
}


function noteNode(text) {
  const row = el("div", "status-row status-completed");
  row.appendChild(el("span", "status-dot"));
  row.appendChild(el("span", null, text));
  return row;
}

// ==========================================================
// MULTIFLOOR_ENGINE_V2_CHAT_PLAN_ROUTING — inline plan sheet.
//
// Built as DOM nodes and an <img src> on the same-origin drawing
// route. No innerHTML anywhere: the sheet is a generated SVG
// document, not trusted markup.
// ==========================================================
// ==========================================================
// KROCKI_SITE_UPLOAD_V27
//
// Upload the land survey (کروکی زمین) as DXF/DWG. The server parses the
// parcel and stores it as a SESSION SITE FACT, so the next design turn
// builds on the real plot. The UI's only jobs are: send the file, show the
// returned summary + preview, and keep the active parcel visible with an
// explicit way to clear it.
// ==========================================================

function bindKrockiUpload() {
  const button = $("btn-upload-krocki");
  const input = $("input-krocki-file");

  if (!button || !input) return;

  button.onclick = () => {
    if (!state.projectId) {
      toast("اول یک پروژه باز کنید.");
      return;
    }
    input.value = "";
    input.click();
  };

  input.onchange = () => {
    const file = input.files && input.files[0];
    if (file) uploadKrocki(file);
  };

  refreshKrockiState();
}

function renderKrockiChip(info) {
  const chip = $("krockiChip");
  if (!chip) return;

  clear(chip);

  if (!info) {
    chip.classList.add("hidden");
    return;
  }

  const width = info.width_m;
  const length = info.length_m;

  const label = el(
    "span",
    null,
    "✅ کروکی فعال: " + width + "×" + length + " متر"
  );
  chip.appendChild(label);

  const clearButton = el("button", "btn btn-ghost btn-small", "×");
  clearButton.type = "button";
  clearButton.title = "حذف کروکی فعال";
  clearButton.onclick = clearKrockiSite;
  chip.appendChild(clearButton);

  chip.classList.remove("hidden");
}

async function refreshKrockiState() {
  if (!state.projectId) {
    renderKrockiChip(null);
    return;
  }

  const { ok, data } = await api(
    "/api/site/krocki?project_id=" + encodeURIComponent(state.projectId)
  );

  renderKrockiChip(ok && data ? data.active_site_krocki : null);

  // Keep the chat bridge in step with the server's view.
  window.activeSiteKrocki = (ok && data && data.active_site_krocki)
    ? Object.assign({ source: "server_parsed" }, data.active_site_krocki)
    : null;
}

async function clearKrockiSite() {
  if (!state.projectId) return;

  await api(
    "/api/site/krocki?project_id=" + encodeURIComponent(state.projectId),
    { method: "DELETE" }
  );

  renderKrockiChip(null);

  window.activeSiteKrocki = null;

  toast("کروکی فعال حذف شد.");
}

// ==========================================================
// KROCKI_LOCAL_FALLBACK_V27_2
//
// Defence in depth. The gateway now proxies the upload, so a 404 should not
// happen — but a deployment whose :3000 build predates the proxy would leave
// the user with nothing. In that case the parcel is derived IN THE BROWSER
// and clearly labelled as a local estimate: a filename like `12x22` is a
// guess, not a survey, and must never look like one.
// ==========================================================

function krockiDimsFromDxfText(text) {
  const lines = String(text || "").split(/\r?\n/);
  const xs = [];
  const ys = [];
  let pendingX = null;

  for (let i = 0; i + 1 < lines.length; i += 2) {
    const code = lines[i].trim();
    const value = lines[i + 1];

    if (code === "10") {
      const parsed = parseFloat(value);
      pendingX = isFinite(parsed) ? parsed : null;
    } else if (code === "20" && pendingX !== null) {
      const parsed = parseFloat(value);
      if (isFinite(parsed)) {
        xs.push(pendingX);
        ys.push(parsed);
      }
      pendingX = null;
    }
  }

  if (xs.length < 2) return null;

  const spanX = Math.max.apply(null, xs) - Math.min.apply(null, xs);
  const spanY = Math.max.apply(null, ys) - Math.min.apply(null, ys);

  if (!(spanX > 0) || !(spanY > 0)) return null;

  // Drawings are routinely in millimetres; a parcel larger than 500 m is not
  // a parcel. Normalise the same way the server does.
  const scale = Math.max(spanX, spanY) > 500 ? 0.001 : 1.0;

  const width = +(Math.min(spanX, spanY) * scale).toFixed(2);
  const length = +(Math.max(spanX, spanY) * scale).toFixed(2);

  return { width_m: width, length_m: length, source: "dxf_bbox" };
}

function krockiDimsFromFilename(name) {
  const match = String(name || "").match(/(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)/);

  if (!match) return null;

  const a = parseFloat(match[1]);
  const b = parseFloat(match[2]);

  if (!(a > 0) || !(b > 0)) return null;

  return {
    width_m: +Math.min(a, b).toFixed(2),
    length_m: +Math.max(a, b).toFixed(2),
    source: "filename",
  };
}

async function buildLocalKrocki(file) {
  let dims = null;

  if (/\.dxf$/i.test(file.name || "")) {
    try {
      dims = krockiDimsFromDxfText(await file.text());
    } catch (error) {
      dims = null;
    }
  }

  if (!dims) dims = krockiDimsFromFilename(file.name);

  // Last resort: the product's own default parcel, so the badge is never
  // empty. `source` says it was assumed.
  if (!dims) dims = { width_m: 10, length_m: 20, source: "default_parcel" };

  const width = dims.width_m;
  const length = dims.length_m;

  return {
    width_m: width,
    length_m: length,
    area_m2: +(width * length).toFixed(2),
    north_angle_deg: 0,
    street_side: "south",
    boundary_points_m: [[0, 0], [width, 0], [width, length], [0, length]],
    source_filename: file.name || "",
    source: "browser_local_estimate",
    estimate_source: dims.source,
  };
}

// KROCKI_CHAT_INJECT_V27_2 — carry the locally-derived parcel into /api/chat.
// Wraps fetch once; never rewrites a request it does not understand.
(function installActiveSiteKrockiBridge() {
  if (window.__architectosKrockiBridge) return;

  window.__architectosKrockiBridge = true;

  const originalFetch = window.fetch.bind(window);

  window.fetch = function (input, init) {
    try {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      const site = window.activeSiteKrocki;

      if (site && url.indexOf("/api/chat") !== -1 && init && typeof init.body === "string") {
        const payload = JSON.parse(init.body);

        if (payload && typeof payload === "object" && !payload.active_site_krocki) {
          payload.active_site_krocki = site;
          init = Object.assign({}, init, { body: JSON.stringify(payload) });
        }
      }
    } catch (error) {
      // A request that cannot be inspected is sent untouched.
    }

    return originalFetch(input, init);
  };
})();


// KROCKI_CHAT_TUNNEL_V27_3 — upload through `/api/chat` when the dedicated
// route is unreachable. `/api/chat` is already proxied and authenticated
// between :3000 and :5000, so it survives a gateway build with no krocki
// route. The file is base64 because that transport is JSON.
async function krockiViaChatTunnel(file) {
  let encoded;

  try {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    const chunk = 0x8000;
    let binary = "";

    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }

    encoded = btoa(binary);
  } catch (error) {
    return null;
  }

  let response;

  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "upload_krocki",
        krocki_upload_only: true,
        krocki_filename: file.name || "krocki.dxf",
        krocki_content_b64: encoded,
        project_id: state.projectId || "default",
        text: "",
      }),
    });
  } catch (error) {
    return null;
  }

  let data = null;
  try { data = await response.json(); } catch (e) { data = null; }

  if (!response.ok || !data) return null;

  const accepted = data.status === "success" || data.ok === true || !!data.krocki_info;

  return accepted ? data : null;
}


async function uploadKrocki(file) {
  if (!state.projectId) {
    toast("اول یک پروژه باز کنید.");
    return;
  }

  const form = new FormData();
  form.append("file", file);
  form.append("project_id", state.projectId);

  toast("در حال خواندن کروکی…");

  let response;
  try {
    response = await fetch(
      "/api/site/upload_krocki?project_id=" + encodeURIComponent(state.projectId),
      { method: "POST", body: form }
    );
  } catch (error) {
    toast("ارسال فایل کروکی ناموفق بود.");
    return;
  }

  let data = null;
  try { data = await response.json(); } catch (e) { data = null; }

  const chat = $("chat");

  // KROCKI_RESPONSE_ACCEPT_V27_1 — a successful upload is recognised by ANY
  // of the three shapes the server and its older clients use. Requiring one
  // exact field is how a working upload got reported as a failure.
  const accepted = !!data
    && (data.status === "success" || data.ok === true || !!data.krocki_info);

  if (!response.ok || !accepted) {
    // KROCKI_CHAT_TUNNEL_V27_3 — the dedicated route is missing on this
    // :3000 build. Tunnel the SAME file through /api/chat, which is already
    // proxied to the Core API, so the real parser still sees it.
    if (response.status === 404) {
      const tunneled = await krockiViaChatTunnel(file);

      if (tunneled) {
        const tunnelInfo = tunneled.krocki_info || tunneled.site || {};
        const tunnelSummary = tunneled.reply || tunneled.message || tunnelInfo.summary_fa || "";

        window.activeSiteKrocki = Object.assign({ source: "server_parsed" }, tunnelInfo);

        renderKrockiChip(tunnelInfo);

        if (chat) {
          chat.appendChild(messageNode("assistant", tunnelSummary || "کروکی زمین ثبت شد."));

          if (tunneled.preview_url) {
            const frame = el("div", "plan-drawing-frame");
            const img = document.createElement("img");
            img.className = "plan-drawing-image";
            img.alt = "پیش‌نمایش کروکی زمین";
            img.loading = "lazy";
            img.src = String(tunneled.preview_url);
            frame.appendChild(img);
            chat.appendChild(frame);
          }

          chat.scrollTop = chat.scrollHeight;
        }

        toast("کروکی زمین ثبت شد.");

        return;
      }

      // Last resort: derive the parcel in the browser. Labelled as an
      // ESTIMATE — a filename like `12x22` is a guess, not a survey.
      const local = await buildLocalKrocki(file);

      window.activeSiteKrocki = local;

      renderKrockiChip({ width_m: local.width_m, length_m: local.length_m });

      if (chat) {
        chat.appendChild(messageNode(
          "assistant",
          "📐 کروکی به‌صورت محلی خوانده شد (تخمین مرورگر، نه تحلیل سرور): "
            + local.width_m + "×" + local.length_m + " متر"
            + " — منبع: " + local.estimate_source
            + "\nاین ابعاد در درخواست بعدی به سرور ارسال می‌شود."
        ));
        chat.scrollTop = chat.scrollHeight;
      }

      toast("کروکی به‌صورت محلی ثبت شد (تخمین).");

      return;
    }

    // Surface the SERVER's reason. A generic «خواندن کروکی ناموفق بود» hides
    // the one detail the user needs: wrong file, missing DWG converter, or
    // geometry the reader could not close.
    const reason = (data && (data.message || data.error || data.detail))
      || ("خطای سرور (HTTP " + response.status + ")");

    if (chat) {
      chat.appendChild(messageNode("assistant", "⚠️ " + reason));
      chat.scrollTop = chat.scrollHeight;
    }
    toast(reason);
    return;
  }

  const info = data.krocki_info || {};

  const summary = data.reply || data.summary_fa || info.summary_fa || "";

  // KROCKI_CHAT_INJECT_V27_2 — the chat bridge forwards whatever is here.
  window.activeSiteKrocki = Object.assign({ source: "server_parsed" }, info);

  renderKrockiChip(info);

  if (chat) {
    chat.appendChild(messageNode("assistant", summary || "کروکی زمین ثبت شد."));

    if (data.preview_url) {
      const frame = el("div", "plan-drawing-frame");
      const img = document.createElement("img");
      img.className = "plan-drawing-image";
      img.alt = "پیش‌نمایش کروکی زمین";
      img.loading = "lazy";
      img.src = String(data.preview_url);
      frame.appendChild(img);
      chat.appendChild(frame);
    }

    if (data.saved_path) {
      const meta = el("div", "plan-drawing-meta");
      const row = el("div", "plan-drawing-path");
      row.appendChild(el("span", "plan-drawing-tag", "DXF"));
      row.appendChild(el("code", null, String(data.saved_path)));
      meta.appendChild(row);
      chat.appendChild(meta);
    }

    chat.scrollTop = chat.scrollHeight;
  }

  toast("کروکی زمین ثبت شد.");
}


// KROCKI_PUBLIC_API_V27_3 — embedding pages and tests call this by name.
window.uploadKrockiFile = uploadKrocki;


function planDrawingNode(drawing) {
  const wrap = el("div", "plan-drawing");

  const frame = el("div", "plan-drawing-frame");
  const img = document.createElement("img");
  img.className = "plan-drawing-image";
  img.alt = "پلان مبلمان‌شده معماری";
  img.loading = "lazy";
  img.decoding = "async";
  // PLAN_SHEET_PNG_V1 — prefer the raster sheet: it has a fixed intrinsic
  // size, so the bubble does not reflow while an SVG document loads. The
  // SVG remains the fallback for a host with no rasteriser.
  img.src = String(
    drawing.png_url || drawing.image_url || drawing.svg_url || ""
  );
  frame.appendChild(img);
  wrap.appendChild(frame);

  // PLAN_SHEET_DOWNLOADS_V1 — served, clickable links. An absolute
  // filesystem path is not something a browser can open, so it is only
  // shown when the server could not produce a URL for that artefact.
  const downloads = (drawing.downloads || []).filter((d) => d && d.url);

  if (downloads.length) {
    const links = el("div", "plan-drawing-meta");
    downloads.forEach(function (item) {
      const row = el("div", "plan-drawing-path");
      row.appendChild(el("span", "plan-drawing-tag", item.label));
      const anchor = document.createElement("a");
      anchor.href = String(item.url);
      anchor.setAttribute("download", "");
      anchor.textContent = String(item.url).split("/").pop();
      row.appendChild(anchor);
      links.appendChild(row);
    });
    wrap.appendChild(links);
  } else {
    const paths = [];
    if (drawing.svg_path) paths.push(["SVG", drawing.svg_path]);
    if (drawing.dxf_path) paths.push(["DXF", drawing.dxf_path]);
    if (drawing.project_dxf_path) paths.push(["AutoCAD", drawing.project_dxf_path]);

    if (paths.length) {
      const meta = el("div", "plan-drawing-meta");
      paths.forEach(function (pair) {
        const row = el("div", "plan-drawing-path");
        row.appendChild(el("span", "plan-drawing-tag", pair[0]));
        row.appendChild(el("code", null, pair[1]));
        meta.appendChild(row);
      });
      wrap.appendChild(meta);
    }
  }

  return wrap;
}

async function handleChatResponse(payload, chat) {
  if (!payload) {
    chat.appendChild(messageNode("assistant", "No response from the Core API."));
    return;
  }

  if (payload.status === "error") {
    const response = payload.response || {};
    chat.appendChild(messageNode("assistant",
      response.message || payload.error || payload.message || "Request failed."));
    return;
  }

  const response = payload.response || {};
  const strategy = payload.strategy || {};

  if (payload.save_state) applySaveState(payload.save_state);

  const attachments = (response.attachments || []).filter(
    (a) => a.kind === "image" || a.kind === "render"
  );

  // CHAT-02E — `result` is a TEXT surface. Coerce defensively so a
  // structured payload can never reach the transcript as "[object Object]";
  // the structured data stays on its own keys for the panels that want it.
  //
  // R4_PHOTO_UI_FINAL_CLOSURE_V1 — this is resolved BEFORE the attachment
  // branch. It used to live after it, so an image reply returned from the
  // branch below and the turn's own sentence was silently discarded: the
  // user saw the picture with no explanation of what had been done.
  const text = typeof response.result === "string" && response.result
    ? response.result
    : (typeof response.message === "string" ? response.message : "");

  if (attachments.length) {
    await loadAssets();

    const asset = newestAsset();
    const parent = asset && asset.parent_asset_id
      ? state.assets.find((a) => a.asset_id === asset.parent_asset_id)
      : null;

    chat.appendChild(renderCard(attachments[0], {
      assetId: asset ? asset.asset_id : null,
      ordinal: asset ? asset.ordinal : null,
      parentOrdinal: parent ? parent.ordinal : null,
      profile: strategy.render_profile || $("qualitySelect").value,
      mode: (payload.routing || {}).mode || strategy.resolved_mode || $("modeSelect").value,
      title: assetLabel(asset),
    }));

    // A card is not a substitute for the assistant's own sentence, so the
    // message is shown beside it. An empty message renders the card alone:
    // no placeholder bubble is invented for an image turn.
    if (text.trim()) {
      chat.appendChild(messageNode("assistant", text));
      state.lastAssistantText = text;
    }
    return;
  }

  // ==========================================================
  // MULTIFLOOR_ENGINE_V2_CHAT_PLAN_ROUTING
  //
  // The furnished-plan turn carries a generated SVG/PNG sheet. It is
  // shown as an <img> pointing at the same-origin drawing route —
  // deliberately NOT innerHTML. The SVG is a generated document and
  // must never be parsed as markup inside the transcript.
  //
  // PLAN_SHEET_PNG_V1 — a renderable surface is resolved BEFORE the
  // empty-reply fallback. A turn that produced a drawing is never
  // announced as "no displayable text".
  // ==========================================================
  const planDrawing = response.plan_drawing_v2
    && (response.plan_drawing_v2.image_url
      || response.plan_drawing_v2.png_url
      || response.plan_drawing_v2.svg_url)
    ? response.plan_drawing_v2
    : null;

  const directImage = response.image_url || response.render_url || null;

  if (text.trim()) {
    chat.appendChild(messageNode("assistant", text));
  } else if (!planDrawing && !directImage) {
    chat.appendChild(messageNode("assistant",
      "⚠️ پاسخ دریافتی متن قابل نمایشی نداشت."));
  }

  if (planDrawing) {
    chat.appendChild(planDrawingNode(planDrawing));
  } else if (directImage) {
    const frame = el("div", "plan-drawing-frame");
    const img = document.createElement("img");
    img.className = "plan-drawing-image";
    img.alt = "رندر معماری";
    img.loading = "lazy";
    img.src = String(directImage);
    frame.appendChild(img);
    chat.appendChild(frame);
  }

  // IMAGE_TURN_TRANSPORT_RECOVERY_01 — remember what has already been
  // shown, so a recovery can never repeat an answer the user has seen.
  state.lastAssistantText = text || null;
}

async function refreshProjectMeta() {
  if (!state.projectId) return;
  const { data } = await api("/api/projects/" + state.projectId);
  if (data && data.project) {
    state.project = data.project;
    updateProjectHeader();
    applySaveState(data.save_state);

    // IMAGE_TURN_TRANSPORT_RECOVERY_01 — keep the baseline current.
    const recovery = data.recovery || {};
    if (typeof recovery.message_count === "number") {
      state.messageCount = recovery.message_count;
    }
  }
}


// ==========================================================
// ASSETS
// ==========================================================

function assetLabel(asset) {
  if (!asset) return "Asset";
  const type = asset.source_type || "asset";
  const kindLabel = {
    uploaded: "Upload",
    text_to_image: "Render",
    render: "Render",
    image_to_image: "Edit",
  }[type] || "Asset";
  return kindLabel + " #" + (asset.ordinal || "?");
}

async function loadAssets() {
  if (!state.projectId) return;

  const { data } = await api(
    "/api/projects/" + state.projectId + "/assets?filter=" + state.galleryFilter
  );
  if (!data || !data.gallery) return;

  state.assets = data.gallery.assets || [];
  state.activeAssetId = data.gallery.active_asset_id;

  $("assetCount").textContent = data.gallery.asset_count || 0;

  renderFilters();
  renderGallery();
  renderActiveAsset();

  // Populate the details panel on entry so the active asset's real
  // paths are visible without an extra click.
  if (!state.selectedAssetId && state.activeAssetId) {
    await showAssetDetails(state.activeAssetId);
    return;
  }

  if (state.selectedAssetId) await showAssetDetails(state.selectedAssetId);
}

function renderFilters() {
  const row = $("galleryFilters");
  clear(row);

  [
    ["all", "All"],
    ["uploads", "Uploads"],
    ["renders", "Renders"],
    ["edits", "Edits"],
    ["files", "Files"],
    ["final", "Final"],
  ].forEach(([value, label]) => {
    const chip = el("button", "chip", label);
    chip.type = "button";
    if (state.galleryFilter === value) chip.classList.add("is-active");
    chip.onclick = () => { state.galleryFilter = value; loadAssets(); };
    row.appendChild(chip);
  });
}

function newestAsset() {
  if (!state.assets.length) return null;
  return state.assets.reduce((a, b) =>
    (a.ordinal || 0) > (b.ordinal || 0) ? a : b);
}

function renderGallery() {
  const grid = $("galleryGrid");
  clear(grid);

  if (!state.assets.length) {
    grid.appendChild(el("p", "muted tiny", "No assets in this filter."));
    return;
  }

  state.assets.forEach((asset) => {
    const card = el("div", "gallery-card");
    if (state.selectedAssetId === asset.asset_id) card.classList.add("is-selected");

    const img = el("img");
    img.src = asset.public_path || "";
    img.alt = assetLabel(asset);
    img.loading = "lazy";
    card.appendChild(img);

    const flags = el("div", "gc-flags");
    if (asset.is_active) flags.appendChild(el("span", "flag flag-active", "ACTIVE"));
    if (asset.is_final) flags.appendChild(el("span", "flag flag-final", "FINAL"));
    card.appendChild(flags);

    const body = el("div", "gc-body");
    body.appendChild(el("div", "gc-title", assetLabel(asset)));
    body.appendChild(el("div", "gc-sub",
      (asset.source_type || "") + " · " + timeAgo(asset.created_at)));
    card.appendChild(body);

    card.onclick = () => showAssetDetails(asset.asset_id);
    grid.appendChild(card);
  });
}

function renderActiveAsset() {
  const box = $("activeAsset");
  clear(box);

  const active = state.assets.find((a) => a.asset_id === state.activeAssetId);

  if (!active) {
    box.classList.add("empty");
    box.textContent = "none";
    return;
  }

  box.classList.remove("empty");

  const img = el("img");
  img.src = active.public_path || "";
  img.alt = assetLabel(active);
  box.appendChild(img);

  const meta = el("div", "aa-meta");
  meta.appendChild(el("div", null, assetLabel(active)));
  meta.appendChild(el("div", "tiny muted", "Image #" + active.ordinal));
  box.appendChild(meta);
}

async function setActiveAsset(assetId) {
  const { data } = await api(
    "/api/projects/" + state.projectId + "/assets/" + assetId + "/active",
    { method: "POST", body: JSON.stringify({}) }
  );

  if (data && data.status === "success") {
    if (data.save_state) applySaveState(data.save_state);
    await loadAssets();
    toast("Active image updated");
  }
}

async function markFinal(assetId, isFinal) {
  const { data } = await api(
    "/api/projects/" + state.projectId + "/assets/" + assetId + "/final",
    { method: "POST", body: JSON.stringify({ is_final: isFinal }) }
  );

  if (data && data.status === "success") {
    await loadAssets();
    toast(isFinal ? "Marked as final" : "Final flag cleared");
  }
}

async function showAssetDetails(assetId) {
  const box = $("assetDetails");

  if (!assetId) {
    state.selectedAssetId = null;
    clear(box);
    box.appendChild(el("p", "muted tiny", "Select an asset to see its details."));
    return;
  }

  state.selectedAssetId = assetId;

  const { data } = await api(
    "/api/projects/" + state.projectId + "/assets/" + assetId
  );

  clear(box);

  if (!data || data.status !== "success") {
    box.appendChild(el("p", "muted tiny", "Asset details unavailable."));
    return;
  }

  const asset = data.asset;

  function row(key, value, plain) {
    if (value === null || value === undefined || value === "") return;
    const line = el("div", "detail-row");
    line.appendChild(el("div", "detail-key", key));
    line.appendChild(el("div", "detail-val" + (plain ? " plain" : ""), String(value)));
    box.appendChild(line);
  }

  row("Name", assetLabel(asset), true);
  row("Type", asset.source_type, true);
  row("Ordinal", "#" + asset.ordinal, true);
  row("Created", new Date((asset.created_at || 0) * 1000).toLocaleString(), true);
  row("Parent asset", asset.parent_asset_id
    ? ("#" + (asset.parent_ordinal || "?") + " (" + asset.parent_asset_id + ")")
    : null);
  row("Original filename", asset.original_filename);
  row("Stored filename", asset.generated_filename);
  row("Saved location", asset.storage_path);
  row("Dimensions", asset.dimensions
    ? asset.dimensions[0] + " × " + asset.dimensions[1] : null, true);
  row("Render status", asset.analysis_status, true);
  row("Active", asset.is_active ? "yes" : "no", true);
  row("Final", asset.is_final ? "yes" : "no", true);

  if (asset.lineage && asset.lineage.length > 1) {
    box.appendChild(el("div", "detail-section-title", "Lineage"));
    asset.lineage.forEach((step) => {
      box.appendChild(el("div", "detail-val plain",
        "#" + step.ordinal + " · " + step.source_type
        + (step.parent_asset_id ? " ← " + step.parent_asset_id : "")));
    });
  }

  const actions = el("div", "detail-actions");

  function action(label, handler, ghost) {
    const btn = el("button",
      "btn " + (ghost ? "btn-ghost" : "btn-primary") + " btn-small", label);
    btn.onclick = handler;
    actions.appendChild(btn);
  }

  action("Set Active", () => setActiveAsset(asset.asset_id));
  action("Copy Path", () => {
    navigator.clipboard.writeText(asset.storage_path || "");
    toast("Path copied");
  }, true);
  action("Open Folder", () => {
    toast("Folder: " + (asset.storage_path || ""));
  }, true);
  action(asset.is_final ? "Clear Final" : "Mark Final",
    () => markFinal(asset.asset_id, !asset.is_final), true);
  action("Use as Reference", async () => {
    await setActiveAsset(asset.asset_id);
    toast("Active image set as reference");
  }, true);
  action("Analyze", () => {
    $("message").value = "این عکس رو توضیح بده";
    $("modeSelect").value = "analyze_image";
    toast("Prompt ready — press Send");
  }, true);
  action("Edit", () => {
    $("message").value = "همین عکس رو ";
    $("modeSelect").value = "image_to_image";
    $("message").focus();
  }, true);

  box.appendChild(actions);

  renderGallery();
}


// ==========================================================
// ATTACHMENT
// ==========================================================

// FACADE-04D.3C-0 — the conditioned opt-in is only meaningful when BOTH role
// images are attached (A = style reference, B = target building). It is
// disabled and force-cleared otherwise, so a half-set opt-in can never be
// sent. The server independently rejects it without both images.
function syncConditionedToggle() {
  const toggle = $("conditionedToggle");
  if (!toggle) return;
  const eligible = !!(state.attachFiles && state.attachFiles.length >= 2);
  toggle.disabled = !eligible;
  if (!eligible) {
    toggle.checked = false;
    // A forced reset is not a user choice, so it must not be sent as one.
    delete toggle.dataset.touched;
  }
}

// PRECISE_EDIT_UI_V1 — a localized (masked) edit needs BOTH a mask image and
// the precise route. The mask input is enabled only while the checkbox is
// ticked, and the hint states the dimension requirement the server enforces.
function syncMaskControls() {
  const toggle = $("localizedEditToggle");
  const input = $("maskFile");
  const hint = $("maskHint");
  if (!toggle || !input) return;
  input.disabled = !toggle.checked;
  if (!toggle.checked) {
    input.value = "";
    if (hint) {
      hint.textContent =
        "The mask must match the source image's pixel size. Only the masked "
        + "area is changed.";
    }
    return;
  }
  if (hint) {
    hint.textContent =
      "Choose a black/white mask the same size as the image being edited. "
      + "Only the masked area is changed; the rest is preserved exactly.";
  }
}

function clearAttachment() {
  state.attachFile = null;
  state.attachFiles = [];
  $("imageInput").value = "";
  $("attachChip").classList.add("hidden");
  $("attachChip").textContent = "";
  syncConditionedToggle();
  refreshUiState();
}
// FACADE-02 — ordered A/B attachment. IMAGE A is the facade style
// reference (appearance only); IMAGE B is the target building
// (geometry authority). Roles are bound by ORDER here and by explicit
// field name at the API boundary; they are never swapped.
const MAX_ATTACH = 2;

// The chip names the ROLE of each file so the A/B binding is visible to
// the user before the turn is sent.
function attachChipLabel(files) {
  if (files.length === 1) return "Attached: " + files[0].name;
  return "A (style): " + files[0].name + "  ·  B (target): " + files[1].name;
}

function onAttach(event) {
  const picked = event.target.files ? Array.from(event.target.files) : [];
  if (!picked.length) return;
  if (picked.length > MAX_ATTACH) {
    state.attachFiles = [];
    state.attachFile = null;
    $("imageInput").value = "";
    $("attachChip").textContent =
      "Too many images — attach at most 2 (A = style reference, B = target building).";
    $("attachChip").classList.remove("hidden");
    syncConditionedToggle();
    refreshUiState();
    return;
  }
  state.attachFiles = picked;
  // `attachFile` keeps the legacy single-image contract intact.
  state.attachFile = picked[0];
  $("attachChip").textContent = attachChipLabel(picked);
  $("attachChip").classList.remove("hidden");
  // ARCHITECTURAL_LEARNING_UI_01 — an attachment means OBSERVATION.
  syncConditionedToggle();
  refreshUiState();
}


// ==========================================================
// VOICE_07 — microphone capture, canonical voice turn, TTS
//
// States: idle | requesting | recording | processing | responding
//         | speaking | failed
//
// Truthful by construction:
//   - no fabricated audio level or waveform
//   - no fabricated transcript on STT failure
//   - no automatic microphone start while TTS is speaking
// ==========================================================

state.voice = {
  status: "idle",
  capability: null,
  recorder: null,
  chunks: [],
  stream: null,
  startedAt: null,
  timer: null,
  cancelled: false,
  speaking: false,
  // PERSIAN_TTS_V1 — the <audio> element used by the server-side Persian
  // voice (English keeps using speechSynthesis).
  audioEl: null,
  settings: { voice_reply: "auto", tts_voice: "auto", stt_language: "auto" },
  // PERSIAN_VOICE_QUALITY_V2 / PHASE 1 — how a finished recording is used:
  //   "dictate" (default) -> STT only, transcript lands in the composer
  //                          and the user edits + sends normally
  //   "direct"            -> legacy one-shot mic -> STT -> reply turn
  // Both remain available; dictate never permanently removes direct voice.
  mode: "dictate",
  transcribing: false,
  // OFFLINE_DEGRADED_STATUS_UI_V1 — the truthful degraded signal the
  // canonical chat path reports, plus one-shot notices so the UI never
  // repeats the same scoped message turn after turn.
  connectivityChatDegraded: false,
  connectivityPersianVoiceNotified: false,
  // True/False = the last capability refresh answered truthfully / did
  // not. `undefined` = never refreshed yet (cold start is not "degraded").
  connectivityCapabilityOk: undefined,
};

// OPERATION_VISIBILITY_UI_01 — Persian phase labels. The UI ships with
// lang="fa" and a Persian reply voice, so the voice phases must be
// readable in the same language. `uploading` is the missing phase
// between "recording stopped" and "STT started".
const VOICE_STATE_LABELS = {
  idle: "",
  requesting: "در حال دریافت دسترسی میکروفون…",
  recording: "در حال ضبط…",
  uploading: "در حال ارسال صدا…",
  processing: "در حال تشخیص گفتار…",
  responding: "در حال پردازش پاسخ…",
  speaking: "در حال ساخت صدا…",
  // PERSIAN_VOICE_QUALITY_V2 / PHASE 1 — a completed DICTATION is not a
  // recording phase; the transcript is sitting in the composer, editable.
  dictated: "متن گفتار آماده و قابل ویرایش است.",
  // UNCERTAIN_TRANSCRIPT_REVIEW_V1 — Whisper produced text that the quality
  // gate withheld for CONFIDENCE reasons. This is neither a failure nor a
  // verified transcript: it is waiting for an explicit user decision.
  candidate: "متن مشکوک — نیازمند تأیید شما",
  failed: "عملیات ناموفق بود",
};

function setVoiceState(status, message) {
  state.voice.status = status;

  const chip = $("voiceStatusChip");

  if (!chip) return;

  if (!status || status === "idle") {
    chip.classList.add("hidden");
    chip.className = "attach-chip hidden";
    chip.textContent = "";
    return;
  }

  chip.classList.remove("hidden");
  chip.className = "attach-chip voice-state-" + status;
  chip.textContent = message || VOICE_STATE_LABELS[status] || status;
}

function clearVoiceState() {
  setVoiceState("idle");
}

// ======================================================
// UNCERTAIN_TRANSCRIPT_REVIEW_V1
// ======================================================
// A withheld transcript is only ever OFFERED, never used. When the quality
// gate withholds text for CONFIDENCE reasons, the text is shown in a review
// card with two explicit actions. Nothing reaches the composer or the chat
// until the user clicks "Use Text", and even then it is only inserted - the
// user's own Send is still required.
//
// Gating rule (evidence-based, deliberately NOT a reason blacklist):
//   * `raw_transcript` must be nonempty. Genuine silence is rejected by the
//     acoustic gate BEFORE decoding (raw_transcript = null), so silence, an
//     empty decode, and every transport failure are excluded automatically.
//   * `quality.low_confidence_suspected` must be true. Only confidence
//     uncertainty is offered - not prompt echo, not repetition, not a script
//     mismatch, not a missing/oversized file.
// This matters because the SAME reason code (`no_speech_detected`) covers
// both genuine silence and a genuine short word; only these two conditions
// tell them apart. Anything else is not offered: the rule fails CLOSED.
const VOICE_REVIEW_ID = "voiceReviewCard";

function voiceReviewCandidate(payload) {
  if (!payload) return null;

  const quality = payload.quality || {};

  if (quality.low_confidence_suspected !== true) return null;

  const text = String(payload.raw_transcript || "").trim();

  if (!text) return null;

  return {
    text: text,
    reason: payload.reason || null,
    detail: quality.low_confidence_reason || null,
  };
}

function clearVoiceReview() {
  const existing = $(VOICE_REVIEW_ID);
  if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
}

function renderVoiceReviewCandidate(payload) {
  const candidate = voiceReviewCandidate(payload);

  clearVoiceReview();

  if (!candidate) return null;

  const anchor = $("voiceStatusChip");
  if (!anchor || !anchor.parentNode) return null;

  const card = el("div", "voice-review-card");
  card.id = VOICE_REVIEW_ID;
  card.style.marginTop = "8px";
  card.style.padding = "10px 12px";
  card.style.border = "1px solid var(--warn)";
  card.style.borderRadius = "var(--radius-sm)";
  card.style.background = "var(--panel-2)";
  card.style.display = "flex";
  card.style.flexDirection = "column";
  card.style.gap = "8px";
  card.style.textAlign = "start";

  // The candidate is rendered as TEXT via textContent (see `el`), never as
  // HTML, so a transcript can never inject markup.
  const warning = el("div", null,
    "این متن با اطمینان پایین تشخیص داده شده و ممکن است نادرست یا ناقص "
    + "باشد. تا زمانی که «استفاده از متن» را نزنید، هیچ متنی ارسال "
    + "نمی‌شود و این متن به‌عنوان گفتار تأییدشده در نظر گرفته نمی‌شود.");
  warning.style.color = "var(--warn)";
  warning.style.fontSize = "var(--fs-xs)";
  warning.style.lineHeight = "1.7";

  const textNode = el("div", null, candidate.text);
  textNode.dir = "auto";
  textNode.style.color = "var(--text)";
  textNode.style.fontSize = "var(--fs-md)";
  textNode.style.background = "var(--bg-elevated)";
  textNode.style.border = "1px solid var(--line)";
  textNode.style.borderRadius = "var(--radius-sm)";
  textNode.style.padding = "8px 10px";
  textNode.style.whiteSpace = "pre-wrap";
  textNode.style.wordBreak = "break-word";

  const actions = el("div", null);
  actions.style.display = "flex";
  actions.style.gap = "8px";

  const useBtn = el("button", "btn btn-ghost btn-small", "استفاده از متن");
  useBtn.type = "button";
  useBtn.onclick = () => {
    // INSERT ONLY. Sending stays the user's action.
    insertIntoComposer(candidate.text);

    const input = $("message");
    if (input) {
      input.dataset.voiceRawTranscript = candidate.text;
      // Provenance: this text came from an UNVERIFIED candidate, so later
      // code can never mistake it for verified speech.
      input.dataset.voiceTranscriptUncertain = "1";
      try { input.focus(); } catch (error) { /* ignore */ }
    }

    clearVoiceReview();
    setVoiceState("candidate",
      "متن مشکوک به کادر نوشتن افزوده شد؛ پیش از ارسال بازبینی کنید.");
    setTimeout(clearVoiceState, 4200);
  };

  const discardBtn = el("button", "btn btn-ghost btn-small", "رد کردن");
  discardBtn.type = "button";
  discardBtn.onclick = () => {
    // Discard: drop the candidate, leave the composer untouched.
    clearVoiceReview();
    clearVoiceState();
  };

  actions.appendChild(useBtn);
  actions.appendChild(discardBtn);

  card.appendChild(warning);
  card.appendChild(textNode);
  card.appendChild(actions);

  anchor.parentNode.insertBefore(card, anchor.nextSibling);

  return candidate;
}

async function loadVoiceCapability() {
  const query = state.projectId ? "?project_id=" + state.projectId : "";
  const { data } = await api("/api/voice/status" + query);
  if (!data || data.status !== "success") return null;

  state.voice.capability = data;

  if (data.settings) {
    state.voice.settings = Object.assign(
      state.voice.settings, data.settings
    );
  }

  // ======================================================
  // PERSIAN_TTS_VOICE_SELECTOR_01 — TTS voice dropdown
  //
  // THREE truthful sources, clearly separated by provider:
  //   1. SERVER PERSIAN (edge-tts) — fa-IR voices, spoken through
  //      POST /api/voice/speak. Reported by the capability endpoint as
  //      `voice.tts_persian_provider.voices`.
  //   2. BROWSER (window.speechSynthesis) — the voices the browser can
  //      actually play locally.
  //   3. SERVER-REPORTED OS voices (fallback only, when the browser
  //      exposes none) — the Windows SAPI/OneCore list.
  //
  // The option VALUE is what gets stored as `tts_voice` and later routed;
  // the LABEL always names the provider so the choice is unambiguous.
  // ======================================================
  const select = $("ttsVoiceSelect");
  if (select) {
    clear(select);

    const auto = el("option", null, "Auto");
    auto.value = "auto";
    select.appendChild(auto);

    // ---- (1) SERVER PERSIAN voices (edge-tts) ----
    const serverProvider = (data.voice && data.voice.tts_persian_provider) || {};
    const serverVoices = Array.isArray(serverProvider.voices)
      ? serverProvider.voices : [];

    if (data.voice && data.voice.tts_persian_server && serverVoices.length) {
      const group = document.createElement("optgroup");
      group.label = "Persian — Server (" +
        (serverProvider.provider || "edge-tts") + ")";

      serverVoices.forEach((voice) => {
        // "fa-IR-DilaraNeural" -> "Dilara"
        const bare = String(voice).replace(/^[a-z]{2}-[A-Z]{2}-/, "")
          .replace(/Neural$/, "");
        const option = el("option", null, "Persian — " + bare + " (Server)");
        option.value = voice;
        option.dataset.provider = "server-persian";
        option.dataset.lang = "fa-IR";
        group.appendChild(option);
      });

      select.appendChild(group);
    }

    // ---- (2) BROWSER voices (what speechSynthesis plays) ----
    const browserVoices = (window.speechSynthesis
      && window.speechSynthesis.getVoices()) || [];

    if (browserVoices.length) {
      const group = document.createElement("optgroup");
      group.label = "Browser";

      browserVoices.forEach((voice) => {
        // "Microsoft Zira - English (United States)" -> "Microsoft Zira"
        const bare = String(voice.name).split(" - ")[0] || voice.name;
        const option = el("option", null, bare + " (Browser)");
        option.value = voice.name;
        option.dataset.provider = "browser";
        option.dataset.lang = voice.lang || "";
        group.appendChild(option);
      });

      select.appendChild(group);
    } else {
      // ---- (3) server-reported OS voices (fallback) ----
      const osVoices = (data.voice && data.voice.tts_voices) || [];

      if (osVoices.length) {
        const group = document.createElement("optgroup");
        group.label = "System";

        osVoices.forEach((voice) => {
          const bare = String(voice.name).split(" - ")[0] || voice.name;
          const option = el("option", null, bare + " (System)");
          option.value = voice.name;
          option.dataset.provider = "system";
          option.dataset.lang = (voice.languages || [])[0] || "";
          group.appendChild(option);
        });

        select.appendChild(group);
      }
    }
  }

  const hint = $("voiceCapabilityHint");
  if (hint) {
    const parts = [];
    parts.push(data.voice.stt_available ? "STT ready" : "STT unavailable");
    if (data.voice.tts_available) {
      parts.push(data.voice.tts_persian
        ? "TTS incl. Persian"
        : "TTS English only");
    } else {
      parts.push("TTS unavailable");
    }
    hint.textContent = parts.join(" · ");
  }

  // restore saved settings into the controls
  if ($("voiceReplySelect")) {
    $("voiceReplySelect").value = state.voice.settings.voice_reply || "auto";
  }
  if ($("sttLanguageSelect")) {
    $("sttLanguageSelect").value = state.voice.settings.stt_language || "auto";
  }
  if ($("ttsVoiceSelect")) {
    $("ttsVoiceSelect").value = state.voice.settings.tts_voice || "auto";
  }

  return data;
}

async function saveVoiceSettings() {
  const settings = {
    project_id: state.projectId,
    voice_reply: $("voiceReplySelect") ? $("voiceReplySelect").value : "auto",
    tts_voice: $("ttsVoiceSelect") ? $("ttsVoiceSelect").value : "auto",
    stt_language: $("sttLanguageSelect")
      ? $("sttLanguageSelect").value : "auto",
  };

  state.voice.settings = Object.assign({}, state.voice.settings, settings);

  if (!state.projectId) return;

  await api("/api/voice/settings", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

function micSupported() {
  return Boolean(
    navigator.mediaDevices
    && navigator.mediaDevices.getUserMedia
    && window.MediaRecorder
  );
}

function pickRecorderMime() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  for (const type of candidates) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported
        && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return "";
}

async function startRecording() {
  // UNCERTAIN_TRANSCRIPT_REVIEW_V1 — a new take supersedes any candidate
  // still waiting for review, so a stale card can never be accepted later.
  clearVoiceReview();

  if (state.voice.speaking) {
    // Never create a microphone -> speaker feedback loop.
    setVoiceState("failed", "پیش از ضبط، پخش صدای پاسخ را متوقف کنید.");
    setTimeout(clearVoiceState, 2600);
    return;
  }

  if (state.voice.status === "recording") {
    stopRecording();
    return;
  }

  if (!micSupported()) {
    setVoiceState("failed",
      "این مرورگر از ضبط میکروفون پشتیبانی نمی‌کند.");
    setTimeout(clearVoiceState, 3200);
    return;
  }

  if (state.voice.capability
      && !state.voice.capability.voice.stt_available) {
    setVoiceState("failed",
      "تشخیص گفتار روی این دستگاه در دسترس نیست.");
    setTimeout(clearVoiceState, 3200);
    return;
  }

  state.voice.cancelled = false;

  // PERSIAN_VOICE_QUALITY_V2 / PHASE 1 — a new take supersedes the
  // "transcript ready" notice from a previous take.
  if (state.voice.status === "dictated") clearVoiceState();

  setVoiceState("requesting");

  try {
    state.voice.stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
    });
  } catch (error) {
    const name = (error && error.name) || "Error";
    let message = "میکروفون در دسترس نیست.";
    if (name === "NotAllowedError" || name === "SecurityError") {
      message = "اجازه دسترسی به میکروفون داده نشد.";
    } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      message = "میکروفونی پیدا نشد.";
    } else if (name === "NotReadableError") {
      message = "میکروفون در حال استفاده توسط برنامه دیگری است.";
    }
    setVoiceState("failed", message);
    setTimeout(clearVoiceState, 4200);
    return;
  }

  const mimeType = pickRecorderMime();

  try {
    state.voice.recorder = mimeType
      ? new MediaRecorder(state.voice.stream, { mimeType })
      : new MediaRecorder(state.voice.stream);
  } catch (error) {
    releaseStream();
    setVoiceState("failed", "این مرورگر از کدک صوتی پشتیبانی نمی‌کند.");
    setTimeout(clearVoiceState, 3600);
    return;
  }

  state.voice.chunks = [];

  state.voice.recorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) state.voice.chunks.push(event.data);
  };

  state.voice.recorder.onstop = () => {
    releaseStream();
    const cancelled = state.voice.cancelled;
    const blob = new Blob(state.voice.chunks, {
      type: state.voice.recorder.mimeType || "audio/webm",
    });
    state.voice.chunks = [];
    if (cancelled) {
      clearVoiceState();
      return;
    }
    // PERSIAN_VOICE_QUALITY_V2 / PHASE 1 — the recording is turned into
    // TEXT first (dictate) instead of being auto-sent as a whole turn.
    // The text lands in the normal composer, is editable, and only the
    // user's Send triggers the unchanged chat path.
    if (state.voice.mode === "direct") {
      sendVoiceTurn(blob);
    } else {
      dictateVoiceToComposer(blob);
    }
  };

  state.voice.recorder.start();
  state.voice.startedAt = Date.now();

  $("recordingBar").classList.remove("hidden");
  $("micBtn").classList.add("is-recording");
  setVoiceState("recording");

  const elapsed = $("recElapsed");
  elapsed.textContent = "00:00";
  state.voice.timer = setInterval(() => {
    elapsed.textContent = clock((Date.now() - state.voice.startedAt) / 1000);
  }, 500);
}

function stopRecording() {
  if (state.voice.recorder
      && state.voice.recorder.state !== "inactive") {
    state.voice.recorder.stop();
  }
  endRecordingUi();
}

function cancelRecording() {
  state.voice.cancelled = true;
  if (state.voice.recorder
      && state.voice.recorder.state !== "inactive") {
    state.voice.recorder.stop();
  } else {
    releaseStream();
    clearVoiceState();
  }
  endRecordingUi();
}

function endRecordingUi() {
  if (state.voice.timer) clearInterval(state.voice.timer);
  state.voice.timer = null;
  $("recordingBar").classList.add("hidden");
  $("micBtn").classList.remove("is-recording");
}

function releaseStream() {
  if (state.voice.stream) {
    state.voice.stream.getTracks().forEach((track) => track.stop());
  }
  state.voice.stream = null;
}

// ----------------------------------------------------------
// PERSIAN_VOICE_QUALITY_V2 / PHASE 1 — EDITABLE VOICE TRANSCRIPT
//
// New default voice path (DICTATE_TO_COMPOSER):
//   mic -> MediaRecorder -> STT-only endpoint -> transcript
//       -> inserted into the NORMAL composer -> user edits
//       -> user presses Send -> the UNCHANGED sendMessage() path.
//
// Design rules honoured here:
//   * no chat submission logic is duplicated — sending stays sendMessage()
//   * nothing is auto-sent; the user stays in control
//   * existing composer text is never destroyed (cursor-safe insert)
//   * the raw transcript is preserved (on the DOM node + in state) so it
//     can be inspected truthfully after edits
//   * the direct voice turn is NOT removed — it stays available via the
//     "ارسال مستقیم" mode
// ----------------------------------------------------------

// Truthful Persian failure labels for the STT-only path. Kept separate
// from VOICE_STATE_LABELS because these are REASONS, not phases.
const VOICE_STT_FAILURE_LABELS = {
  repetition_detected: "گفتار تکراری تشخیص داده شد. لطفاً دوباره تلاش کنید.",
  prompt_echo_detected: "تشخیص گفتار نامطمئن بود. لطفاً دوباره تلاش کنید.",
  script_mismatch_detected: "زبان گفتار با زبان انتظار هم‌خوانی نداشت.",
  no_speech_detected: "گفتاری شنیده نشد.",
  low_confidence_detected: "تشخیص گفتار با اطمینان کافی انجام نشد. لطفاً واضح‌تر و کمی آهسته‌تر بگویید.",
  empty_transcript: "گفتاری تشخیص داده نشد.",
  no_audio_received: "صدایی دریافت نشد.",
  audio_store_failed: "ذخیرهٔ صدای ضبط‌شده انجام نشد.",
  stt_unavailable: "تشخیص گفتار روی این دستگاه در دسترس نیست.",
};

// Insert `text` into the composer at the caret without destroying what the
// user already wrote. When the composer is empty this is just a set; when it
// has content, a separating space is added only if the surrounding
// characters actually need one. Prefers caret insertion, which is the
// smallest clean behaviour and exactly what desktop dictation does.
function insertIntoComposer(text) {
  const input = $("message");
  if (!input || !text) return;

  const value = String(input.value || "");

  if (!value) {
    input.value = text;
  } else {
    const start = typeof input.selectionStart === "number"
      ? input.selectionStart : value.length;
    const end = typeof input.selectionEnd === "number"
      ? input.selectionEnd : value.length;

    const before = value.slice(0, start);
    const after = value.slice(end);

    const needsLeading = before.length > 0 && !/\s$/.test(before);
    const needsTrailing = after.length > 0 && !/^\s/.test(after);

    const insert = (needsLeading ? " " : "") + text
      + (needsTrailing ? " " : "");

    input.value = before + insert + after;

    const caret = before.length + insert.length;
    try { input.setSelectionRange(caret, caret); } catch (e) { /* ignore */ }
  }

  autoGrowMessage();
}

async function dictateVoiceToComposer(blob) {
  if (!blob || blob.size === 0) {
    setVoiceState("failed", "ضبط خالی بود. لطفاً دوباره تلاش کنید.");
    setTimeout(clearVoiceState, 3600);
    return;
  }

  // Reuse the Operation Visibility phase vocabulary: upload, then STT.
  setVoiceState("uploading");
  state.voice.transcribing = true;

  const form = new FormData();
  form.append("audio", blob, "voice.webm");
  if (state.projectId) form.append("project_id", state.projectId);
  form.append("language", $("sttLanguageSelect")
    ? $("sttLanguageSelect").value : "auto");

  const sttPhase = setTimeout(() => {
    if (state.voice.status === "uploading") setVoiceState("processing");
  }, 900);

  let payload = null;
  try {
    const response = await fetch("/api/voice/transcribe", {
      method: "POST",
      body: form,
    });
    clearTimeout(sttPhase);
    setVoiceState("processing");
    payload = await response.json();
  } catch (error) {
    clearTimeout(sttPhase);
    state.voice.transcribing = false;
    setVoiceState("failed", "ارتباط با سرور برقرار نشد.");
    setTimeout(clearVoiceState, 3600);
    return;
  }

  state.voice.transcribing = false;

  // ---- truthful STT failure: never fabricate text ----
  if (!payload || payload.status !== "ok") {
    const reason = payload && (payload.reason || payload.error);
    const message = payload && payload.message
      ? payload.message
      : (VOICE_STT_FAILURE_LABELS[reason] || "تشخیص گفتار انجام نشد.");

    // UNCERTAIN_TRANSCRIPT_REVIEW_V1 — if Whisper DID produce text and the
    // quality gate withheld it for confidence reasons, offer it for explicit
    // review instead of discarding it. Returns null - leaving the failure
    // path below completely unchanged - for genuine silence, an empty
    // decode, prompt echo, repetition, script mismatch and transport
    // failures. Nothing is inserted and nothing is sent here.
    if (renderVoiceReviewCandidate(payload)) {
      setVoiceState("candidate");
      return;
    }

    setVoiceState("failed", message);
    setTimeout(clearVoiceState, 4200);
    return;
  }

  const transcript = (payload.transcript || "").trim();
  if (!transcript) {
    setVoiceState("failed", "گفتاری تشخیص داده نشد. لطفاً دوباره تلاش کنید.");
    setTimeout(clearVoiceState, 3800);
    return;
  }

  // The transcript is only an INPUT METHOD result: put it in the composer.
  insertIntoComposer(transcript);

  const input = $("message");
  if (input) {
    // Keep the RAW transcript observable for inspection/debugging, and
    // never overwrite an already-recorded raw value from an earlier take
    // with a later one — the last take wins, which is what the user sees.
    input.dataset.voiceRawTranscript = transcript;
    try { input.focus(); } catch (e) { /* ignore */ }
    // Place the caret at the end of the freshly inserted text so the user
    // can keep typing / correcting immediately.
    try {
      const end = input.value.length;
      input.setSelectionRange(end, end);
    } catch (e) { /* ignore */ }
  }

  // Subtle, non-blocking Persian status. `dictated` is deliberately NOT
  // part of VOICE_STATE_LABELS so it never collides with the recording
  // lifecycle; it is cleared as soon as the user sends or starts again.
  setVoiceState("dictated", "متن گفتار آماده و قابل ویرایش است.");

  // The transcript has been recognised, so this voice capture is over.
  endRecordingUi();
}

async function sendVoiceTurn(blob) {
  const chat = $("chatScroll");
  const empty = $("chatEmpty");
  if (empty) empty.classList.add("hidden");

  if (!blob || blob.size === 0) {
    setVoiceState("failed", "ضبط خالی بود. لطفاً دوباره تلاش کنید.");
    setTimeout(clearVoiceState, 3600);
    return;
  }

  // OPERATION_VISIBILITY_UI_01 — the voice flow has genuinely distinct
  // phases, and each is shown on its own (never all at once):
  //   ضبط → ارسال صدا → تشخیص گفتار → پردازش پاسخ → ساخت صدا
  setVoiceState("uploading");

  const startedAt = Date.now();

  const form = new FormData();
  form.append("audio", blob, "voice.webm");
  if (state.projectId) form.append("project_id", state.projectId);
  form.append("mode", $("modeSelect").value);
  form.append("quality", $("qualitySelect").value);
  form.append("seed_mode", $("seedModeSelect").value);
  if ($("seedValue").value) form.append("seed_value", $("seedValue").value);
  form.append("language", $("sttLanguageSelect")
    ? $("sttLanguageSelect").value : "auto");

  let payload = null;

  // The single request carries upload → STT → reply, so the visible
  // phase is advanced at each real boundary rather than guessed. The
  // STT boundary is reached the moment the server starts responding;
  // we advance the label right before the fetch settles into parsing.
  const sttPhase = setTimeout(() => {
    if (state.voice.status === "uploading") setVoiceState("processing");
  }, 900);

  try {
    const response = await fetch("/api/voice/turn", {
      method: "POST",
      body: form,
    });
    clearTimeout(sttPhase);
    setVoiceState("processing");
    payload = await response.json();
  } catch (error) {
    clearTimeout(sttPhase);
    setVoiceState("failed", "ارتباط با سرور برقرار نشد.");
    setTimeout(clearVoiceState, 3600);
    return;
  }

  if (!payload || payload.status === "error") {
    const message = (payload && payload.message)
      || "تشخیص گفتار انجام نشد.";
    setVoiceState("failed", message);
    chat.appendChild(messageNode("assistant", message));

    // UNCERTAIN_TRANSCRIPT_REVIEW_V1 — direct mode is NOT rerouted. The
    // /api/voice/turn endpoint returns before running the chat whenever STT
    // is not ok (core/voice/voice_api_v1.py:239-259), so no chat turn, no
    // LLM call and no TTS can be triggered by rejected or uncertain speech.
    // The response already carries the STT envelope, so the withheld text
    // can be offered for review here without a second decode or a second
    // request. `payload.stt` is absent for transport-level failures, and
    // `renderVoiceReviewCandidate` still fails closed.
    if (payload && payload.stt) renderVoiceReviewCandidate(payload.stt);

    setTimeout(clearVoiceState, 4200);
    return;
  }

  const stt = payload.stt || {};
  const transcript = payload.transcript || "";

  setVoiceState("responding");

  // Show the recognised transcript in the normal chat flow.
  const wrap = el("div", "msg msg-user");
  wrap.appendChild(el("div", "msg-role", "You · Voice"));
  wrap.appendChild(el("div", "msg-bubble", transcript));

  const meta = el("div", "msg-voice-meta");
  const bits = [];
  if (stt.detected_language) bits.push(stt.detected_language);
  if (stt.provider) bits.push(stt.provider);
  if (stt.confidence !== null && stt.confidence !== undefined) {
    bits.push("avg_logprob " + stt.confidence);
  }
  if (payload.timing && payload.timing.stt_seconds !== undefined) {
    bits.push("STT " + payload.timing.stt_seconds + "s");
  }
  meta.textContent = bits.join(" · ");
  wrap.appendChild(meta);

  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;

  await handleChatResponse(payload, chat);

  // ---- TTS reply ----
  const replyText = ((payload.response || {}).result
    || (payload.response || {}).message || "");

  if (replyText) {
    maybeSpeak(replyText);
  }

  const total = ((Date.now() - startedAt) / 1000).toFixed(1);
  if (!state.voice.speaking) {
    // No TTS is running, so the whole voice turn is done. Clear the
    // phase chip; the header activity pill is not used for the voice
    // wizard (the chip already shows every phase on its own).
    setVoiceState("idle");
    toast("پاسخ صوتی کامل شد در " + total + "s");
  }

  await loadAssets();
  await refreshProjectMeta();
}

// ----------------------------------------------------------
// TTS  (browser speech synthesis — real, OS-voice dependent)
// ----------------------------------------------------------

function isPersianText(text) {
  return /[\u0600-\u06FF]/.test(String(text || ""));
}

// PERSIAN_TTS_V1 — the OS voice stores on this machine have NO Persian
// voice, so the browser cannot speak Persian. A server-side provider
// (reported as `tts_persian_server`) supplies real Persian audio. English
// is untouched: it keeps using the browser's own speechSynthesis.
function persianServerTTS() {
  const capability = state.voice.capability;
  return !!(capability && capability.voice && capability.voice.tts_persian_server);
}

function finishSpeaking() {
  state.voice.speaking = false;
  if (state.voice.audioEl) {
    try { state.voice.audioEl.pause(); } catch (error) { /* ignore */ }
    state.voice.audioEl = null;
  }
  $("micBtn").disabled = false;
  clearVoiceState();
}

// ======================================================
// PERSIAN_TTS_VOICE_SELECTOR_01 — resolve the SELECTED server Persian voice.
//
// Returns a specific fa-IR voice name ONLY when the stored `tts_voice`
// setting actually names one this server can synthesise; otherwise null
// (meaning: let the server use its configured default).
//
// The value is validated against the capability-reported server voice list,
// so a stale/browser setting can never be sent to /api/voice/speak.
// ======================================================
function selectedServerPersianVoice() {
  const wanted = state.voice.settings.tts_voice;

  if (!wanted || wanted === "auto") return null;

  const capability = state.voice.capability || {};
  const provider = capability.voice && capability.voice.tts_persian_provider;
  const serverVoices = (provider && Array.isArray(provider.voices))
    ? provider.voices : [];

  return serverVoices.indexOf(wanted) !== -1 ? wanted : null;
}

async function speakPersianViaServer(text) {
  if (window.speechSynthesis) window.speechSynthesis.cancel();

  state.voice.speaking = true;
  $("micBtn").disabled = true;
  setVoiceState("speaking");

  try {
    // The selected server voice (Dilara / Farid) is passed explicitly.
    // With no explicit server voice, the field is omitted and the server
    // uses its own default — the endpoint validates the value anyway.
    const body = { text: String(text), language: "fa" };
    const chosen = selectedServerPersianVoice();
    if (chosen) body.voice = chosen;

    const response = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const type = response.headers.get("Content-Type") || "";

    if (!response.ok || type.indexOf("audio") !== 0) {
      const info = await response.json().catch(() => ({}));
      finishSpeaking();
      toast(info.message || "صدای فارسی در دسترس نیست", 3600);
      // OFFLINE_DEGRADED_STATUS_UI_V1 — a real synthesis failure means
      // the online Persian voice is not reachable right now. Re-derive
      // so the persistent pill tells the truth; recovery clears it.
      await refreshConnectivity();
      return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);

    state.voice.audioEl = audio;

    const done = () => {
      URL.revokeObjectURL(url);
      finishSpeaking();
    };

    audio.onended = done;
    audio.onerror = () => {
      done();
      toast("Voice playback failed");
    };

    await audio.play();
  } catch (error) {
    finishSpeaking();
    toast("صدای فارسی در دسترس نیست", 3600);
  }
}

function maybeSpeak(text) {
  const mode = state.voice.settings.voice_reply || "auto";

  if (mode === "off") return;

  const capability = state.voice.capability;

  if (isPersianText(text)) {
    // Prefer the real server-side Persian voice when it is available.
    if (persianServerTTS()) {
      speakPersianViaServer(String(text));
      return;
    }

    // OFFLINE_DEGRADED_STATUS_UI_V1 — the online Persian voice is
    // genuinely unreachable. Explain it ONCE (scoped), not every turn,
    // and let the persistent pill carry the ongoing state.
    const provider = (capability && capability.voice
      && capability.voice.tts_persian_provider) || {};
    if (provider.installed === true
        && (provider.offline === true || provider.reachable === false)) {
      setVoiceState("idle");
      notePersianVoiceUnavailable();
      return;
    }

    // Truthful: do not pretend to speak a language we have no voice for.
    if (capability && capability.voice && capability.voice.tts_persian === false) {
      setVoiceState("idle");
      toast("Persian voice reply unavailable — showing text", 3200);
      return;
    }
  }

  if (!window.speechSynthesis) {
    toast("Speech playback is unavailable in this browser");
    return;
  }

  if (state.voice.speaking) {
    window.speechSynthesis.cancel();
  }

  const utterance = new SpeechSynthesisUtterance(String(text));

  // Language metadata, not a vendor voice name: match the response
  // language so the browser never picks an arbitrary voice.
  utterance.lang = isPersianText(text) ? "fa-IR" : "en-US";

  const wanted = state.voice.settings.tts_voice;
  if (wanted && wanted !== "auto") {
    const voices = window.speechSynthesis.getVoices() || [];
    const match = voices.find((v) => v.name === wanted);
    if (match) utterance.voice = match;
  } else {
    const voices = window.speechSynthesis.getVoices() || [];
    const prefix = utterance.lang.slice(0, 2).toLowerCase();
    const byLang = voices.find(
      (v) => String(v.lang || "").toLowerCase().indexOf(prefix) === 0);
    if (byLang) utterance.voice = byLang;
  }

  utterance.onstart = () => {
    state.voice.speaking = true;
    $("micBtn").disabled = true;
    setVoiceState("speaking");
  };

  const finish = () => {
    state.voice.speaking = false;
    $("micBtn").disabled = false;
    clearVoiceState();
  };

  utterance.onend = finish;
  utterance.onerror = () => {
    finish();
    toast("Voice playback failed");
  };

  window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  if (state.voice.audioEl) {
    try { state.voice.audioEl.pause(); } catch (error) { /* ignore */ }
    state.voice.audioEl = null;
  }
  state.voice.speaking = false;
  $("micBtn").disabled = false;
  clearVoiceState();
}


// ==========================================================
// OFFLINE_DEGRADED_STATUS_UI_V1 — CONNECTIVITY / CAPABILITY STATUS
//
// ONE calm, persistent indicator (the existing runtime pill) that tells
// the user at a glance whether ArchitectOS is fully online, is running
// in a limited mode, or is fully offline — WITHOUT reading the chat.
//
// It is UI-ONLY. It adds no connectivity probing of its own: the truth
// already exists on the backend and is reused verbatim, so this never
// duplicates the offline logic that `OFFLINE_FIRST` established:
//
//   * tts_persian_provider.{installed, reachable, offline, available}
//     — reported by GET /api/voice/status (`audit_voice()`); the
//       `reachable` field is the backend's own bounded online probe.
//   * stt_available — local STT stays usable offline.
//   * /status.image_server — the render/image backend.
//   * `degraded` / `degraded_reason` on chat replies — set by the
//       canonical chat path when the LOCAL LLM engine is unavailable.
//
// navigator.onLine is deliberately NOT a source of truth: it reports
// "connected to a network", not "our services are reachable", and the
// backend already reports the latter more accurately.
//
// STATE MODEL (matches the phase brief):
//   ONLINE   — every expected online capability is currently reachable.
//   DEGRADED — one or more important capabilities are unavailable, but
//              ArchitectOS is still working (e.g. online Persian TTS
//              unreachable, or the local reasoning engine unavailable).
//   OFFLINE  — the app cannot reach its own site/runtime at all, so the
//              only truthful statement is that online services are out.
//
// The whole app is never labelled "offline" merely because one provider
// fails while everything else still works.
// ==========================================================

// The three visible states, in Persian, exactly as suggested by the
// brief. These are labels — the CSS classes already exist (see
// style.css: `.runtime-online/.runtime-degraded/.runtime-offline`).
const CONNECTIVITY_ONLINE = "آنلاین";
const CONNECTIVITY_OFFLINE = "آفلاین";
const CONNECTIVITY_DEGRADED = "حالت محدود";

const CONNECTIVITY_DETAILS = {
  online: "همهٔ قابلیت‌های آنلاین در دسترس هستند.",
  degraded:
    "قابلیت‌های محلی فعال هستند؛ برخی سرویس‌های آنلاین در دسترس نیستند.",
  offline:
    "اتصال به سرویس‌های آنلاین برقرار نیست؛ قابلیت‌های محلی ArchitectOS فعال هستند.",
};

// Last state we actually RENDERED. Used only to avoid flicker: a
// transient failure must not visibly flip the pill back and forth.
// `null` means "nothing rendered yet".
let _connectivityState = null;
// Set when the backend itself could not be reached on the last refresh
// (as opposed to a capability inside it being unavailable). A single
// such blip is held back from repainting if we were already online.
let _connectivityMisses = 0;

// Derive the state from the EXISTING backend data. Never invented.
//
// `runtime`  — the /status payload (image_server).
// `capability` — the /api/voice/status payload (may be null/absent).
// `probeOk`  — whether the refresh round itself reached the backend.
function deriveConnectivity(runtime, capability, probeOk) {
  // The runtime probe not reaching the backend at all is the strongest
  // offline signal we have. It is only trusted after one confirming
  // miss, so a momentary blip does not flash the pill.
  if (!probeOk) return "offline";

  const cap = (capability && capability.voice) || {};

  // The capability endpoint refusing to answer is itself an important
  // capability being unavailable: the app is up, but the online speech
  // service (and everything behind the core) cannot be reached. That is
  // DEGRADED, not OFFLINE — local ArchitectOS keeps working.
  const capabilityUnreachable =
    state.connectivityCapabilityOk === false;

  // An important capability that is genuinely unreachable -> limited.
  // The backend reports this truthfully; we do not re-probe it.
  const provider = cap.tts_persian_provider || {};
  const persianVoiceDown =
    provider.installed === true
    && (provider.offline === true || provider.reachable === false);

  // A degraded chat reply already carries its own truthful reason.
  const chatDegraded = state.connectivityChatDegraded === true;

  // The render/image backend being degraded is important but local
  // ArchitectOS still works -> limited, not offline.
  const runtimeDegraded =
    !runtime || runtime.image_server !== "online";

  if (capabilityUnreachable || persianVoiceDown || chatDegraded
      || runtimeDegraded) {
    return "degraded";
  }
  return "online";
}

// Render the state into BOTH pills (home header + workspace header).
// Calm and persistent: no toasts, no chat messages, no animation except
// the dot colour defined by the existing CSS classes.
function renderConnectivity(nextState, opts) {
  const options = opts || {};

  // Flicker guard: when we were already online, require two consecutive
  // misses before showing an offline/limited state. Recovery to online
  // is always immediate (the brief asks for automatic recovery).
  if (nextState !== "online" && _connectivityState === "online") {
    _connectivityMisses += 1;
    if (_connectivityMisses < 2 && !options.force) return;
  }
  if (nextState === "online") _connectivityMisses = 0;

  _connectivityState = nextState;

  const label = nextState === "online"
    ? CONNECTIVITY_ONLINE
    : nextState === "offline"
      ? CONNECTIVITY_OFFLINE
      : CONNECTIVITY_DEGRADED;

  const title = CONNECTIVITY_DETAILS[nextState] || "";

  ["homeRuntime", "wsRuntime"].forEach((id) => {
    const node = $(id);
    if (!node) return;
    node.className = "runtime-pill runtime-" + nextState;
    const span = node.querySelector(".runtime-label");
    if (span) span.textContent = label;
    node.title = label + " — " + title;
  });
}

// Refresh connectivity from the truthful backend sources. Reuses
// `loadVoiceCapability()` (which already stores the full payload in
// `state.voice.capability`) so no duplicate fetch is added when a
// project is open. On the home screen there is no project, so the
// capability endpoint is queried directly — the same endpoint the rest
// of the app already trusts.
async function refreshConnectivity() {
  let runtime = null;
  let probeOk = true;

  try {
    const { data } = await api("/status");
    runtime = data || null;
    probeOk = !!data;
  } catch (error) {
    runtime = null;
    probeOk = false;
  }

  state.connectivityRuntime = runtime;

  let capability = state.voice.capability;

  // Refresh the capability payload from the backend so recovery is
  // real: if the online Persian voice comes back, the pill must return
  // to ONLINE on its own. This is the SAME endpoint `loadVoiceCapability`
  // already uses — no duplicate connectivity logic, no extra probe.
  //
  // The response is only allowed to overwrite the stored settings the
  // first time (or when the server actually returns them), so a voice
  // the user just picked is never silently reverted by a status poll.
  try {
    const { data } = await api("/api/voice/status");
    if (data && data.status === "success") {
      const firstHydration = !state.voice.capability;
      capability = data;
      state.voice.capability = data;
      state.connectivityCapabilityOk = true;
      if (firstHydration && data.settings) {
        state.voice.settings = Object.assign(
          state.voice.settings, data.settings
        );
      }
    } else {
      // Truthful: the endpoint answered, but not with a capability
      // report (e.g. the core is unreachable -> `status:"error"`).
      state.connectivityCapabilityOk = false;
    }
  } catch (error) {
    state.connectivityCapabilityOk = false;
  }

  renderConnectivity(deriveConnectivity(runtime, capability, probeOk));
}

// Kept as a thin alias so the existing boot/poll wiring (and the
// deep-link/advanced paths) keep working unchanged.
async function checkRuntime() {
  await refreshConnectivity();
}

// Called from the chat path when a reply arrives carrying the truthful
// `degraded` metadata the canonical path now sets. It updates the pill
// WITHOUT touching the transcript and never toasts.
function noteChatConnectivity(payload) {
  const degraded = !!(payload && payload.degraded);
  const changed = (state.connectivityChatDegraded === true) !== degraded;
  state.connectivityChatDegraded = degraded;

  if (degraded && changed) {
    // Scoped, once — not on every turn. The pill is the persistent
    // signal; this is only the one-line explanation. Persian text keeps
    // the workspace language consistent.
    const reason = payload.degraded_reason || "llm_unavailable";
    if (reason === "llm_unavailable") {
      toast("موتور استدلال محلی در دسترس نیست؛ پاسخ متنی ادامه دارد.", 4200);
    }
  }

  // Re-derive immediately so the pill reflects the new truth. A reply
  // that says "the reasoning engine is unavailable" is DEFINITIVE, not a
  // transient blip, so it bypasses the flicker guard (`force`).
  renderConnectivity(
    deriveConnectivity(state.connectivityRuntime, state.voice.capability, true),
    { force: true }
  );
}

// TTS-side scoped notice: shown ONLY when a Persian reply was going to
// be spoken and the server voice is genuinely unreachable. Never spams.
function notePersianVoiceUnavailable() {
  if (state.connectivityPersianVoiceNotified) return;
  state.connectivityPersianVoiceNotified = true;
  toast("صدای فارسی آنلاین در دسترس نیست؛ پاسخ متنی ادامه دارد.", 4200);
}


// ==========================================================
// WIRING
// ==========================================================

function wire() {
  $("newProjectBtn").onclick = createProject;
  $("sideNewProject").onclick = createProject;
  $("backHome").onclick = showHome;

  // PROJECT_CONTEXT_MENU_V1 — one-time wiring of the shared project menu.
  wireProjectMenu();
  $("renameProjectBtn").onclick = renameProject;
  $("archiveProjectBtn").onclick = archiveProject;
  $("deleteProjectBtn").onclick = deleteProject;
  $("exportProjectBtn").onclick = exportProject;
  $("sendBtn").onclick = sendMessage;
  $("runPythonBtn").onclick = openExecutionModal;
  $("draftVerifyBtn").onclick = openDraftVerifyModal;
  $("draftVerifyCloseBtn").onclick = closeDraftVerifyModal;
  $("loadPendingDraftBtn").onclick = loadPendingDraft;
  $("confirmDraftVerifyBtn").onclick = confirmDraftVerification;
  $("executionCloseBtn").onclick = closeExecutionModal;
  $("loadExecutionPreviewBtn").onclick = loadExecutionPreview;
  $("confirmRunBtn").onclick = confirmExecutionRun;

  // Separate packaging consent — sandbox-only Windows EXE build.
  $("packageExeBtn").onclick = openPackageModal;
  $("packageCloseBtn").onclick = closePackageModal;
  $("preparePackageBtn").onclick = preparePackageJob;
  $("checkPackageBtn").onclick = checkPackageResult;

  // ARCHITECTURAL_LEARNING_UI_01 — turn controls + teaching toggle.
  $("stopBtn").onclick = stopTurn;
  $("cancelBtn").onclick = cancelTurn;
  $("retryBtn").onclick = retryTurn;
  $("teachToggle").onclick = toggleTeaching;

  $("advancedToggle").onclick = () => {
    $("advancedRow").classList.toggle("hidden");
    $("voiceRow").classList.toggle("hidden");
    if ($("preciseRow")) $("preciseRow").classList.toggle("hidden");
  };

  // PRECISE_EDIT_UI_V1 — the mask input is only usable when the user asked
  // for a localized edit, so it starts disabled and follows the checkbox.
  if ($("localizedEditToggle")) {
    $("localizedEditToggle").onchange = syncMaskControls;
    syncMaskControls();
  }

  // REFERENCE_TRANSFER_POLICY_V1 — remember that the user expressed a choice,
  // so an explicit OFF is distinguishable from an untouched toggle.
  if ($("conditionedToggle")) {
    $("conditionedToggle").onchange = () => {
      $("conditionedToggle").dataset.touched = "1";
    };
  }
  $("toggleArchived").onclick = () => {
    const grid = $("archivedProjects");
    grid.classList.toggle("hidden");
    $("toggleArchived").textContent =
      grid.classList.contains("hidden") ? "Show" : "Hide";
  };
  $("imageInput").onchange = onAttach;

  // ---- KROCKI_SITE_UPLOAD_V27 ----
  bindKrockiUpload();

  // ---- VOICE_07 ----
  $("micBtn").onclick = startRecording;
  $("recStopBtn").onclick = stopRecording;
  $("recCancelBtn").onclick = cancelRecording;

  // PERSIAN_VOICE_QUALITY_V2 / PHASE 1 — the voice-send mode toggle.
  // Purely a client-side choice (edit-before-send vs send-immediately);
  // it does not alter the canonical voice API or the chat path.
  if ($("voiceSendModeSelect")) {
    $("voiceSendModeSelect").value = state.voice.mode;
    $("voiceSendModeSelect").onchange = () => {
      state.voice.mode = $("voiceSendModeSelect").value === "direct"
        ? "direct" : "dictate";
      if (state.voice.status === "dictated") clearVoiceState();
    };
  }

  ["voiceReplySelect", "ttsVoiceSelect", "sttLanguageSelect"].forEach((id) => {
    const node = $(id);
    if (node) node.onchange = saveVoiceSettings;
  });

  if (window.speechSynthesis) {
    // Voices may load asynchronously in some browsers.
    window.speechSynthesis.onvoiceschanged = () => {
      if (state.voice.capability) loadVoiceCapability();
    };
  }

  // OFFLINE_DEGRADED_STATUS_UI_V1 — when the tab becomes visible again
  // (the user came back after the network changed), re-derive once. The
  // brief asks for automatic recovery without aggressive polling, so
  // this is event-driven, not a second timer.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshConnectivity();
  });

  // ARCHITECTURAL_LEARNING_UI_01 — multiline composer: Enter inserts a
  // newline; Ctrl/Cmd+Enter sends. Long teaching messages stay intact.
  $("message").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      sendMessage();
    }
  });
  $("message").addEventListener("input", autoGrowMessage);

  // ARCHITECTURAL_LEARNING_UI_01 — initial visible state.
  refreshUiState();
  autoGrowMessage();
}

window.addEventListener("DOMContentLoaded", async () => {
  wire();

  // ==================================================
  // UI_FINAL_POLISH_STARTUP_V1 — THE PROJECT LIST MUST NOT WAIT FOR THE
  // VOICE PROBE
  //
  // Measured dependency chain (runs/ui_workspace_stability_v1/startup.py):
  //
  //   checkRuntime() -> refreshConnectivity()
  //        GET /status              ~1 ms
  //        GET /api/voice/status    ~6.3-6.8 s   <-- the entire delay
  //   loadProjects()
  //        GET /api/projects        ~95 ms
  //
  // `loadProjects()` reads nothing that `refreshConnectivity()` writes:
  // the list comes from /api/projects alone, and service health is
  // painted from `state.connectivityRuntime` by `renderConnectivity()`.
  // So the list starts first and the probe is awaited afterwards.
  //
  // `applyDeepLink()` deliberately keeps its ORIGINAL position, after the
  // probe has settled, so the navigation/deep-link contract is unchanged.
  // ==================================================
  const runtimeProbe = checkRuntime().catch(() => null);

  // The static markup ships `#recentEmpty` visible, so a cold boot used to
  // claim "No projects yet" for the whole probe. Keep it hidden until a
  // load has actually reported a count — `renderHomeProjects()` is the
  // only thing allowed to show it again.
  $("recentEmpty").classList.add("hidden");

  try {
    await loadProjects();
  } catch (error) {
    // A failed list must not abort boot. The grid stays empty and the
    // runtime pill reports the outage truthfully.
  }

  // Never let a rejected probe escape as an unhandled startup rejection.
  await runtimeProbe;
  setInterval(checkRuntime, 15000);

  try {
    await applyDeepLink();
  } catch (error) {
    // A bad deep link must not leave the boot sequence half-finished.
  }
});


// ==========================================================
// DEEP LINKS
//
//   #/project/<project_id>                 open a project
//   #/project/<project_id>?advanced=1      show advanced controls
//   #/project/<project_id>?confirm=delete  open the delete confirm
//   #/project/<project_id>?asset=<id>      preselect an asset
//
// Useful for support/debugging and for automated visual capture.
// ==========================================================

function parseDeepLink() {
  const hash = String(location.hash || "").replace(/^#/, "");
  if (!hash) return null;

  const [path, query] = hash.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = {};
  (query || "").split("&").filter(Boolean).forEach((pair) => {
    const [k, v] = pair.split("=");
    params[decodeURIComponent(k)] = decodeURIComponent(v || "");
  });

  if (parts[0] === "project" && parts[1]) {
    return { projectId: parts[1], params };
  }
  return null;
}

async function applyDeepLink() {
  const link = parseDeepLink();

  if (!link) {
    // ==================================================
    // UI_WORKSPACE_STABILITY_V1 — NEVER YANK A WORKSPACE THE USER
    // ALREADY OPENED
    //
    // The boot sequence is `await checkRuntime()` -> `loadProjects()`
    // -> `applyDeepLink()`, and `checkRuntime()` awaits a runtime
    // status call that has been measured at ~7.6 s. A user (or an
    // acceptance driver) can therefore open a project BEFORE this
    // pass runs.
    //
    // This branch used to call `showHome()` unconditionally, so it
    // silently hid `#workspaceView` ~4 s after the project opened.
    // Because `#activityStatus` lives INSIDE `#workspaceView`, the
    // render progress pill kept updating in the DOM while being
    // completely invisible to the user.
    //
    // `openProject()` deliberately does not write `location.hash`, so
    // "no link" is not evidence that no project is open. Only take the
    // home path when no project has been entered.
    //
    // UI_FINAL_POLISH_STARTUP_V1 — an EXPLICIT `#/new` is an instruction,
    // not a default, so it is resolved BEFORE the preservation guard.
    // The guard used to return first, which silently swallowed the
    // requested New Project action whenever a workspace was already open.
    // The dialog is now opened without tearing down that workspace, so
    // cancelling it leaves the user exactly where they were.
    // ==================================================
    const wantsNewProject = String(location.hash || "") === "#/new";

    if (wantsNewProject) {
      if (!(state.view === "workspace" && state.projectId)) {
        showHome();
      }
      await createProject();
      return;
    }

    if (state.view === "workspace" && state.projectId) {
      return;
    }

    showHome();
    return;
  }

  await openProject(link.projectId);

  if (link.params.asset) {
    await showAssetDetails(link.params.asset);
  }

  if (link.params.advanced === "1") {
    $("advancedRow").classList.remove("hidden");
    $("voiceRow").classList.remove("hidden");
  }

  if (link.params.confirm === "delete") {
    // Visual/support affordance: open the destructive confirmation so it
    // can be reviewed without performing the deletion.
    await openModal({
      title: "Delete Project",
      body: 'Delete "' + ((state.project || {}).project_name || "") + '"?\n\n'
        + "This will remove this project and its managed project files.\n"
        + "Files are moved to a quarantine folder, not erased.",
      confirmLabel: "Delete Project",
      cancelLabel: "Cancel",
      danger: true,
    });
  }

  if (link.params.action === "mic") {
    // Support/visual affordance: begin microphone capture so the
    // recording state can be reviewed or captured.
    await startRecording();
  }
}


// ==========================================================
// VISUAL_REFERENCE_UX_V2 — REFERENCE PICKER
//
// A selector, not a management application. The browser receives an ID and
// a preview URL; it never names a filesystem path. Metadata is displayed with
// its authority stated so a declared hint is never mistaken for a certified
// classification.
// ==========================================================

state.referenceId = null;
state.reference = null;

let referenceCache = null;

// Local to this module: the file has no shared escaper, and injecting one
// globally could collide with another module's helper.
function referenceEsc(value) {
  return String(value === undefined || value === null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function referenceRenderChip() {
  const chip = $("referenceChip");
  if (!chip) return;
  if (!state.referenceId) {
    chip.classList.add("hidden");
    chip.textContent = "";
    return;
  }
  const ref = state.reference || { reference_id: state.referenceId };
  chip.classList.remove("hidden");
  chip.innerHTML =
    '<span class="reference-chip-label">Reference</span>'
    + '<strong>' + referenceEsc(ref.reference_id) + "</strong>"
    + (ref.declared_hint
        ? '<span class="reference-chip-hint">' + referenceEsc(ref.declared_hint) + "</span>"
        : "")
    + '<span class="reference-chip-authority">unverified</span>'
    + '<button type="button" id="referenceClear" class="reference-chip-clear"'
    + ' title="Clear the selected reference">×</button>';
  const clear = $("referenceClear");
  if (clear) {
    clear.addEventListener("click", () => {
      state.referenceId = null;
      state.reference = null;
      referenceRenderChip();
      if (referenceCache) referenceRenderGrid(referenceCache);
    });
  }
}

function referenceRenderGrid(items) {
  const grid = $("referenceGrid");
  if (!grid) return;
  if (!items.length) {
    grid.innerHTML = '<p class="reference-empty">No references match.</p>';
    return;
  }
  grid.innerHTML = items.map((item) => {
    const selected = item.reference_id === state.referenceId;
    const thumb = item.preview_url
      ? '<img loading="lazy" src="' + item.preview_url + '" alt="' + referenceEsc(item.reference_id) + '">'
      : '<div class="reference-thumb-missing">no preview</div>';
    return (
      '<button type="button" class="reference-card' + (selected ? " is-selected" : "") + '"'
      + ' data-reference-id="' + referenceEsc(item.reference_id) + '">'
      + thumb
      + '<span class="reference-card-id">' + referenceEsc(item.reference_id) + "</span>"
      + (item.declared_hint
          ? '<span class="reference-card-hint">' + referenceEsc(item.declared_hint) + "</span>"
          : "")
      + "</button>"
    );
  }).join("");

  grid.querySelectorAll("[data-reference-id]").forEach((node) => {
    node.addEventListener("click", () => {
      const id = node.getAttribute("data-reference-id");
      const item = (referenceCache || []).find((r) => r.reference_id === id);
      if (!item) return;
      // Explicit selection. Nothing is re-ranked or substituted.
      state.referenceId = item.reference_id;
      state.reference = item;
      referenceRenderChip();
      referenceRenderGrid(referenceCache);
    });
  });
}

async function referenceLoad() {
  const grid = $("referenceGrid");
  if (grid) grid.innerHTML = '<p class="reference-empty">Loading references…</p>';
  const result = await api("/api/references");
  if (!result.ok || !result.data || !Array.isArray(result.data.references)) {
    if (grid) {
      grid.innerHTML = '<p class="reference-empty">Reference library unavailable.</p>';
    }
    return;
  }
  referenceCache = result.data.references;
  referenceRenderGrid(referenceCache);
}

function referenceOpen() {
  const panel = $("referencePanel");
  if (!panel) return;
  panel.classList.remove("hidden");
  const search = $("referenceSearch");
  if (search) {
    search.value = "";
    search.focus();
  }
  if (referenceCache) referenceRenderGrid(referenceCache);
  else referenceLoad();
}

function referenceClose() {
  const panel = $("referencePanel");
  if (panel) panel.classList.add("hidden");
}

function referenceWire() {
  const openBtn = $("referenceBtn");
  if (openBtn) openBtn.addEventListener("click", referenceOpen);

  const closeBtn = $("referenceClose");
  if (closeBtn) closeBtn.addEventListener("click", referenceClose);

  const search = $("referenceSearch");
  if (search) {
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      const items = (referenceCache || []).filter((item) => {
        if (!q) return true;
        const hay = (
          item.reference_id + " " + (item.declared_hint || "")
        ).toLowerCase();
        return hay.includes(q);
      });
      referenceRenderGrid(items);
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", referenceWire);
} else {
  referenceWire();
}
