#!/usr/bin/env python3
"""
MixCut Backend - Modular Implementation
Refactored version with clean architecture
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import configuration
from config import (
    SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS,
    MAX_CONTENT_LENGTH,
    UPLOAD_FOLDER,
    THUMBNAIL_FOLDER,
    UNIFIED_FOLDER,
    RENDERS_FOLDER,
    CORS_ORIGINS
)

# Import models
from models import db, Project, Shot, Material, Render

# Import utilities
from utils.file_utils import allowed_file, ensure_folders, clear_project_renders, cleanup_old_renders
from utils.video_utils import (
    transcode_to_unified,
    generate_image_thumbnail,
    generate_video_thumbnail,
    get_video_duration,
    format_duration,
    get_quality_settings
)

# Create Flask app
def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    
    # Initialize extensions
    CORS(app, origins=CORS_ORIGINS)
    db.init_app(app)
    
    # Ensure folders exist
    ensure_folders()
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app

# Create app instance
app = create_app()

# Task management
render_tasks = {}
transcode_tasks = {}

# Import and register routes
from routes import (
    projects_bp,
    shots_bp,
    materials_bp,
    upload_bp,
    render_bp,
    download_bp
)

# Register blueprints
app.register_blueprint(projects_bp)
app.register_blueprint(shots_bp)
app.register_blueprint(materials_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(render_bp)
app.register_blueprint(download_bp)

# Static file serving
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/uploads/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_FOLDER, filename)

@app.route('/uploads/unified/<path:filename>')
def serve_unified(filename):
    return send_from_directory(UNIFIED_FOLDER, filename)

@app.route('/renders/<path:filename>')
def serve_render(filename):
    return send_from_directory(RENDERS_FOLDER, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002, debug=True)
