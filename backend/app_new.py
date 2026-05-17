#!/usr/bin/env python3
"""
MixCut Backend - Modular Architecture
=====================================
This is the new modular entry point. The original app.py is kept for reference.

Project Structure:
├── app_new.py          # This file - main entry point
├── config.py           # Configuration settings
├── extensions.py       # Flask extensions (db, etc.)
├── models.py           # Database models
├── utils/              # Utility functions
│   ├── __init__.py
│   ├── validators.py   # Input validation
│   ├── video.py        # Video processing
│   └── helpers.py      # General helper functions
├── services/           # Business logic layer
│   ├── __init__.py
│   ├── user_service.py
│   ├── shot_service.py
│   ├── material_service.py
│   ├── render_service.py
│   └── channels_service.py  # 视频号运营服务
└── routes/             # API routes (blueprints)
    ├── __init__.py
    ├── auth.py         # Authentication
    ├── users.py        # User management
    ├── shots.py        # Shot management
    ├── materials.py    # Material management
    ├── upload.py       # File upload
    ├── generate.py     # Video generation
    ├── renders.py      # Render results
    ├── static.py       # Static files
    └── channels.py     # 视频号运营

Usage:
    python app_new.py

To use this new structure:
1. Move app.py to app_old.py (backup)
2. Rename this file to app.py
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
from websocket import socketio, init_websocket

# Import models to ensure they are registered with SQLAlchemy
from models import User, Shot, Material, Render, KaipaiEdit, DigitalHuman, VoiceClone

# Import blueprints
from routes import (
    auth_bp,
    users_bp,
    shots_bp,
    materials_bp,
    upload_bp,
    generate_bp,
    renders_bp,
    static_bp,
    kaipai_bp,
    oss_upload_bp,
    channels_bp,
    ai_bp,
    digital_human_bp
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
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    
    # Initialize extensions
    db.init_app(app)
    init_websocket(app)  # Initialize WebSocket
    
    # Ensure directories exist
    ensure_directories()
    
    # Register blueprints
    # 注意：kaipai_bp 有 /users/<user_id>/kaipai/drafts 路由
    # 必须在 users_bp (/users/<user_id>) 之前注册，否则会被截获
    app.register_blueprint(auth_bp)
    app.register_blueprint(kaipai_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(shots_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(generate_bp)
    app.register_blueprint(renders_bp)
    app.register_blueprint(static_bp)
    app.register_blueprint(oss_upload_bp)
    app.register_blueprint(channels_bp)  # 视频号运营路由
    app.register_blueprint(ai_bp)  # AI文案路由
    app.register_blueprint(digital_human_bp)  # 数字人和声音克隆路由
    
    @app.errorhandler(Exception)
    def handle_all_exceptions(e):
        print(f"[Global Exception] {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        from flask import jsonify
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500
    
    # Debug: 打印所有路由
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        if 'kaipai' in rule.endpoint or 'channels' in rule.endpoint:
            print(f"  {rule.rule} -> {rule.endpoint}")
    
    # Create tables
    with app.app_context():
        db.create_all()
        
        # 迁移：为 channels_video_monitors 添加自动回复字段
        try:
            with db.engine.connect() as conn:
                result = conn.execute(db.text("PRAGMA table_info(channels_video_monitors)"))
                columns = [row[1] for row in result]
                
                if 'auto_reply_enabled' not in columns:
                    conn.execute(db.text("ALTER TABLE channels_video_monitors ADD COLUMN auto_reply_enabled BOOLEAN DEFAULT 0"))
                    conn.commit()
                    print("[Migration] 添加 auto_reply_enabled 字段")
                
                if 'auto_reply_text' not in columns:
                    conn.execute(db.text("ALTER TABLE channels_video_monitors ADD COLUMN auto_reply_text TEXT"))
                    conn.commit()
                    print("[Migration] 添加 auto_reply_text 字段")
                
                if 'auto_reply_only_high_intent' not in columns:
                    conn.execute(db.text("ALTER TABLE channels_video_monitors ADD COLUMN auto_reply_only_high_intent BOOLEAN DEFAULT 1"))
                    conn.commit()
                    print("[Migration] 添加 auto_reply_only_high_intent 字段")
        except Exception as e:
            print(f"[Migration] 迁移失败（可能字段已存在）: {e}")
    
    return app


if __name__ == '__main__':
    app = create_app()
    start_cleanup_scheduler()
    # Use socketio.run instead of app.run for WebSocket support
    # debug=False 避免 watchdog 检测到 Playwright 文件变化时自动重启
    socketio.run(app, host='0.0.0.0', port=3002, debug=False, allow_unsafe_werkzeug=True)
