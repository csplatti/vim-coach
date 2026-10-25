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
const debugLogFile = process.env.VIM_COACH_DEBUG_LOG_FILE || path.join(
  os.homedir(), ".local", "state", "vim-coach", "debug.jsonl"
);
let debugLogOffset = 0;
let debugLogRemainder = "";
let historyWatcher = null;
let historyChangeTimer = null;

function printDebugEvents() {
  try {
    const size = fs.statSync(debugLogFile).size;
    if (size < debugLogOffset) debugLogOffset = 0;
    if (size === debugLogOffset) return;
    const descriptor = fs.openSync(debugLogFile, "r");
    const buffer = Buffer.alloc(size - debugLogOffset);
    fs.readSync(descriptor, buffer, 0, buffer.length, debugLogOffset);
    fs.closeSync(descriptor);
    debugLogOffset = size;
    const lines = (debugLogRemainder + buffer.toString("utf8")).split("\n");
    debugLogRemainder = lines.pop() || "";
    for (const line of lines.filter(Boolean)) {
      try {
        const event = JSON.parse(line);
        console.log(`\n[Vim Coach debug: ${event.kind}] ${event.timestamp || ""}`);
        console.dir(event.payload, { depth: null, colors: true });
      } catch (_) {
        console.log("[Vim Coach debug]", line);
      }
    }
  } catch (_) {
    // The file is created lazily by the first debug-enabled batch.
  }
}

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

function writeHistory(value) {
  fs.mkdirSync(path.dirname(historyFile), { recursive: true });
  const temporary = `${historyFile}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`);
  fs.renameSync(temporary, historyFile);
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

function notifyHistoryChanged() {
  for (const window of BrowserWindow.getAllWindows()) {
    window.webContents.send("history:changed");
  }
}

function watchHistory() {
  const directory = path.dirname(historyFile);
  const filename = path.basename(historyFile);
  fs.mkdirSync(directory, { recursive: true });
  historyWatcher = fs.watch(directory, (_, changedName) => {
    if (changedName && changedName.toString() !== filename) return;
    clearTimeout(historyChangeTimer);
    historyChangeTimer = setTimeout(notifyHistoryChanged, 50);
  });
  historyWatcher.on("error", (error) => {
    console.error("[Vim Coach] History watcher failed:", error.message);
  });
}

function createWindow() {
  const window = new BrowserWindow({
    width: 760,
    height: 640,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });
  window.loadFile(path.join(__dirname, "index.html"));
}

ipcMain.handle("history:read", () => readHistory());
ipcMain.handle("worker:status", () => readWorkerStatus());
ipcMain.handle("history:status", (_, lessonId, status) => updateStatus(lessonId, status));
ipcMain.handle("history:reset", () => resetStatuses());

app.whenReady().then(() => {
  try {
    debugLogOffset = fs.statSync(debugLogFile).size;
  } catch (_) {
    debugLogOffset = 0;
  }
  console.log(`[Vim Coach] Watching debug events at ${debugLogFile}`);
  setInterval(printDebugEvents, 250);
  watchHistory();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (historyWatcher) historyWatcher.close();
  clearTimeout(historyChangeTimer);
});
