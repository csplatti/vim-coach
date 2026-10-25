const { app, BrowserWindow, ipcMain } = require("electron");
const fs = require("fs");
const os = require("os");
const path = require("path");

const historyFile = process.env.VIM_COACH_HISTORY_FILE || path.join(
  os.homedir(), ".local", "state", "vim-coach", "lessons.json"
);
const statusFile = process.env.VIM_COACH_STATUS_FILE || path.join(
  os.homedir(), ".local", "state", "vim-coach", "status.json"
);
const goalsFile = process.env.VIM_COACH_GOALS_FILE || path.join(
  os.homedir(), ".local", "state", "vim-coach", "goals.json"
);
const fileWatchers = [];
const fileChangeTimers = new Map();

function readHistory() {
  try {
    const value = JSON.parse(fs.readFileSync(historyFile, "utf8"));
    if (value && value.schemaVersion === 1 && Array.isArray(value.lessons)) {
      return value;
    }
  } catch (_) {
    // An empty inbox is the normal first-run state.
  }
  return { schemaVersion: 1, lessons: [] };
}

function readWorkerStatus() {
  try {
    return JSON.parse(fs.readFileSync(statusFile, "utf8"));
  } catch (_) {
    return { state: "idle" };
  }
}

function readGoals() {
  try {
    const value = JSON.parse(fs.readFileSync(goalsFile, "utf8"));
    if (value && value.schemaVersion === 1 && Array.isArray(value.goals)) {
      return value;
    }
  } catch (_) {
    // Goals are created lazily when Neovim sees the first lesson.
  }
  return { schemaVersion: 1, goals: [] };
}

function writeHistory(value) {
  fs.mkdirSync(path.dirname(historyFile), { recursive: true });
  const temporary = `${historyFile}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`);
  fs.renameSync(temporary, historyFile);
}

function writeGoals(value) {
  fs.mkdirSync(path.dirname(goalsFile), { recursive: true });
  const temporary = `${goalsFile}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`);
  fs.renameSync(temporary, goalsFile);
}

function updateGoalStatus(featureId, status) {
  if (!["active", "paused"].includes(status)) return false;
  const value = readGoals();
  const goal = value.goals.find((item) => item.featureId === featureId);
  if (!goal || goal.status === "completed") return false;
  goal.status = status;
  writeGoals(value);
  return true;
}

function updateStatus(lessonId, status) {
  if (!["new", "dismissed", "known"].includes(status)) return false;
  const history = readHistory();
  const lesson = history.lessons.find((item) => item.lessonId === lessonId);
  if (!lesson) return false;
  lesson.status = status;
  lesson.updatedAt = new Date().toISOString();
  writeHistory(history);
  return true;
}

function resetStatuses() {
  const history = readHistory();
  history.lessons.forEach((lesson) => { lesson.status = "new"; });
  writeHistory(history);
  return history;
}

function notifyChanged(channel) {
  for (const window of BrowserWindow.getAllWindows()) {
    window.webContents.send(channel);
  }
}

function watchFile(file, channel) {
  const directory = path.dirname(file);
  const filename = path.basename(file);
  fs.mkdirSync(directory, { recursive: true });
  const watcher = fs.watch(directory, (_, changedName) => {
    if (changedName && changedName.toString() !== filename) return;
    clearTimeout(fileChangeTimers.get(channel));
    fileChangeTimers.set(channel, setTimeout(() => notifyChanged(channel), 50));
  });
  watcher.on("error", (error) => {
    console.error(`[Vim Coach] Watcher failed for ${filename}:`, error.message);
  });
  fileWatchers.push(watcher);
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1040,
    height: 760,
    minWidth: 760,
    minHeight: 620,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });
  window.loadFile(path.join(__dirname, "index.html"));
}

ipcMain.handle("history:read", () => readHistory());
ipcMain.handle("goals:read", () => readGoals());
ipcMain.handle("worker:status", () => readWorkerStatus());
ipcMain.handle("history:status", (_, lessonId, status) => updateStatus(lessonId, status));
ipcMain.handle("history:reset", () => resetStatuses());
ipcMain.handle("goals:status", (_, featureId, status) => updateGoalStatus(featureId, status));

app.whenReady().then(() => {
  watchFile(historyFile, "history:changed");
  watchFile(goalsFile, "goals:changed");
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  fileWatchers.forEach((watcher) => watcher.close());
  fileChangeTimers.forEach((timer) => clearTimeout(timer));
});
