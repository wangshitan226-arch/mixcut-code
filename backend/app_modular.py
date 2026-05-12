#!/usr/bin/env python3
"""
MixCut Backend - Modular Architecture
=====================================
This is the modular version of the backend.

Project Structure:
├── app.py                  # Original monolithic version (kept for reference)
├── app_modular.py          # This file - modular entry point
├── config.py               # Configuration settings
├── extensions.py           # Flask extensions (db, task management)
├── models.py               # Database models
├── utils/                  # Utility functions
│   ├── __init__.py
│   ├── validators.py       # Input validation
│   ├── video.py            # Video processing
│   └── helpers.py          # Helper functions
├── services/               # Business logic layer
│   ├── __init__.py
│   ├── user_service.py
│   ├── shot_service.py
│   ├── material_service.py
│   └── render_service.py
└── routes/                 # API routes (blueprints)
    ├── __init__.py
    ├── auth.py             # Authentication
    ├── users.py            # User management
    ├── shots.py            # Shot management
    ├── materials.py        # Material management
    ├── upload.py           # File upload
    ├── generate.py         # Video generation
    ├── renders.py          # Render results
    └── static.py           # Static files

Usage:
    python app_modular.py

To switch from original app.py:
    1. Backup: mv app.py app_original.py
    2. Switch: mv app_modular.py app.py
    3. Run: python app.py
"""

import threading
import time
import os

from flask import Flask
from flask_cors import CORS

from config import (
    SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS,
    RENDERS_FOLDER,
    ensure_directories
)
from extensions import db

# Import models to ensure they are registered with SQLAlchemy
from models import User, Shot, Material, Render

# Import blueprints
from routes import (
    auth_bp,
    users_bp,
    shots_bp,
    materials_bp,
    upload_bp,
    generate_bp,
    renders_bp,
    static_bp
)


def cleanup_old_renders(max_age_hours=24):
    """Clean up old render files"""
    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        cleaned_count = 0
        for filename in os.listdir(RENDERS_FOLDER):
            filepath = os.path.join(RENDERS_FOLDER, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        cleaned_count += 1
                    except:
                        pass
        
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} old render files")
    except Exception as e:
        print(f"Cleanup error: {e}")


def start_cleanup_scheduler():
    """Start background cleanup scheduler"""
    def cleanup_loop():
        while True:
            time.sleep(3600)  # Run every hour
            cleanup_old_renders(max_age_hours=24)
    
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    CORS(app)
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    
    # Initialize extensions
    db.init_app(app)
    
    # Ensure directories exist
    ensure_directories()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(shots_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(generate_bp)
    app.register_blueprint(renders_bp)
    app.register_blueprint(static_bp)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app


if __name__ == '__main__':
    app = create_app()
    start_cleanup_scheduler()
    app.run(host='0.0.0.0', port=3002, debug=True)
