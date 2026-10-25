const inbox = document.getElementById("inbox");
const lessonSummary = document.getElementById("lesson-summary");
const lessonCount = document.getElementById("lesson-count");
const batchStatus = document.getElementById("batch-status");
const challengeList = document.getElementById("challenge-list");
const achievementList = document.getElementById("achievement-list");
const achievementCount = document.getElementById("achievement-count");
const goalsSummary = document.getElementById("goals-summary");
const statStrip = document.getElementById("stat-strip");
const levelBadge = document.getElementById("level-badge");
const statsDashboard = document.getElementById("stats-dashboard");

let history = { lessons: [] };
let goalsState = { goals: [] };
let historySignature = null;
let goalsSignature = null;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

function renderWorkerStatus(status) {
  batchStatus.className = "";
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
    batchStatus.textContent = `Batch complete · ${status.lessonCount || 0} new lesson${status.lessonCount === 1 ? "" : "s"}`;
    batchStatus.className = "batch-complete";
    return;
  }
  batchStatus.textContent = "Coach ready";
  batchStatus.className = "batch-idle";
}

function renderKeySequence(tokens, className = "") {
  if (!Array.isArray(tokens) || !tokens.length) return '<span class="unknown-key">?</span>';
  return `<span class="key-sequence ${className}">${tokens.map((token) => `<kbd>${escapeHtml(token)}</kbd>`).join("")}</span>`;
}

function metrics(goals) {
  const result = { active: 0, paused: 0, learned: 0, uses: 0, target: 0 };
  for (const goal of goals) {
    result.uses += Number(goal.progress) || 0;
    result.target += Number(goal.target) || 0;
    if (goal.status === "completed") result.learned += 1;
    else if (goal.status === "paused") result.paused += 1;
    else result.active += 1;
  }
  result.mastery = result.target ? Math.round((result.uses / result.target) * 100) : 0;
  return result;
}

function renderStat(label, value, detail, tone = "blue") {
  return `
    <article class="stat-card ${tone}">
      <span class="stat-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <span class="stat-detail">${escapeHtml(detail)}</span>
    </article>
  `;
}

function renderChallenge(goal) {
  const progress = Number(goal.progress) || 0;
  const target = Number(goal.target) || 0;
  const percentage = target ? Math.min(100, Math.round((progress / target) * 100)) : 0;
  const progressStep = Math.round(percentage / 5) * 5;
  const paused = goal.status === "paused";
  const remaining = Math.max(0, target - progress);
  return `
    <article class="challenge-card ${paused ? "paused" : ""}" data-feature="${escapeHtml(goal.featureId)}">
      <div class="challenge-key">${renderKeySequence(goal.binding, "challenge-binding")}</div>
      <div class="challenge-body">
        <div class="challenge-heading">
          <div>
            <span class="challenge-state">${paused ? "PAUSED" : "ACTIVE CHALLENGE"}</span>
            <h3>${escapeHtml(goal.title || goal.featureId)}</h3>
          </div>
          <strong class="challenge-score">${progress}<span> / ${target}</span></strong>
        </div>
        <div class="progress-track" role="progressbar" aria-label="${escapeHtml(goal.title)} progress" aria-valuemin="0" aria-valuemax="${target}" aria-valuenow="${progress}">
          <span class="progress-fill progress-${progressStep}"></span>
        </div>
        <div class="challenge-footer">
          <span>${paused ? "Resume when you are ready" : `${remaining} successful use${remaining === 1 ? "" : "s"} to mastery`}</span>
          <button class="goal-toggle secondary compact" data-status="${paused ? "active" : "paused"}">${paused ? "Resume" : "Pause"}</button>
        </div>
      </div>
    </article>
  `;
}

function renderAchievement(goal) {
  const date = goal.completedAt ? goal.completedAt.slice(0, 10) : "Mastered";
  return `
    <article class="achievement-card">
      <div class="achievement-icon" aria-hidden="true">✓</div>
      <div>
        <span>${escapeHtml(date)}</span>
        <h3>${escapeHtml(goal.title || goal.featureId)}</h3>
        ${renderKeySequence(goal.binding, "achievement-binding")}
      </div>
    </article>
  `;
}

