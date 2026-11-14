const { app, BrowserWindow, ipcMain, session } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

const ROOT_DIR = path.resolve(__dirname, "..", "..");
const BACKEND_URL = "http://127.0.0.1:8420";
let backendProc = null;
let mainWindow = null;

function startBackendIfNeeded() {
  const pythonBin = process.platform === "win32"
    ? path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    : path.join(ROOT_DIR, ".venv", "bin", "python");
  backendProc = spawn(
    pythonBin,
    ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8420"],
    { cwd: ROOT_DIR, stdio: "inherit" }
  );
  backendProc.on("error", (err) => console.error("Failed to start Studio Python backend:", err));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    backgroundColor: "#09090b",
    title: "Universal AI Video Production Studio",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  const isDev = !app.isPackaged && process.env.NODE_ENV !== "production";
  if (isDev && process.env.VITE_DEV_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_wc, permission, callback) => {
    callback(permission === "media");
  });
  ipcMain.handle("studio:get-backend-url", () => BACKEND_URL);
  ipcMain.handle("studio:get-platform", () => process.platform);
  startBackendIfNeeded();
  setTimeout(createWindow, 1200);
});

app.on("window-all-closed", () => {
  if (backendProc) {
    backendProc.kill("SIGTERM");
    backendProc = null;
  }
  if (process.platform !== "darwin") app.quit();
});
