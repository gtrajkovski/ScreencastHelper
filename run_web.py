#!/usr/bin/env python3
"""Run ScreenCast Studio web application."""

import webbrowser
import threading
import time

from src.web.app import app

def open_browser():
    """Open browser after short delay."""
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  ScreenCast Studio - Web Application")
    print("="*50)
    print("\n  Starting server at http://127.0.0.1:5000")
    print("  Press Ctrl+C to stop\n")

    # Open browser automatically
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Flask app
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
