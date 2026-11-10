/* Hands a finished PNG to the user. Every export (the chart's Save Plot and the
 * three card types' Save button) ends here, through downloadCanvasAsPng() in
 * chart-export.js.
 *
 * Two paths:
 *  - Desktop (a mouse): an ordinary file download.
 *  - Touch devices that can share files (iOS, Android): the system share sheet,
 *    which also offers Save Image and Copy. iOS only allows share() right after
 *    a tap, and an export takes seconds, so the tap that started it has often
 *    expired by now. When it has, an "Image ready" bar asks for a fresh tap
 *    (Share / Save, or Copy through the clipboard) instead of failing silently.
 *
 * The same bar shows "Preparing image…" from the moment the export starts, so a
 * slow phone does not look like a dead button.
 */

// How long a blob URL stays valid after a download click. Revoking it right away
// can cancel the download on Safari, which reads the URL after click() returns.
const BLOB_URL_LIFETIME_MS = 60000;

const STATUS_AUTO_HIDE_MS = 2500;

let statusEl = null;
let textEl = null;
let actionsEl = null;
let hideTimer = null;

function ensureStatusBar() {
  if (statusEl) return statusEl;

  statusEl = document.createElement("div");
  statusEl.id = "export-status";
  statusEl.className = "export-status";
  statusEl.setAttribute("role", "status");
  statusEl.setAttribute("aria-live", "polite");
  statusEl.hidden = true;

  textEl = document.createElement("span");
  textEl.className = "export-status-text";

  actionsEl = document.createElement("span");
  actionsEl.className = "export-status-actions";

  statusEl.append(textEl, actionsEl);

  // A tap on the bar must not reach the document-level "click outside" handlers
  // (they close the filters drawer and the Teams dropdown).
  statusEl.addEventListener("click", (e) => e.stopPropagation());

  document.body.appendChild(statusEl);
  return statusEl;
}

function setStatus(message, actions = [], { ready = false } = {}) {
  ensureStatusBar();
  clearTimeout(hideTimer);

  // "Image ready" is a popup with a backdrop; the other messages are a small pill.
  statusEl.classList.toggle("is-ready", ready);
  textEl.textContent = message;
  actionsEl.replaceChildren(...actions);
  statusEl.hidden = false;
}

function statusButton(label, onClick, { primary = false } = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = primary ? "export-status-btn is-primary" : "export-status-btn";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

export function hideExportStatus() {
  clearTimeout(hideTimer);
  if (statusEl) statusEl.hidden = true;
}

function hideExportStatusSoon() {
  clearTimeout(hideTimer);
  hideTimer = setTimeout(hideExportStatus, STATUS_AUTO_HIDE_MS);
}

// Shows "Preparing image…" and resolves once the browser has had a chance to
// paint it, so the heavy export work that follows cannot hide it.
export function showExportStatus(message = "Preparing image…") {
  setStatus(message);

  return new Promise((resolve) => {
    const done = () => resolve();
    requestAnimationFrame(() => setTimeout(done, 0));
    setTimeout(done, 120); // A hidden tab never fires animation frames.
  });
}

export function failExportStatus(message = "Could not create the image.") {
  setStatus(message);
  hideExportStatusSoon();
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("canvas.toBlob returned null"));
    }, "image/png");
  });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);

  anchor.click();
  anchor.remove();

  setTimeout(() => URL.revokeObjectURL(url), BLOB_URL_LIFETIME_MS);
}

// The share sheet is used on touch devices only, and only when the browser can
// share this very file.
function usesShareSheet(file) {
  if (typeof navigator.share !== "function" || typeof navigator.canShare !== "function") return false;
  if (!window.matchMedia("(pointer: coarse)").matches) return false;

  try {
    return navigator.canShare({ files: [file] });
  } catch {
    return false;
  }
}

function canCopyImage() {
  return typeof window.ClipboardItem === "function" && Boolean(navigator.clipboard && navigator.clipboard.write);
}

// Share the file. Resolves "shared", "cancelled" (the user closed the sheet) or
// "failed" (the browser refused, for example because the tap had expired).
async function shareFile(file) {
  try {
    await navigator.share({ files: [file] });
    return "shared";
  } catch (err) {
    return err && err.name === "AbortError" ? "cancelled" : "failed";
  }
}

async function copyImage(blob) {
  try {
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    setStatus("Image copied");
    hideExportStatusSoon();
  } catch (err) {
    console.error("Copying the image failed:", err);
    setStatus("Could not copy the image");
    hideExportStatusSoon();
  }
}

// A fresh tap is needed: the bar's buttons are that tap.
function showReadyBar(blob, file, filename) {
  const actions = [
    statusButton(
      "Share / Save",
      async () => {
        const result = await shareFile(file);
        if (result === "failed") downloadBlob(blob, filename);
        hideExportStatus();
      },
      { primary: true }
    ),
  ];

  if (canCopyImage()) actions.push(statusButton("Copy", () => copyImage(blob)));
  actions.push(statusButton("Close", hideExportStatus));

  setStatus("Image ready", actions, { ready: true });
}

// Hands the canvas's PNG to the user and releases the canvas's memory.
export async function deliverPng(canvas, filename) {
  const startedAt = performance.now();
  const width = canvas.width;
  const height = canvas.height;
  const blob = await canvasToBlob(canvas);

  // Safari keeps a canvas's pixels until garbage collection; zeroing the size frees them now.
  canvas.width = 0;
  canvas.height = 0;

  const name = `${filename}.png`;
  const file = new File([blob], name, { type: "image/png" });
  const tapIsFresh = Boolean(navigator.userActivation && navigator.userActivation.isActive);

  console.info("[export]", {
    width,
    height,
    bytes: blob.size,
    tapIsFresh,
    encodeMs: Math.round(performance.now() - startedAt),
  });

  if (!usesShareSheet(file)) {
    downloadBlob(blob, name);
    hideExportStatus();
    return;
  }

  if (tapIsFresh) {
    const result = await shareFile(file);
    if (result !== "failed") {
      hideExportStatus();
      return;
    }
  }

  showReadyBar(blob, file, name);
}
