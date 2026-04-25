"""
Database models for MixCut
"""
import uuid
from extensions import db


class User(db.Model):
    """User model supporting both anonymous and registered users"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = db.Column(db.String(20), default='anonymous', nullable=False)
    
    # Registration fields (nullable for anonymous users)
    username = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    
    # Profile fields
    nickname = db.Column(db.String(50), nullable=True)
    avatar = db.Column(db.String(500), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    last_login_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    shots = db.relationship('Shot', backref='user', lazy=True, cascade='all, delete-orphan')
    materials = db.relationship('Material', backref='user', lazy=True, cascade='all, delete-orphan')
    renders = db.relationship('Render', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'type': self.type,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'nickname': self.nickname,
            'avatar': self.avatar,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }
        return data


class Shot(db.Model):
    """Shot (scene) model"""
    __tablename__ = 'shots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    
    # Relationships
    materials = db.relationship('Material', backref='shot', lazy=True, cascade='all, delete-orphan')


class Material(db.Model):
    """Material (video/image) model"""
    __tablename__ = 'materials'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    shot_id = db.Column(db.Integer, db.ForeignKey('shots.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'video' or 'image'
    original_name = db.Column(db.String(255))
    file_path = db.Column(db.String(500), nullable=False)
    unified_path = db.Column(db.String(500))
    thumbnail_path = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.String(10))
    duration_seconds = db.Column(db.Float, default=0)  # 数值类型，用于快速计算
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    # 客户端渲染相关字段
    is_local = db.Column(db.Boolean, default=False)  # 是否客户端本地渲染（视频文件在浏览器本地）
    local_material_id = db.Column(db.String(36), nullable=True)  # 客户端本地素材ID（用于关联本地存储）
    width = db.Column(db.Integer, nullable=True)  # 视频宽度
    height = db.Column(db.Integer, nullable=True)  # 视频高度
    file_size = db.Column(db.BigInteger, nullable=True)  # 文件大小（字节）


class Render(db.Model):
    """Render result model"""
    __tablename__ = 'renders'
    
    id = db.Column(db.String(100), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    combo_index = db.Column(db.Integer, nullable=False)
    material_ids = db.Column(db.Text, nullable=False)  # JSON array
    tag = db.Column(db.String(50))
    duration = db.Column(db.String(10))
    duration_seconds = db.Column(db.Float)
    thumbnail = db.Column(db.String(500))
    file_path = db.Column(db.String(500))  # 本地文件路径（用于预览）
    oss_url = db.Column(db.String(500))    # OSS URL（用于下载/文字快剪）
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=db.func.now())


class Template(db.Model):
    """Video Template model - 视频模板（仅系统预设）"""
    __tablename__ = 'templates'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)  # ecommerce, knowledge, emotion, product, entertainment
    
    # 模板配置（JSON格式）
    config = db.Column(db.Text, nullable=False)  # JSON: {subtitleStyles, videoEffects, backgroundMusic}
    
    # 预览图
    preview_url = db.Column(db.String(500))
    
    # 状态
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)  # 排序
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    def to_dict(self):
        import json
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'config': json.loads(self.config) if self.config else None,
            'preview_url': self.preview_url,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class KaipaiEdit(db.Model):
    """Kaipai editing task model - 开拍式剪辑任务/草稿"""
    __tablename__ = 'kaipai_edits'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    render_id = db.Column(db.String(100), db.ForeignKey('renders.id'), nullable=False)
    parent_id = db.Column(db.String(36), db.ForeignKey('kaipai_edits.id'), nullable=True)
    version = db.Column(db.Integer, default=1, nullable=False)
    
    # 视频信息
    original_video_url = db.Column(db.String(500), nullable=False)
    output_video_url = db.Column(db.String(500), nullable=True)
    
    # 语音识别结果（JSON格式保存完整结果）
    asr_result = db.Column(db.Text, nullable=True)  # JSON: {sentences, videoInfo}
    
    # 视频片段信息（用于预览剪辑效果）
    segment_urls = db.Column(db.Text, nullable=True)  # JSON: [{id, url, beginTime, endTime}]
    segment_status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    
    # 编辑参数（JSON格式）
    edit_params = db.Column(db.Text, nullable=True)  # JSON: {removed_segments, subtitle_style, bgm, template}
    
    # 剪辑历史记录（用于撤回功能）
    edit_history = db.Column(db.Text, nullable=True)  # JSON array of edit actions
    
    # 状态: draft, transcribing, processing, completed, failed
    status = db.Column(db.String(20), default='draft')
    
    # 草稿标题
    title = db.Column(db.String(200), nullable=True)
    
    # 选择的模板（可选）
    template_id = db.Column(db.String(36), db.ForeignKey('templates.id'), nullable=True)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    # 关联
    render = db.relationship('Render', backref='kaipai_edits', lazy=True)
    user = db.relationship('User', backref='kaipai_edits', lazy=True)
    template = db.relationship('Template', backref='kaipai_edits', lazy=True)
    
    def to_dict(self):
        import json
        return {
            'id': self.id,
            'user_id': self.user_id,
            'render_id': self.render_id,
            'parent_id': self.parent_id,
            'version': self.version,
            'title': self.title,
            'original_video_url': self.original_video_url,
            'output_video_url': self.output_video_url,
            'asr_result': json.loads(self.asr_result) if self.asr_result else None,
            'segment_urls': json.loads(self.segment_urls) if self.segment_urls else [],
            'segment_status': self.segment_status,
            'edit_params': json.loads(self.edit_params) if self.edit_params else None,
            'edit_history': json.loads(self.edit_history) if self.edit_history else [],
            'status': self.status,
            'template_id': self.template_id,
            'template': self.template.to_dict() if self.template else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
