"""Database models"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), default='未命名项目')
    quality = db.Column(db.String(20), default='medium')
    created_at = db.Column(db.DateTime, default=db.func.now())
    shots = db.relationship('Shot', backref='project', lazy=True, cascade='all, delete-orphan')
    renders = db.relationship('Render', backref='project', lazy=True, cascade='all, delete-orphan')

class Shot(db.Model):
    __tablename__ = 'shots'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    name = db.Column(db.String(255), default='未命名镜头')
    sequence = db.Column(db.Integer, default=0)
    materials = db.relationship('Material', backref='shot', lazy=True, cascade='all, delete-orphan')

class Material(db.Model):
    __tablename__ = 'materials'
    id = db.Column(db.String(36), primary_key=True)
    shot_id = db.Column(db.Integer, db.ForeignKey('shots.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    original_name = db.Column(db.String(255))
    file_path = db.Column(db.String(500), nullable=False)
    unified_path = db.Column(db.String(500))
    thumbnail_path = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=db.func.now())

class Render(db.Model):
    __tablename__ = 'renders'
    id = db.Column(db.String(100), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    combo_index = db.Column(db.Integer, nullable=False)
    material_ids = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(50))
    duration = db.Column(db.String(10))
    duration_seconds = db.Column(db.Float)
    thumbnail = db.Column(db.String(500))
    file_path = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=db.func.now())

def init_db(app):
    """Initialize database"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
