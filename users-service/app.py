"""
Users Service - Smart Meeting Room Management System
Handles user management, authentication, and authorization.
Author: Maroun El Hajj
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import datetime
import os
import re

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

db = SQLAlchemy(app)


# Models
class User(db.Model):
    """
    User model for storing user information.
    
    Attributes:
        id (int): Primary key
        name (str): Full name of the user
        username (str): Unique username
        password (str): Hashed password
        email (str): User email address
        role (str): User role (admin, regular_user, facility_manager, moderator, auditor, service_account)
        created_at (datetime): Account creation timestamp
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False, default='regular_user')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def to_dict(self):
        """Convert user object to dictionary (excluding password)."""
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }


# Helper Functions
def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username):
    """Validate username format (alphanumeric and underscore only)."""
    pattern = r'^[a-zA-Z0-9_]{3,50}$'
    return re.match(pattern, username) is not None


def sanitize_input(text):
    """Sanitize input to prevent SQL injection."""
    if text is None:
        return None
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/']
    sanitized = str(text)
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    return sanitized.strip()


def token_required(f):
    """Decorator to require valid JWT token for protected routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(current_user, *args, **kwargs)
    return decorated


# Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'users'}), 200


@app.route('/api/users/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Request Body:
        name (str): Full name
        username (str): Unique username
        password (str): Password (min 6 characters)
        email (str): Email address
        role (str): User role (optional, defaults to 'regular_user')
    
    Returns:
        JSON: User details and success message
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'username', 'password', 'email']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Sanitize inputs
        name = sanitize_input(data['name'])
        username = sanitize_input(data['username'])
        email = sanitize_input(data['email'])
        password = data['password']
        role = sanitize_input(data.get('role', 'regular_user'))
        
        # Validate email format
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate username format
        if not validate_username(username):
            return jsonify({'error': 'Username must be 3-50 alphanumeric characters or underscores'}), 400
        
        # Validate password strength
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Validate role
        valid_roles = ['admin', 'regular_user', 'facility_manager', 'moderator', 'auditor', 'service_account']
        if role not in valid_roles:
            return jsonify({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}), 400
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 409
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 409
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            name=name,
            username=username,
            password=hashed_password,
            email=email,
            role=role
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'message': 'User registered successfully',
            'user': new_user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500


@app.route('/api/users/login', methods=['POST'])
def login():
    """
    User login endpoint.
    
    Request Body:
        username (str): Username
        password (str): Password
    
    Returns:
        JSON: JWT token and user details
    """
    try:
        data = request.get_json()
        
        username = sanitize_input(data.get('username'))
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password, password):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500


@app.route('/api/users', methods=['GET'])
@token_required
def get_all_users(current_user):
    """
    Get all users (Admin or Auditor only).
    
    Returns:
        JSON: List of all users
    """
    if current_user.role not in ['admin', 'auditor']:
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        users = User.query.all()
        return jsonify({
            'users': [user.to_dict() for user in users],
            'count': len(users)
        }), 200
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve users: {str(e)}'}), 500


@app.route('/api/users/<username>', methods=['GET'])
@token_required
def get_user(current_user, username):
    """
    Get specific user by username.
    
    Args:
        username (str): Username to retrieve
    
    Returns:
        JSON: User details
    """
    username = sanitize_input(username)
    
    # Users can view their own profile, admins and auditors can view any profile
    if current_user.username != username and current_user.role not in ['admin', 'auditor']:
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve user: {str(e)}'}), 500


@app.route('/api/users/<username>', methods=['PUT'])
@token_required
def update_user(current_user, username):
    """
    Update user details.
    
    Args:
        username (str): Username to update
    
    Request Body:
        name (str): New name (optional)
        email (str): New email (optional)
        password (str): New password (optional)
    
    Returns:
        JSON: Updated user details
    """
    username = sanitize_input(username)
    
    # Users can update their own profile, admins can update any profile
    if current_user.username != username and current_user.role != 'admin':
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update name
        if 'name' in data:
            user.name = sanitize_input(data['name'])
        
        # Update email
        if 'email' in data:
            email = sanitize_input(data['email'])
            if not validate_email(email):
                return jsonify({'error': 'Invalid email format'}), 400
            
            # Check if email already exists for another user
            existing_user = User.query.filter_by(email=email).first()
            if existing_user and existing_user.id != user.id:
                return jsonify({'error': 'Email already in use'}), 409
            
            user.email = email
        
        # Update password
        if 'password' in data:
            if len(data['password']) < 6:
                return jsonify({'error': 'Password must be at least 6 characters'}), 400
            user.password = generate_password_hash(data['password'])
        
        # Update role (admin only)
        if 'role' in data:
            if current_user.role != 'admin':
                return jsonify({'error': 'Only admins can change roles'}), 403
            
            role = sanitize_input(data['role'])
            valid_roles = ['admin', 'regular_user', 'facility_manager', 'moderator', 'auditor', 'service_account']
            if role not in valid_roles:
                return jsonify({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}), 400
            user.role = role
        
        db.session.commit()
        
        return jsonify({
            'message': 'User updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Update failed: {str(e)}'}), 500


@app.route('/api/users/<username>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, username):
    """
    Delete a user account (Admin only).
    
    Args:
        username (str): Username to delete
    
    Returns:
        JSON: Success message
    """
    username = sanitize_input(username)
    
    try:
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent deleting yourself
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': f'User {username} deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Delete failed: {str(e)}'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)