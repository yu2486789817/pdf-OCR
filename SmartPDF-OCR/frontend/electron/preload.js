/**
 * Electron Preload Script
 * Exposes safe APIs to the renderer process.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Parse query parameters to get API port
const urlParams = new URLSearchParams(window.location.search);
const apiPort = urlParams.get('apiPort') || '8000';

contextBridge.exposeInMainWorld('electronAPI', {
  apiPort: apiPort,
  platform: process.platform,
  // Add more APIs as needed
  onBackendReady: (callback) => ipcRenderer.on('backend-ready', callback),
});
