const { app, BrowserWindow, globalShortcut, ipcMain, Tray, Menu, clipboard, screen } = require('electron');
const { spawn, exec, execFile } = require('child_process');
const path = require('path');

let bubbleWindow;
let tray;
let flaskProcess;
let targetWindowHandle = null;

let captureInFlight = false;

const PS_GET_HWND = `
Add-Type 'using System; using System.Runtime.InteropServices; public class WinAPI { [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); }'
[WinAPI]::GetForegroundWindow().ToInt64()
`.trim();

function captureTargetWindow() {
  if (captureInFlight) return Promise.resolve(targetWindowHandle);
  captureInFlight = true;
  return new Promise((resolve) => {
    execFile('powershell', ['-NoProfile', '-Command', PS_GET_HWND], (err, stdout) => {
      captureInFlight = false;
      if (!err && stdout.trim()) {
        const handle = stdout.trim();
        const bubbleHandle = bubbleWindow?.getNativeWindowHandle();
        const bubbleInt = bubbleHandle ? bufferToInt64(bubbleHandle) : null;
        if (handle !== String(bubbleInt)) {
          targetWindowHandle = handle;
        }
      }
      resolve(targetWindowHandle);
    });
  });
}

function bufferToInt64(buf) {
  if (buf.length >= 8) return buf.readBigInt64LE(0).toString();
  if (buf.length >= 4) return buf.readInt32LE(0).toString();
  return '0';
}

// Focus the target window and send a key combo (e.g. "^v").
// Only restore the window if it's minimized: SW_RESTORE (9) on a maximized window un-maximizes it.
function focusTargetAndSendKeys(keys, restoreDelayMs, focusDelayMs) {
  const psScript = `
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinAPI {
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
}
"@
$hwnd = [IntPtr]${targetWindowHandle}
if ([WinAPI]::IsIconic($hwnd)) {
    [WinAPI]::ShowWindow($hwnd, 9)
    Start-Sleep -Milliseconds ${restoreDelayMs}
}
[WinAPI]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds ${focusDelayMs}
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("${keys}")
`.trim();

  return new Promise((resolve) => {
    execFile('powershell', ['-NoProfile', '-Command', psScript], (err, stdout, stderr) => {
      if (err) console.error(`Send keys ${keys} failed:`, err.message, stderr);
      resolve(!err);
    });
  });
}

async function pasteToTargetWindow() {
  if (!targetWindowHandle) {
    console.log('No target window handle, skipping paste');
    return;
  }
  console.log('Pasting to window handle:', targetWindowHandle);
  if (await focusTargetAndSendKeys('^v', 100, 200)) console.log('Paste done');
}

function startFlask() {
  flaskProcess = spawn('python', ['app.py'], {
    cwd: __dirname,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  flaskProcess.stdout.on('data', (d) => process.stdout.write(`[Flask] ${d}`));
  flaskProcess.stderr.on('data', (d) => process.stderr.write(`[Flask] ${d}`));
  flaskProcess.on('close', (code) => {
    console.log(`Flask exited with code ${code}`);
  });
}

function createBubbleWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  bubbleWindow = new BrowserWindow({
    width: 320,
    height: 72,
    x: width - 340,
    y: height - 100,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: false,
    thickFrame: false,
    title: '',
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  bubbleWindow.loadFile('bubble.html');
  bubbleWindow.setAlwaysOnTop(true, 'screen-saver');
  bubbleWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  // Workaround for Electron bug #46882: frameless transparent windows
  // show a phantom title bar on blur on Windows.
  bubbleWindow.on('blur', () => bubbleWindow.setMaximizable(false));
  bubbleWindow.on('focus', () => bubbleWindow.setMaximizable(false));

  // Track which external window last had focus.
  // Poll every 500ms so we always have a recent handle ready.
  setInterval(async () => {
    if (!bubbleWindow.isFocused()) {
      await captureTargetWindow();
    }
  }, 500);
}

function createTray() {
  // Use a simple icon - create one from the Electron default
  tray = new Tray(path.join(__dirname, 'static', 'icon.ico'));
  tray.setToolTip('Voice Bubble');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show Bubble', click: () => bubbleWindow?.show() },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() }
  ]));
}

app.whenReady().then(() => {
  startFlask();
  createBubbleWindow();

  // Try to create tray (won't crash if icon missing)
  try { createTray(); } catch (e) { console.log('Tray icon not found, skipping tray'); }

  // Global hotkey: Ctrl+Shift+Space to toggle recording
  globalShortcut.register('Ctrl+Shift+Space', async () => {
    await captureTargetWindow();
    bubbleWindow.webContents.send('toggle-recording');
  });

  // Global hotkey: Ctrl+Shift+S to speak selection/clipboard aloud (or stop if already speaking)
  globalShortcut.register('Ctrl+Shift+S', async () => {
    // First, copy selection from the target window (Ctrl+C)
    if (targetWindowHandle) {
      await focusTargetAndSendKeys('^c', 50, 100);
      // Small delay for clipboard to update
      await new Promise(r => setTimeout(r, 100));
    }
    const text = clipboard.readText();
    bubbleWindow.webContents.send('speak-clipboard', text || '');
  });

  // IPC: read clipboard text (for renderer button clicks)
  ipcMain.handle('get-clipboard-text', () => clipboard.readText());

  // IPC: transcription done, paste it
  ipcMain.on('transcription-complete', (event, text) => {
    clipboard.writeText(text);
    pasteToTargetWindow();
  });

  // IPC: copy only (no paste)
  ipcMain.on('copy-to-clipboard', (event, text) => {
    clipboard.writeText(text);
  });

  // IPC: resize bubble
  ipcMain.on('resize-bubble', (event, { width, height }) => {
    if (bubbleWindow) {
      const bounds = bubbleWindow.getBounds();
      bubbleWindow.setBounds({
        x: bounds.x + bounds.width - width,
        y: bounds.y + bounds.height - height,
        width,
        height
      });
    }
  });
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (flaskProcess) {
    flaskProcess.kill();
  }
});

app.on('window-all-closed', () => {
  app.quit();
});
