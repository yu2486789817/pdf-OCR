/**
 * Electron Main Process
 * Manages the application window and Python backend lifecycle.
 */

const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');

let mainWindow = null;
let pythonProcess = null;
let apiPort = 8000;

// Determine if we are in development or production
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

/**
 * Find an available port
 */
function findFreePort(startPort = 8000) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(startPort, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', () => {
      resolve(findFreePort(startPort + 1));
    });
  });
}

/**
 * Start Python backend server
 */
/**
 * Get path to Python backend executable
 */
function getBackendPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'bin', 'ocr-engine.exe');
  }
  // In development, fallback to local dist or python script
  // Check if dist exe exists first
  const distExe = path.join(__dirname, '..', '..', 'dist', 'ocr-engine.exe');
  const fs = require('fs');
  if (fs.existsSync(distExe)) {
    return distExe;
  }
  return 'python'; // Fallback to system python
}

/**
 * Start Python backend server
 */
async function startPythonBackend() {
  apiPort = await findFreePort(8000);
  console.log(`Starting Python backend on port ${apiPort}...`);

  const pythonPath = getBackendPath();
  const isExe = pythonPath.endsWith('.exe');

  const args = (!isExe)
    ? [path.join(__dirname, '..', '..', 'run_server.py'), '--port', apiPort.toString()]
    : ['--port', apiPort.toString()];

  console.log(`Spawning backend: ${pythonPath} with args: ${args.join(' ')}`);

  pythonProcess = spawn(pythonPath, args, {
    cwd: app.isPackaged ? process.resourcesPath : path.join(__dirname, '..', '..'),
    stdio: 'inherit', // Let output flow to main console
    windowsHide: true, // Hide console window on Windows
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
    pythonProcess = null;
  });

  // Wait for server to be ready
  await waitForServer(apiPort, 30000);
  console.log('Python backend is ready.');
}

/**
 * Wait for server to respond
 */
function waitForServer(port, timeout) {
  const startTime = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const socket = new net.Socket();
      socket.setTimeout(1000);
      socket.on('connect', () => {
        socket.destroy();
        resolve();
      });
      socket.on('error', () => {
        socket.destroy();
        if (Date.now() - startTime > timeout) {
          reject(new Error('Backend startup timeout'));
        } else {
          setTimeout(check, 500);
        }
      });
      socket.on('timeout', () => {
        socket.destroy();
        setTimeout(check, 500);
      });
      socket.connect(port, '127.0.0.1');
    };
    check();
  });
}

/**
 * Create the main application window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'SmartPDF-OCR',
    icon: path.join(__dirname, '..', 'public', 'icon.png'),
  });

  // Load the frontend
  if (isDev) {
    // Development: load from Next.js dev server
    mainWindow.loadURL(`http://localhost:3000?apiPort=${apiPort}`);
    mainWindow.webContents.openDevTools();
  } else {
    // Production: load from static export
    const indexPath = path.join(__dirname, '..', 'out', 'index.html');
    mainWindow.loadFile(indexPath, {
      query: { apiPort: apiPort.toString() }
    });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Remove default menu in production
  if (!isDev) {
    Menu.setApplicationMenu(null);
  }
}

/**
 * Application lifecycle
 */
app.whenReady().then(async () => {
  try {
    await startPythonBackend();
    createWindow();
  } catch (error) {
    console.error('Failed to start application:', error);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('will-quit', () => {
  // Kill Python backend
  if (pythonProcess) {
    console.log('Terminating Python backend...');
    pythonProcess.kill();
  }
});