function bindGoalActions() {
  document.querySelectorAll(".goal-toggle").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".challenge-card");
      await window.vimCoachReview.setGoalStatus(card.dataset.feature, button.dataset.status);
      updateGoals(await window.vimCoachReview.getGoals());
    });
  });
}

function renderGoals() {
  const goals = Array.isArray(goalsState.goals) ? goalsState.goals : [];
  const totals = metrics(goals);
  const activeGoals = goals
    .filter((goal) => goal.status !== "completed")
    .sort((left, right) => (left.status === "paused") - (right.status === "paused") || (right.progress || 0) - (left.progress || 0));
  const completed = goals
    .filter((goal) => goal.status === "completed")
    .sort((left, right) => String(right.completedAt || "").localeCompare(String(left.completedAt || "")));

  levelBadge.textContent = `LEVEL ${totals.learned + 1}`;
  goalsSummary.textContent = goals.length
    ? `${totals.active} active · ${totals.paused} paused · keep building muscle memory`
    : "New lessons become challenges as you discover them.";
  statStrip.innerHTML = [
    renderStat("Learned", totals.learned, "features mastered", "gold"),
    renderStat("Active", totals.active, "challenges in play", "blue"),
    renderStat("Successful uses", totals.uses, "tracked in real edits", "green"),
    renderStat("Mastery", `${totals.mastery}%`, "of all goal reps", "purple"),
  ].join("");

  challengeList.innerHTML = activeGoals.length
    ? activeGoals.map(renderChallenge).join("")
    : `<section class="empty quest-empty"><div class="empty-icon">⌁</div><h3>No active challenges</h3><p>Capture edits and run <code>:VimCoachSync</code>. Your next lesson will become a challenge here.</p></section>`;

  achievementCount.textContent = `${completed.length} unlocked`;
  achievementList.innerHTML = completed.length
    ? completed.map(renderAchievement).join("")
    : '<section class="locked-achievement"><span aria-hidden="true">◇</span><div><h3>First mastery</h3><p>Complete a challenge to unlock your first achievement.</p></div></section>';
  bindGoalActions();
}

function renderSuggestionTitle(lesson) {
  const original = Array.isArray(lesson.originalTokens) && lesson.originalTokens.length;
  const replacement = Array.isArray(lesson.compiledTokens) && lesson.compiledTokens.length;
  if (!original || !replacement) return `<h3>${escapeHtml(lesson.concept)}</h3>`;
  return `
    <div class="suggestion-title" aria-label="${escapeHtml(lesson.originalTokens.join(""))} becomes ${escapeHtml(lesson.compiledTokens.join(""))}">
      ${renderKeySequence(lesson.originalTokens, "old-keys")}
      <span class="sequence-arrow" aria-hidden="true">→</span>
      ${renderKeySequence(lesson.compiledTokens, "new-keys")}
    </div>
    <h3 class="concept">${escapeHtml(lesson.concept)}</h3>
  `;
}

function renderLessons() {
  const byFeature = new Map();
  for (const lesson of history.lessons || []) {
    const identity = lesson.helpTag
      ? `help:${lesson.helpTag}`
      : `concept:${String(lesson.concept || "").trim().toLowerCase()}`;
    if (!byFeature.has(identity)) byFeature.set(identity, lesson);
  }
  const lessons = [...byFeature.values()];
  const active = lessons.filter((lesson) => !["dismissed", "known"].includes(lesson.status));
  lessonCount.textContent = active.length;
  lessonSummary.textContent = `${active.length} lesson${active.length === 1 ? "" : "s"} to review · ${lessons.length} discovered`;
  inbox.innerHTML = active.length ? active.map((lesson) => `
    <article class="lesson-card" data-id="${escapeHtml(lesson.lessonId)}">
      <div class="card-top"><span class="tag">NEW TECHNIQUE</span><span>−${lesson.savedLogicalKeys ?? "?"} keys</span></div>
      ${renderSuggestionTitle(lesson)}
      <p class="lesson-intro">${escapeHtml(lesson.explanation)}</p>
      ${lesson.helpTag ? `<p class="help-link">Learn more with <code>:help ${escapeHtml(lesson.helpTag)}</code></p>` : ""}
      <p class="scope">Replay verified · ${lesson.originalLogicalKeys ?? "?"} → ${lesson.candidateLogicalKeys ?? "?"} logical keys</p>
      <div class="actions">
        <button data-status="known">Already know it</button>
        <button data-status="dismissed" class="secondary">Dismiss</button>
      </div>
    </article>
  `).join("") : '<section class="empty"><div class="empty-icon">✓</div><h3>Inbox cleared</h3><p>Keep editing in Neovim and sync when you are ready for another lesson.</p></section>';

  inbox.querySelectorAll("button[data-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      await window.vimCoachReview.setStatus(button.closest(".lesson-card").dataset.id, button.dataset.status);
      updateHistory(await window.vimCoachReview.getHistory());
    });
  });
}

