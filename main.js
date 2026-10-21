const { app, BrowserWindow, globalShortcut, ipcMain, Tray, Menu, clipboard, screen, nativeImage } = require('electron');
const { spawn, execFile, execFileSync } = require('child_process');
const path = require('path');

// Windows is the main platform. macOS and Linux are experimental: pasting uses osascript (macOS,
// needs the Accessibility permission) or xdotool (Linux/X11); without xdotool the text is only copied.
const IS_WINDOWS = process.platform === 'win32';
const IS_MAC = process.platform === 'darwin';
const HAS_XDOTOOL = !IS_WINDOWS && !IS_MAC && commandExists('xdotool');
const PYTHON = IS_WINDOWS ? 'python' : 'python3';

// Hotkeys come from .env (HOTKEY_DICTATE / HOTKEY_READ_ALOUD, set by the setup wizard).
// Read aloud defaults to the dictation hotkey plus Alt: hardly any app uses it, on any OS.
const env = readEnvFile(path.join(__dirname, '.env'));
const HOTKEYS = {
  dictate: env.HOTKEY_DICTATE || 'Ctrl+Shift+Space',
  readAloud: env.HOTKEY_READ_ALOUD || 'Ctrl+Alt+Shift+Space'
};

function readEnvFile(file) {
  const values = {};
  try {
    for (const line of require('fs').readFileSync(file, 'utf8').split(/\r?\n/)) {
      const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
      if (match) values[match[1]] = match[2].replace(/^["']|["']$/g, '');
    }
  } catch { /* no .env yet */ }
  return values;
}

function commandExists(command) {
  try {
    execFileSync('which', [command], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

let bubbleWindow;
let tray;
let flaskProcess;
let targetWindowHandle = null;

let captureInFlight = false;

const PS_GET_HWND = `
Add-Type 'using System; using System.Runtime.InteropServices; public class WinAPI { [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow(); }'
[WinAPI]::GetForegroundWindow().ToInt64()
`.trim();

// Remember the window the user was typing in, so we can paste back into it.
// macOS doesn't need this: the bubble is a non-activating panel, so that app never loses focus.
function captureTargetWindow() {
  if (IS_MAC || (!IS_WINDOWS && !HAS_XDOTOOL)) return Promise.resolve(null);
  if (captureInFlight) return Promise.resolve(targetWindowHandle);
  captureInFlight = true;
  const [command, args] = IS_WINDOWS
    ? ['powershell', ['-NoProfile', '-Command', PS_GET_HWND]]
    : ['xdotool', ['getactivewindow']];
  return new Promise((resolve) => {
    execFile(command, args, { windowsHide: true }, (err, stdout) => {
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
    execFile('powershell', ['-NoProfile', '-Command', psScript], { windowsHide: true }, (err, stdout, stderr) => {
      if (err) console.error(`Send keys ${keys} failed:`, err.message, stderr);
      resolve(!err);
    });
  });
}

function runCommand(command, args) {
  return new Promise((resolve) => {
    execFile(command, args, { windowsHide: true }, (err, stdout, stderr) => {
      if (err) console.error(`${command} failed:`, err.message, stderr);
      resolve(!err);
    });
  });
}

// Send Ctrl+<key> (Cmd+<key> on macOS) to the window the user was working in.
// Returns false when this system can't send keystrokes.
async function sendShortcutToTarget(key) {
  if (IS_MAC) {
    return runCommand('osascript', ['-e', `tell application "System Events" to keystroke "${key}" using command down`]);
  }
  if (!targetWindowHandle) return false;
  if (IS_WINDOWS) {
    return key === 'v' ? focusTargetAndSendKeys('^v', 100, 200) : focusTargetAndSendKeys('^c', 50, 100);
  }
  if (HAS_XDOTOOL) {
    return runCommand('xdotool', ['windowactivate', '--sync', targetWindowHandle, 'key', '--clearmodifiers', `ctrl+${key}`]);
  }
  return false;
}

async function pasteToTargetWindow() {
  const pasted = await sendShortcutToTarget('v');
  console.log(pasted ? 'Paste done' : 'Could not paste; text is on the clipboard');
  return pasted;
}

function startFlask() {
  flaskProcess = spawn(PYTHON, ['app.py'], {
    cwd: __dirname,
    windowsHide: true, // no console window when started from a desktop shortcut
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
    // macOS: a non-activating panel, so clicking the bubble doesn't steal focus from the app you're typing in
    ...(IS_MAC ? { type: 'panel' } : {}),
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
  bubbleWindow.on('blur', () => {
    bubbleWindow.setMaximizable(false);
    bubbleWindow.webContents.send('window-blur'); // closes the settings panel on outside clicks
  });
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
  // Windows tray icons come from the multi-size .ico; other platforms use the PNG scaled down
  const icon = IS_WINDOWS
    ? path.join(__dirname, 'static', 'icon.ico')
    : nativeImage.createFromPath(path.join(__dirname, 'static', 'icon.png')).resize({ width: IS_MAC ? 18 : 22 });
  tray = new Tray(icon);
  tray.setToolTip('Voice Bubble');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show Bubble', click: () => bubbleWindow?.show() },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() }
  ]));
}

// A second launch (e.g. double-clicking the shortcut again) just quits; the bubble is already running
if (!app.requestSingleInstanceLock()) {
  app.quit();
}
app.on('second-instance', () => bubbleWindow?.show());

// globalShortcut.register returns false when another app already owns the combination
const failedHotkeys = [];
function registerHotkey(accelerator, handler) {
  let registered = false;
  try {
    registered = globalShortcut.register(accelerator, handler);
  } catch (e) {
    console.error(`Invalid hotkey "${accelerator}":`, e.message); // e.g. a typo in .env
  }
  if (!registered) {
    console.error(`Hotkey ${accelerator} could not be registered (used by another app, or invalid)`);
    failedHotkeys.push(accelerator);
  }
}

app.whenReady().then(() => {
  if (IS_MAC) app.dock?.hide(); // live in the menu bar only, like skipTaskbar on Windows
  startFlask();
  createBubbleWindow();

  // Try to create tray (won't crash if icon missing)
  try { createTray(); } catch (e) { console.log('Tray icon not found, skipping tray'); }

  // Global hotkey to toggle recording (Ctrl+Shift+Space by default)
  registerHotkey(HOTKEYS.dictate, async () => {
    await captureTargetWindow();
    bubbleWindow.webContents.send('toggle-recording');
  });

  // Global hotkey to read the selection aloud, or the clipboard if nothing is selected
  // (Ctrl+Alt+Shift+Space by default). Pressing it while speaking stops.
  registerHotkey(HOTKEYS.readAloud, async () => {
    // Copy the selection from the target window (Ctrl+C / Cmd+C), then put the user's clipboard back
    const before = clipboard.readText();
    const copied = await sendShortcutToTarget('c');
    if (copied) await new Promise(r => setTimeout(r, 150)); // give the app time to update the clipboard
    const text = clipboard.readText();
    if (copied && before && text !== before) clipboard.writeText(before);
    bubbleWindow.webContents.send('speak-clipboard', text || '');
  });

  // IPC: the configured hotkeys, and any another app already owns, for the bubble's UI
  ipcMain.handle('get-hotkeys', () => ({ ...HOTKEYS, failed: failedHotkeys }));

  // IPC: read clipboard text (for renderer button clicks)
  ipcMain.handle('get-clipboard-text', () => clipboard.readText());

  // IPC: transcription done, paste it. Resolves false if the text could only be copied.
  ipcMain.handle('transcription-complete', (event, text) => {
    clipboard.writeText(text);
    return pasteToTargetWindow();
  });

  // IPC: copy only (no paste)
  ipcMain.on('copy-to-clipboard', (event, text) => {
    clipboard.writeText(text);
  });

  // IPC: resize bubble, keeping the bubble itself in place. The window normally grows upward
  // (anchored at the bottom); if that would go off the top of the screen it grows downward instead.
  // Returns the anchor so the renderer can lay out the panel above or below the bubble.
  let resizeAnchor = 'bottom';
  ipcMain.handle('resize-bubble', (event, { width, height }) => {
    if (!bubbleWindow) return resizeAnchor;
    const bounds = bubbleWindow.getBounds();
    const growing = height > bounds.height;
    if (growing) {
      const workArea = screen.getDisplayMatching(bounds).workArea;
      resizeAnchor = bounds.y + bounds.height - height >= workArea.y ? 'bottom' : 'top';
    }
    bubbleWindow.setBounds({
      x: bounds.x + bounds.width - width,
      y: resizeAnchor === 'bottom' ? bounds.y + bounds.height - height : bounds.y,
      width,
      height
    });
    return resizeAnchor;
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
