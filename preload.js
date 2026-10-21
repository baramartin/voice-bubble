const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  toggleRecording: () => ipcRenderer.send('toggle-recording'),
  onToggleRecording: (callback) => ipcRenderer.on('toggle-recording', callback),
  transcriptionComplete: (text) => ipcRenderer.send('transcription-complete', text),
  copyToClipboard: (text) => ipcRenderer.send('copy-to-clipboard', text),
  resizeBubble: (width, height) => ipcRenderer.invoke('resize-bubble', { width, height }),
  onWindowBlur: (callback) => ipcRenderer.on('window-blur', callback),
  getClipboardText: () => ipcRenderer.invoke('get-clipboard-text'),
  onSpeakClipboard: (callback) => ipcRenderer.on('speak-clipboard', (_event, text) => callback(text))
});
