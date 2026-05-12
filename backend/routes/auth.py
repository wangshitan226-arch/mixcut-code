"""
Authentication routes
"""
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from extensions import db
from models import User
from utils import validate_username, validate_password, validate_email, validate_phone

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json or {}
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        password = data.get('password', '')
        nickname = data.get('nickname', '').strip()
        
        if not username and not email and not phone:
            return jsonify({'error': '请提供用户名、邮箱或手机号'}), 400
        
        # Validate inputs
        if username:
            valid, error = validate_username(username)
            if not valid:
                return jsonify({'error': error}), 400
            if User.query.filter_by(username=username).first():
                return jsonify({'error': '用户名已被注册'}), 400
        
        if email:
            valid, error = validate_email(email)
            if not valid:
                return jsonify({'error': error}), 400
            if User.query.filter_by(email=email).first():
                return jsonify({'error': '邮箱已被注册'}), 400
        
        if phone:
            valid, error = validate_phone(phone)
            if not valid:
                return jsonify({'error': error}), 400
            if User.query.filter_by(phone=phone).first():
                return jsonify({'error': '手机号已被注册'}), 400
        
        valid, error = validate_password(password)
        if not valid:
            return jsonify({'error': error}), 400
        
        # Create user
        user = User(
            type='registered',
            username=username or None,
            email=email or None,
            phone=phone or None,
            password_hash=generate_password_hash(password),
            nickname=nickname or username or '用户',
            is_active=True
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': '注册成功',
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.json or {}
        account = data.get('account', '').strip()
        password = data.get('password', '')
        
        if not account:
            return jsonify({'error': '请输入用户名、邮箱或手机号'}), 400
        if not password:
            return jsonify({'error': '请输入密码'}), 400
        
        # Find user
        user = None
        if '@' in account:
            user = User.query.filter_by(email=account).first()
        elif account.isdigit():
            user = User.query.filter_by(phone=account).first()
        
        if not user:
            user = User.query.filter_by(username=account).first()
        
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        if user.type != 'registered':
            return jsonify({'error': '该账户不支持密码登录'}), 400
        
        if not user.is_active:
            return jsonify({'error': '账户已被禁用'}), 403
        
        if not user.password_hash or not check_password_hash(user.password_hash, password):
            return jsonify({'error': '密码错误'}), 401
        
        # Update last login
        user.last_login_at = datetime.now()
        db.session.commit()
        
        return jsonify({
            'message': '登录成功',
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    return jsonify({'message': '退出登录成功'})


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get user profile"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': '缺少用户ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        return jsonify({'user': user.to_dict()})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update user profile"""
    try:
        data = request.json or {}
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': '缺少用户ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        if 'nickname' in data:
            nickname = data['nickname'].strip()
            if nickname:
                user.nickname = nickname[:50]
        
        if 'avatar' in data:
            user.avatar = data['avatar']
        
        db.session.commit()
        
        return jsonify({
            'message': '资料更新成功',
            'user': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """Change user password"""
    try:
        data = request.json or {}
        user_id = data.get('user_id')
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not user_id:
            return jsonify({'error': '缺少用户ID'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        if user.type != 'registered':
            return jsonify({'error': '该账户不支持修改密码'}), 400
        
        if not user.password_hash or not check_password_hash(user.password_hash, old_password):
            return jsonify({'error': '原密码错误'}), 401
        
        valid, error = validate_password(new_password)
        if not valid:
            return jsonify({'error': error}), 400
        
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({'message': '密码修改成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
