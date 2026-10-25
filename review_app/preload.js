const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("vimCoachReview", {
  getHistory: () => ipcRenderer.invoke("history:read"),
  getGoals: () => ipcRenderer.invoke("goals:read"),
  getWorkerStatus: () => ipcRenderer.invoke("worker:status"),
  onHistoryChanged: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("history:changed", listener);
    return () => ipcRenderer.removeListener("history:changed", listener);
  },
  onGoalsChanged: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("goals:changed", listener);
    return () => ipcRenderer.removeListener("goals:changed", listener);
  },
  setStatus: (lessonId, status) => ipcRenderer.invoke("history:status", lessonId, status),
  setGoalStatus: (featureId, status) => ipcRenderer.invoke("goals:status", featureId, status),
  reset: () => ipcRenderer.invoke("history:reset"),
});