function renderStats() {
  const goals = Array.isArray(goalsState.goals) ? goalsState.goals : [];
  const totals = metrics(goals);
  const completion = goals.length ? Math.round((totals.learned / goals.length) * 100) : 0;
  const recent = goals
    .filter((goal) => goal.status === "completed")
    .sort((left, right) => String(right.completedAt || "").localeCompare(String(left.completedAt || "")))
    .slice(0, 8);
  statsDashboard.innerHTML = `
    <section class="mastery-panel">
      <div class="mastery-ring">
        <svg viewBox="0 0 44 44" aria-hidden="true">
          <circle class="ring-track" cx="22" cy="22" r="18"></circle>
          <circle class="ring-value" cx="22" cy="22" r="18" pathLength="100" stroke-dasharray="${completion} ${100 - completion}"></circle>
        </svg>
        <div><strong>${completion}%</strong><span>complete</span></div>
      </div>
      <div class="mastery-copy">
        <span class="section-kicker">OVERALL MASTERY</span>
        <h3>${totals.learned} of ${goals.length} features learned</h3>
        <p>You have logged ${totals.uses} successful uses across your Vim challenges.</p>
      </div>
    </section>
    <div class="stats-grid">
      ${renderStat("Completed", totals.learned, "earned achievements", "gold")}
      ${renderStat("In progress", totals.active, "active challenges", "blue")}
      ${renderStat("Paused", totals.paused, "waiting challenges", "purple")}
      ${renderStat("Total reps", totals.uses, "successful uses", "green")}
    </div>
    <section class="recent-panel">
      <div class="section-heading-row"><h2>Recently learned</h2><span class="muted">Latest achievements</span></div>
      ${recent.length ? recent.map((goal) => `
        <div class="recent-row">
          <span class="recent-check">✓</span>
          ${renderKeySequence(goal.binding, "recent-binding")}
          <strong>${escapeHtml(goal.title || goal.featureId)}</strong>
          <time>${escapeHtml(goal.completedAt ? goal.completedAt.slice(0, 10) : "")}</time>
        </div>
      `).join("") : '<p class="empty-copy">Completed challenges will build your learning history here.</p>'}
    </section>
  `;
}

function updateHistory(value) {
  const signature = JSON.stringify(value);
  if (signature === historySignature) return;
  historySignature = signature;
  history = value;
  renderLessons();
}

function updateGoals(value) {
  const signature = JSON.stringify(value);
  if (signature === goalsSignature) return;
  goalsSignature = signature;
  goalsState = value;
  renderGoals();
  renderStats();
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
    document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `${tab.dataset.view}-view`));
  });
});

document.getElementById("reset").addEventListener("click", async () => {
  updateHistory(await window.vimCoachReview.reset());
});

Promise.all([
  window.vimCoachReview.getHistory(),
  window.vimCoachReview.getGoals(),
]).then(([historyValue, goalsValue]) => {
  updateHistory(historyValue);
  updateGoals(goalsValue);
});
window.vimCoachReview.onHistoryChanged(async () => updateHistory(await window.vimCoachReview.getHistory()));
window.vimCoachReview.onGoalsChanged(async () => updateGoals(await window.vimCoachReview.getGoals()));
window.vimCoachReview.getWorkerStatus().then(renderWorkerStatus);
setInterval(() => window.vimCoachReview.getWorkerStatus().then(renderWorkerStatus), 500);
