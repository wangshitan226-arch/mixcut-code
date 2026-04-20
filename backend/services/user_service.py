"""
User service - Business logic for user management
"""
from models import User
from extensions import db


class UserService:
    """User related business logic"""
    
    @staticmethod
    def create_anonymous_user():
        """Create a new anonymous user"""
        user = User(type='anonymous')
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID"""
        return User.query.get(user_id)
    
    @staticmethod
    def get_user_by_username(username):
        """Get user by username"""
        return User.query.filter_by(username=username).first()
    
    @staticmethod
    def get_user_by_email(email):
        """Get user by email"""
        return User.query.filter_by(email=email).first()
    
    @staticmethod
    def get_user_by_phone(phone):
        """Get user by phone"""
        return User.query.filter_by(phone=phone).first()
