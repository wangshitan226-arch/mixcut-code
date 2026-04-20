"""
Flask extensions initialization
"""
from flask_sqlalchemy import SQLAlchemy

# Initialize extensions
db = SQLAlchemy()

# Task management (in-memory storage for now)
render_tasks = {}
transcode_tasks = {}
