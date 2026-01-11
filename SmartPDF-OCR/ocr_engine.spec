# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for SmartPDF-OCR Backend
Run with: pyinstaller ocr_engine.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Project root
PROJECT_ROOT = Path('.').resolve()

a = Analysis(
    ['run_server.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Include app module
        ('app', 'app'),
    ],
    hiddenimports=[
        # FastAPI / Uvicorn
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'pydantic',
        'pydantic_settings',
        
        # PaddleOCR
        'paddleocr',
        'paddle',
        'paddle.fluid',
        
        # Image processing
        'cv2',
        'numpy',
        'PIL',
        
        # PDF
        'fitz',
        'pdfplumber',
        
        # Export
        'docx',
        'reportlab',
        
        # AI
        'google.genai',
        'httpx',
        
        # Others
        'aiofiles',
        'multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ocr-engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for debugging; set False for production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if available
)
