const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("studioAPI", {
  getBackendUrl: () => ipcRenderer.invoke("studio:get-backend-url"),
  getPlatform: () => ipcRenderer.invoke("studio:get-platform"),
});
