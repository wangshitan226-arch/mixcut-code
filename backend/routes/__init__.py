"""Routes package"""
from flask import Blueprint

# Create blueprints for each module
projects_bp = Blueprint('projects', __name__, url_prefix='/api')
shots_bp = Blueprint('shots', __name__, url_prefix='/api')
materials_bp = Blueprint('materials', __name__, url_prefix='/api')
upload_bp = Blueprint('upload', __name__, url_prefix='/api')
render_bp = Blueprint('render', __name__, url_prefix='/api')
download_bp = Blueprint('download', __name__, url_prefix='/api')

# Import routes (to be implemented)
# from . import projects, shots, materials, upload, render, download
