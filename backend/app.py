#!/usr/bin/env python3
"""
MixCut Backend - Entry Point
=============================
This file delegates to the modular architecture in app_new.py.
The original monolithic code has been moved to app_old.py for reference.

Usage:
    python app.py
"""

from app_new import create_app, start_cleanup_scheduler

app = create_app()

if __name__ == '__main__':
    start_cleanup_scheduler()
    from websocket import socketio
    socketio.run(app, host='0.0.0.0', port=3002, debug=False, allow_unsafe_werkzeug=True)
