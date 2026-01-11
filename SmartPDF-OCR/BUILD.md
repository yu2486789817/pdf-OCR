# SmartPDF-OCR Electron Desktop Application

## Build Instructions

This document describes how to build the SmartPDF-OCR desktop application.

### Prerequisites

1. **Node.js 18+** and npm
2. **Python 3.10+** with pip
3. **CUDA Toolkit** (if using GPU acceleration)
4. **PyInstaller** (`pip install pyinstaller`)

### Step 1: Build Python Backend

```bash
cd SmartPDF-OCR

# Install dependencies
pip install -r requirements.txt

# Build executable
pyinstaller ocr_engine.spec

# The output will be in dist/ocr-engine.exe (Windows)
```

### Step 2: Build Frontend

```bash
cd frontend

# Install dependencies
npm install

# Build static site
npm run build

# The output will be in out/ directory
```

### Step 3: Package Electron App

```bash
cd frontend

# Copy Python backend to expected location
# Windows:
mkdir -p ../dist/ocr-engine
copy ..\dist\ocr-engine.exe ..\dist\ocr-engine\

# Build Electron installer
npm run dist

# The installer will be in dist-electron/ directory
```

### Development Mode

To run the application in development mode:

1. Start the Python backend:
   ```bash
   python run_server.py --port 8000
   ```

2. Start the Next.js dev server:
   ```bash
   cd frontend
   npm run dev
   ```

3. Start Electron in dev mode:
   ```bash
   cd frontend
   npm run electron:dev
   ```

### Directory Structure

```
SmartPDF-OCR/
├── app/                    # Python backend
├── frontend/
│   ├── app/                # Next.js pages
│   ├── electron/
│   │   ├── main.js         # Electron main process
│   │   └── preload.js      # Electron preload script
│   ├── out/                # Built static site
│   └── dist-electron/      # Final installers
├── dist/
│   └── ocr-engine.exe      # Built Python backend
├── run_server.py           # Python entry point
└── ocr_engine.spec         # PyInstaller config
```

### Notes

- The Python backend is started as a child process by Electron
- API communication happens via localhost on a dynamically assigned port
- User data (uploads, outputs) is stored in `%LOCALAPPDATA%\SmartPDF-OCR` on Windows
- GPU acceleration (TensorRT) requires CUDA runtime on the target machine
