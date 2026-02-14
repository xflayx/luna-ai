const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("deskpet", {
  onBackendConfig: (cb) =>
    ipcRenderer.on("backend-config", (_event, data) => cb(data)),
  minimizeWindow: () => ipcRenderer.send("window:minimize"),
  restoreWindow: () => ipcRenderer.send("window:restore"),
  closeWindow: () => ipcRenderer.send("window:close"),
  onMiniMode: (cb) =>
    ipcRenderer.on("window:miniMode", (_event, isMini) => cb(isMini)),
});
