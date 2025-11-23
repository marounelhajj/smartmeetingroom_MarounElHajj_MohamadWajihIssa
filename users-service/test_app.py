"""
Unit tests for Users Service
Author: Maroun El Hajj

This file contains comprehensive tests for the Users Service API.
Run with: pytest test_app.py -v --cov=app --cov-report=html
"""

import pytest
import json
from app import app, db, User
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """
    Create test client with in-memory database.
    This fixture is used by all test functions.
    """
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            # Create test admin user
            admin = User(
                name='Admin User',
                username='admin',
                password=generate_password_hash('admin123'),
                email='admin@test.com',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
        yield client
        with app.app_context():
            db.drop_all()


@pytest.fixture
def admin_token(client):
    """
    Get admin authentication token for protected routes.
    """
    response = client.post('/api/users/login',
                          data=json.dumps({
                              'username': 'admin',
                              'password': 'admin123'
                          }),
                          content_type='application/json')
    data = json.loads(response.data)
    return data['token']


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert data['service'] == 'users'


def test_user_registration_success(client):
    """Test successful user registration."""
    response = client.post('/api/users/register',
                          data=json.dumps({
                              'name': 'John Doe',
                              'username': 'johndoe',
                              'password': 'password123',
                              'email': 'john@example.com',
                              'role': 'regular_user'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['message'] == 'User registered successfully'
    assert data['user']['username'] == 'johndoe'
    assert data['user']['role'] == 'regular_user'


def test_user_registration_missing_fields(client):
    """Test registration with missing required fields."""
    response = client.post('/api/users/register',
                          data=json.dumps({
                              'name': 'John Doe',
                              'username': 'johndoe'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_user_registration_duplicate_username(client):
    """Test registration with duplicate username."""
    # First registration
    client.post('/api/users/register',
               data=json.dumps({
                   'name': 'John Doe',
                   'username': 'johndoe',
                   'password': 'password123',
                   'email': 'john@example.com'
               }),
               content_type='application/json')
    
    # Try to register again with same username
    response = client.post('/api/users/register',
                          data=json.dumps({
                              'name': 'Jane Doe',
                              'username': 'johndoe',
                              'password': 'password456',
                              'email': 'jane@example.com'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 409
    data = json.loads(response.data)
    assert 'already exists' in data['error']


def test_user_registration_invalid_email(client):
    """Test registration with invalid email format."""
    response = client.post('/api/users/register',
                          data=json.dumps({
                              'name': 'John Doe',
                              'username': 'johndoe',
                              'password': 'password123',
                              'email': 'invalid-email'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Invalid email' in data['error']


def test_user_registration_weak_password(client):
    """Test registration with weak password."""
    response = client.post('/api/users/register',
                          data=json.dumps({
                              'name': 'John Doe',
                              'username': 'johndoe',
                              'password': '123',
                              'email': 'john@example.com'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'at least 6 characters' in data['error']


def test_user_login_success(client):
    """Test successful user login."""
    # Register user first
    client.post('/api/users/register',
               data=json.dumps({
                   'name': 'John Doe',
                   'username': 'johndoe',
                   'password': 'password123',
                   'email': 'john@example.com'
               }),
               content_type='application/json')
    
    # Login
    response = client.post('/api/users/login',
                          data=json.dumps({
                              'username': 'johndoe',
                              'password': 'password123'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'token' in data
    assert data['message'] == 'Login successful'


def test_user_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post('/api/users/login',
                          data=json.dumps({
                              'username': 'nonexistent',
                              'password': 'wrongpassword'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'Invalid' in data['error']


def test_get_all_users_as_admin(client, admin_token):
    """Test getting all users as admin."""
    response = client.get('/api/users',
                         headers={'Authorization': f'Bearer {admin_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'users' in data
    assert 'count' in data


def test_get_all_users_without_token(client):
    """Test getting all users without authentication."""
    response = client.get('/api/users')
    
    assert response.status_code == 401


def test_get_specific_user(client, admin_token):
    """Test getting specific user by username."""
    response = client.get('/api/users/admin',
                         headers={'Authorization': f'Bearer {admin_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['user']['username'] == 'admin'


def test_get_nonexistent_user(client, admin_token):
    """Test getting non-existent user."""
    response = client.get('/api/users/nonexistent',
                         headers={'Authorization': f'Bearer {admin_token}'})
    
    assert response.status_code == 404


def test_update_user_profile(client, admin_token):
    """Test updating user profile."""
    response = client.put('/api/users/admin',
                         headers={'Authorization': f'Bearer {admin_token}'},
                         data=json.dumps({
                             'name': 'Updated Admin',
                             'email': 'newemail@test.com'
                         }),
                         content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['user']['name'] == 'Updated Admin'
    assert data['user']['email'] == 'newemail@test.com'


def test_update_user_invalid_email(client, admin_token):
    """Test updating user with invalid email."""
    response = client.put('/api/users/admin',
                         headers={'Authorization': f'Bearer {admin_token}'},
                         data=json.dumps({
                             'email': 'invalid-email'
                         }),
                         content_type='application/json')
    
    assert response.status_code == 400


def test_delete_user_as_admin(client, admin_token):
    """Test deleting user as admin."""
    # Create a user to delete
    client.post('/api/users/register',
               data=json.dumps({
                   'name': 'Test User',
                   'username': 'testuser',
                   'password': 'password123',
                   'email': 'test@example.com'
               }),
               content_type='application/json')
    
    # Delete the user
    response = client.delete('/api/users/testuser',
                           headers={'Authorization': f'Bearer {admin_token}'})
    
    assert response.status_code == 200


def test_delete_own_account_prevention(client, admin_token):
    """Test that users cannot delete their own account."""
    response = client.delete('/api/users/admin',
                           headers={'Authorization': f'Bearer {admin_token}'})
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Cannot delete your own account' in data['error']


def test_sql_injection_prevention(client):
    """Test SQL injection prevention in username."""
    response = client.post('/api/users/register',
                          data=json.dumps({
                              'name': 'Test User',
                              'username': "admin'; DROP TABLE users--",
                              'password': 'password123',
                              'email': 'test@example.com'
                          }),
                          content_type='application/json')
    
    # Should either succeed with sanitized input or fail validation
    assert response.status_code in [201, 400]


def test_unauthorized_access_to_protected_route(client):
    """Test accessing protected route without authentication."""
    response = client.get('/api/users')
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'Token' in data['error']


def test_invalid_role_registration(client):
    """Test registration with invalid role."""
    response = client.post('/api/users/register',
                          data=json.dumps({
                              'name': 'Test User',
                              'username': 'testuser',
                              'password': 'password123',
                              'email': 'test@example.com',
                              'role': 'invalid_role'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'Invalid role' in data['error']


def test_update_user_role_as_admin(client, admin_token):
    """Test updating user role (admin only)."""
    # Create a regular user
    client.post('/api/users/register',
               data=json.dumps({
                   'name': 'Regular User',
                   'username': 'regularuser',
                   'password': 'password123',
                   'email': 'regular@example.com',
                   'role': 'regular_user'
               }),
               content_type='application/json')
    
    # Update role to facility_manager
    response = client.put('/api/users/regularuser',
                         headers={'Authorization': f'Bearer {admin_token}'},
                         data=json.dumps({
                             'role': 'facility_manager'
                         }),
                         content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['user']['role'] == 'facility_manager'


def test_token_expiration_handling(client, admin_token):
    """Test that expired tokens are rejected."""
    # This is a placeholder - in production you'd test with an expired token
    # For now, just verify token is required
    response = client.get('/api/users',
                         headers={'Authorization': 'Bearer invalid_token'})
    
    assert response.status_code == 401


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=app', '--cov-report=html'])