"""
Static file serving routes
"""
from flask import Blueprint, send_from_directory
from config import UPLOAD_FOLDER, THUMBNAIL_FOLDER, RENDERS_FOLDER

static_bp = Blueprint('static', __name__)


@static_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@static_bp.route('/uploads/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_FOLDER, filename)


@static_bp.route('/renders/<path:filename>')
def serve_render(filename):
    return send_from_directory(RENDERS_FOLDER, filename)
