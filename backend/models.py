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
    
    # 双轨视频字段
    server_video_url = db.Column(db.String(500))  # 视频①：服务器高质量拼接视频URL（用于ASR/导出）
    server_video_status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    client_video_url = db.Column(db.String(500))  # 视频②：客户端拼接视频URL（Blob URL，仅前端使用）


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


# ==================== 视频号运营功能模型 ====================

class ChannelsAccount(db.Model):
    """视频号账号模型"""
    __tablename__ = 'channels_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # 账号信息
    nickname = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(500), nullable=True)
    
    # Cookie 文件路径（相对于项目目录）
    cookie_path = db.Column(db.String(500), nullable=False)
    
    # 状态: normal(正常), expired(登录过期), invalid(失效)
    status = db.Column(db.String(20), default='normal')
    
    # 最近登录时间
    last_login_at = db.Column(db.DateTime, nullable=True)
    
    # 创建/更新时间
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    # 关联
    user = db.relationship('User', backref='channels_accounts', lazy=True)
    publish_records = db.relationship('ChannelsPublishRecord', backref='account', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'nickname': self.nickname,
            'avatar': self.avatar,
            'status': self.status,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ChannelsPublishRecord(db.Model):
    """视频号发布记录"""
    __tablename__ = 'channels_publish_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('channels_accounts.id'), nullable=False)
    render_id = db.Column(db.String(100), db.ForeignKey('renders.id'), nullable=True)
    
    # 发布内容
    title = db.Column(db.String(200), nullable=False)
    tags = db.Column(db.String(500), nullable=True)  # 话题标签，空格分隔
    description = db.Column(db.Text, nullable=True)
    cover_url = db.Column(db.String(500), nullable=True)  # 封面图片路径
    video_path = db.Column(db.String(500), nullable=False)  # 发布的视频文件路径
    
    # 平台信息
    platform_link = db.Column(db.String(500), nullable=True)  # 视频号链接
    platform_video_id = db.Column(db.String(100), nullable=True)  # 平台视频ID
    
    # 状态: pending(等待中), uploading(上传中), publishing(发布中), success(成功), failed(失败)
    status = db.Column(db.String(20), default='pending')
    error_msg = db.Column(db.Text, nullable=True)
    
    # 创建时间
    created_at = db.Column(db.DateTime, default=db.func.now())
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # 关联
    user = db.relationship('User', backref='channels_publish_records', lazy=True)
    render = db.relationship('Render', backref='channels_publish_records', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'render_id': self.render_id,
            'title': self.title,
            'tags': self.tags,
            'description': self.description,
            'cover_url': self.cover_url,
            'video_path': self.video_path,
            'platform_link': self.platform_link,
            'platform_video_id': self.platform_video_id,
            'status': self.status,
            'error_msg': self.error_msg,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class ChannelsVideoMonitor(db.Model):
    """视频号视频监控任务"""
    __tablename__ = 'channels_video_monitors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('channels_accounts.id'), nullable=False)
    publish_record_id = db.Column(db.Integer, db.ForeignKey('channels_publish_records.id'), nullable=False)
    
    # 平台视频ID
    platform_video_id = db.Column(db.String(100), nullable=False)
    
    # 监控状态: monitoring(监控中), stopped(已停止), expired(已过期)
    status = db.Column(db.String(20), default='monitoring')
    
    # 最后抓取时间
    last_fetch_at = db.Column(db.DateTime, nullable=True)
    
    # 评论统计
    total_comments = db.Column(db.Integer, default=0)
    new_comments = db.Column(db.Integer, default=0)
    unreplied_comments = db.Column(db.Integer, default=0)
    high_intent_comments = db.Column(db.Integer, default=0)
    
    # 自动回复配置
    auto_reply_enabled = db.Column(db.Boolean, default=False)
    auto_reply_text = db.Column(db.Text, nullable=True)
    auto_reply_only_high_intent = db.Column(db.Boolean, default=True)
    
    # 创建时间
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    
    # 关联
    user = db.relationship('User', backref='channels_video_monitors', lazy=True)
    account = db.relationship('ChannelsAccount', backref='video_monitors', lazy=True)
    publish_record = db.relationship('ChannelsPublishRecord', backref='video_monitor', lazy=True)
    comments = db.relationship('ChannelsComment', backref='video_monitor', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'publish_record_id': self.publish_record_id,
            'platform_video_id': self.platform_video_id,
            'status': self.status,
            'last_fetch_at': self.last_fetch_at.isoformat() if self.last_fetch_at else None,
            'total_comments': self.total_comments,
            'new_comments': self.new_comments,
            'unreplied_comments': self.unreplied_comments,
            'high_intent_comments': self.high_intent_comments,
            'auto_reply_enabled': self.auto_reply_enabled,
            'auto_reply_text': self.auto_reply_text,
            'auto_reply_only_high_intent': self.auto_reply_only_high_intent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ChannelsComment(db.Model):
    """视频号评论"""
    __tablename__ = 'channels_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey('channels_video_monitors.id'), nullable=False)
    
    # 评论者信息
    commenter_name = db.Column(db.String(100), nullable=False)
    commenter_avatar = db.Column(db.String(500), nullable=True)
    
    # 评论内容
    content = db.Column(db.Text, nullable=False)
    
    # 平台评论ID（用于回复）
    platform_comment_id = db.Column(db.String(100), nullable=True)
    
    # 高意向标记
    is_high_intent = db.Column(db.Boolean, default=False)
    intent_keywords = db.Column(db.String(200), nullable=True)
    
    # 回复状态: pending(待回复), replied(已回复), ignored(已忽略)
    reply_status = db.Column(db.String(20), default='pending')
    reply_content = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)
    
    # 是否为新评论
    is_new = db.Column(db.Boolean, default=True)
    
    # 评论时间（平台时间）
    commented_at = db.Column(db.DateTime, nullable=True)
    
    # 创建时间（本地记录时间）
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'monitor_id': self.monitor_id,
            'commenter_name': self.commenter_name,
            'commenter_avatar': self.commenter_avatar,
            'content': self.content,
            'platform_comment_id': self.platform_comment_id,
            'is_high_intent': self.is_high_intent,
            'intent_keywords': self.intent_keywords,
            'reply_status': self.reply_status,
            'reply_content': self.reply_content,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
            'is_new': self.is_new,
            'commented_at': self.commented_at.isoformat() if self.commented_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DigitalHuman(db.Model):
    __tablename__ = 'digital_humans'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)

    title = db.Column(db.String(100), nullable=False)
    avatar_id = db.Column(db.String(200), nullable=True)
    video_url = db.Column(db.String(500), nullable=True)
    cover_url = db.Column(db.String(500), nullable=True)
    voice_id = db.Column(db.String(200), nullable=True)
    voice_name = db.Column(db.String(100), nullable=True)

    status = db.Column(db.String(20), default='draft')

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    user = db.relationship('User', backref='digital_humans', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'avatar_id': self.avatar_id,
            'video_url': self.video_url,
            'cover_url': self.cover_url,
            'voice_id': self.voice_id,
            'voice_name': self.voice_name,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class VoiceClone(db.Model):
    __tablename__ = 'voice_clones'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)

    title = db.Column(db.String(100), nullable=False)
    audio_url = db.Column(db.String(500), nullable=True)
    clone_voice_id = db.Column(db.String(200), nullable=True)
    clone_task_id = db.Column(db.String(200), nullable=True)
    model_type = db.Column(db.String(50), default='cosyvoice-clone-v1')
    ref_text = db.Column(db.String(500), nullable=True)
    preview_url = db.Column(db.String(500), nullable=True)

    status = db.Column(db.String(20), default='draft')

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    user = db.relationship('User', backref='voice_clones', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'audio_url': self.audio_url,
            'clone_voice_id': self.clone_voice_id,
            'clone_task_id': self.clone_task_id,
            'model_type': self.model_type,
            'ref_text': self.ref_text,
            'preview_url': self.preview_url,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
