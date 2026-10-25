const inbox = document.getElementById("inbox");
const summary = document.getElementById("summary");
const batchStatus = document.getElementById("batch-status");
let historySignature = null;

function renderWorkerStatus(status) {
  if (status.state === "running") {
    batchStatus.innerHTML = '<div class="loading"><span class="loading-spinner" aria-hidden="true"></span><span>Evaluating batch…</span></div>';
    return;
  }
  if (status.state === "error") {
    batchStatus.textContent = `Last batch failed: ${status.message || "unknown error"}`;
    batchStatus.className = "batch-error";
    return;
  }
  if (status.state === "completed") {
    batchStatus.textContent = `Last batch finished · ${status.lessonCount || 0} lesson${status.lessonCount === 1 ? "" : "s"}`;
    batchStatus.className = "batch-complete";
    return;
  }
  batchStatus.textContent = "No batch is running";
  batchStatus.className = "batch-idle";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

function render(history) {
  const byFeature = new Map();
  for (const lesson of history.lessons || []) {
    const identity = lesson.helpTag
      ? `help:${lesson.helpTag}`
      : `concept:${String(lesson.concept || "").trim().toLowerCase()}`;
    if (!byFeature.has(identity)) byFeature.set(identity, lesson);
  }
  const lessons = [...byFeature.values()];
  const active = lessons.filter((lesson) => !["dismissed", "known"].includes(lesson.status));
  summary.textContent = `${active.length} lesson${active.length === 1 ? "" : "s"} to review · ${lessons.length} total`;
  if (!active.length) {
    inbox.innerHTML = '<section class="empty"><h2>No lessons yet</h2><p>Run <code>:VimCoachSync</code> in Neovim after capturing a few edits.</p></section>';
    return;
  }
  inbox.innerHTML = active.map((lesson) => `
    <article class="card" data-id="${escapeHtml(lesson.lessonId)}">
      <div class="card-top"><span class="tag">New Vim feature</span><span>${lesson.savedLogicalKeys ?? "?"} keys saved</span></div>
      <h2>${escapeHtml(lesson.concept)}</h2>
      <p class="lesson-intro">${escapeHtml(lesson.explanation)}</p>
      <p class="sequence"><span>Example binding</span><code>${escapeHtml(lesson.compiledTokens?.join(""))}</code></p>
      ${lesson.helpTag ? `<p class="help-link">Open the full documentation with <code>:help ${escapeHtml(lesson.helpTag)}</code></p>` : ""}
      <p class="scope">Verified replay · ${lesson.originalLogicalKeys ?? "?"} → ${lesson.candidateLogicalKeys ?? "?"} logical keys</p>
      <div class="actions">
        <button data-status="known">I know this</button>
        <button data-status="dismissed" class="secondary">Dismiss</button>
        <button disabled title="Practice needs an explicit opt-in snapshot protocol">Practice (next step)</button>
      </div>
    </article>
  `).join("");
  inbox.querySelectorAll("button[data-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      await window.vimCoachReview.setStatus(button.closest(".card").dataset.id, button.dataset.status);
      renderHistoryIfChanged(await window.vimCoachReview.getHistory());
    });
  });
}

function renderHistoryIfChanged(history) {
  const signature = JSON.stringify(history);
  if (signature === historySignature) return;
  historySignature = signature;
  render(history);
}

document.getElementById("reset").addEventListener("click", async () => {
  renderHistoryIfChanged(await window.vimCoachReview.reset());
});

window.vimCoachReview.getHistory().then(renderHistoryIfChanged);
window.vimCoachReview.onHistoryChanged(async () => {
  renderHistoryIfChanged(await window.vimCoachReview.getHistory());
});
window.vimCoachReview.getWorkerStatus().then(renderWorkerStatus);
setInterval(() => window.vimCoachReview.getWorkerStatus().then(renderWorkerStatus), 500);
