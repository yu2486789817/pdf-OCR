"""
SmartPDF-OCR Backend Server Entry Point
Supports both development and packaged (PyInstaller) environments.
"""

import sys
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="SmartPDF-OCR Backend Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload (dev only)")
    args = parser.parse_args()
    
    print(f"Starting SmartPDF-OCR Server on http://{args.host}:{args.port}...")
    
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
