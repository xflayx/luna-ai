const { app, BrowserWindow, ipcMain, screen } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const crypto = require("crypto");

let pyProc = null;
let backendPort = null;
let authToken = null;
let win = null;
let isMiniMode = false;
let backendReady = false;
let rendererReady = false;
let configSent = false;

const FULL_WIDTH = 430;
const FULL_HEIGHT = 760;
const MINI_SIZE = 80;

app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");

function pickPort() {
  return 18000 + Math.floor(Math.random() * 2000);
}

function startBackend() {
  backendPort = pickPort();
  authToken = crypto.randomBytes(32).toString("hex");
  backendReady = false;

  const env = {
    ...process.env,
    BACKEND_HOST: "127.0.0.1",
    BACKEND_PORT: String(backendPort),
    BACKEND_TOKEN: authToken,
    PYTHONUNBUFFERED: "1",
  };

  const scriptPath = path.join(__dirname, "..", "backend", "server.py");
  pyProc = spawn("python", ["-u", scriptPath], {
    env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  pyProc.stdout.on("data", (d) => {
    const text = d.toString();
    console.log("[py]", text.trim());
    if (text.includes("READY")) {
      backendReady = true;
      sendBackendConfig();
    }
  });

  pyProc.stderr.on("data", (d) => {
    console.error("[py-err]", d.toString().trim());
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: FULL_WIDTH,
    height: FULL_HEIGHT,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  win.webContents.on("will-navigate", (e) => e.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("console-message", (_event, level, message) => {
    const prefix = level >= 2 ? "[renderer-err]" : "[renderer]";
    console.log(prefix, message);
  });
  win.webContents.on("did-start-loading", () => {
    rendererReady = false;
    configSent = false;
  });

  win.loadFile(path.join(__dirname, "renderer", "index.html"));
  win.webContents.once("did-finish-load", () => {
    rendererReady = true;
    sendBackendConfig();
  });
}

function sendBackendConfig() {
  if (!win || !backendPort || !authToken) return;
  if (!backendReady || !rendererReady) return;
  if (configSent) return;
  win.webContents.send("backend-config", {
    url: `ws://127.0.0.1:${backendPort}/ws`,
    token: authToken,
  });
  configSent = true;
}

app.whenReady().then(() => {
  startBackend();
  createWindow();
});

app.on("before-quit", () => {
  if (pyProc) {
    pyProc.kill();
  }
});

ipcMain.on("window:minimize", () => {
  if (!win) return;
  isMiniMode = true;
  const bounds = win.getBounds();
  win._restoreBounds = bounds;
  win.setMinimumSize(MINI_SIZE, MINI_SIZE);
  win.setSize(MINI_SIZE, MINI_SIZE);
  const display = screen.getPrimaryDisplay();
  const x = display.workArea.x + display.workArea.width - MINI_SIZE - 20;
  const y = display.workArea.y + display.workArea.height - MINI_SIZE - 20;
  win.setPosition(x, y);
  win.webContents.send("window:miniMode", true);
});

ipcMain.on("window:restore", () => {
  if (!win) return;
  isMiniMode = false;
  win.setMinimumSize(200, 300);
  win.setSize(FULL_WIDTH, FULL_HEIGHT);
  if (win._restoreBounds) {
    win.setBounds(win._restoreBounds);
  } else {
    win.center();
  }
  win.webContents.send("window:miniMode", false);
});

ipcMain.on("window:close", () => {
  if (win) win.close();
});
