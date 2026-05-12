"""
Validation utilities
"""
import re


def validate_username(username):
    """Validate username: 3-20 chars, alphanumeric and underscore"""
    if not username:
        return False, "用户名不能为空"
    if len(username) < 3 or len(username) > 20:
        return False, "用户名长度需在3-20个字符之间"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "用户名只能包含字母、数字和下划线"
    return True, None


def validate_password(password):
    """Validate password: at least 6 chars"""
    if not password:
        return False, "密码不能为空"
    if len(password) < 6:
        return False, "密码长度至少为6个字符"
    return True, None


def validate_email(email):
    """Validate email format"""
    if not email:
        return False, "邮箱不能为空"
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "邮箱格式不正确"
    return True, None


def validate_phone(phone):
    """Validate phone number: Chinese mobile format"""
    if not phone:
        return False, "手机号不能为空"
    pattern = r'^1[3-9]\d{9}$'
    if not re.match(pattern, phone):
        return False, "手机号格式不正确"
    return True, None
