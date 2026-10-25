const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("vimCoachReview", {
  getHistory: () => ipcRenderer.invoke("history:read"),
  getWorkerStatus: () => ipcRenderer.invoke("worker:status"),
  onHistoryChanged: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("history:changed", listener);
    return () => ipcRenderer.removeListener("history:changed", listener);
  },
  setStatus: (lessonId, status) => ipcRenderer.invoke("history:status", lessonId, status),
  reset: () => ipcRenderer.invoke("history:reset"),
});
