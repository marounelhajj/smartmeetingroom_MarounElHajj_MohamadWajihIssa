"""
Unit tests for Rooms Service
Author: mwidotcom
"""

import pytest
import json
import jwt
import datetime
from app import app, db, Room


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            # Create test rooms
            room1 = Room(
                name='Conference Room A',
                capacity=10,
                equipment='Projector,Whiteboard,TV',
                location='Building 1, Floor 2',
                status='available'
            )
            room2 = Room(
                name='Meeting Room B',
                capacity=6,
                equipment='Whiteboard,Video Conference',
                location='Building 1, Floor 3',
                status='available'
            )
            db.session.add_all([room1, room2])
            db.session.commit()
        yield client
        with app.app_context():
            db.drop_all()


@pytest.fixture
def admin_token():
    """Generate admin token for testing."""
    secret_key = app.config['SECRET_KEY']
    token = jwt.encode({
        'user_id': 1,
        'username': 'admin',
        'role': 'admin',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, secret_key, algorithm='HS256')
    return token


@pytest.fixture
def facility_token():
    """Generate facility manager token for testing."""
    secret_key = app.config['SECRET_KEY']
    token = jwt.encode({
        'user_id': 2,
        'username': 'facility_manager',
        'role': 'facility_manager',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, secret_key, algorithm='HS256')
    return token


@pytest.fixture
def user_token():
    """Generate regular user token for testing."""
    secret_key = app.config['SECRET_KEY']
    token = jwt.encode({
        'user_id': 3,
        'username': 'regular_user',
        'role': 'regular_user',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, secret_key, algorithm='HS256')
    return token


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert data['service'] == 'rooms'


def test_add_room_as_admin(client, admin_token):
    """Test adding a new room as admin."""
    response = client.post('/api/rooms',
                          headers={'Authorization': f'Bearer {admin_token}'},
                          data=json.dumps({
                              'name': 'Executive Suite',
                              'capacity': 20,
                              'equipment': ['Projector', 'Conference Phone', 'Whiteboard'],
                              'location': 'Building 2, Floor 5',
                              'status': 'available'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['message'] == 'Room added successfully'
    assert data['room']['name'] == 'Executive Suite'
    assert data['room']['capacity'] == 20


def test_add_room_as_facility_manager(client, facility_token):
    """Test adding a new room as facility manager."""
    response = client.post('/api/rooms',
                          headers={'Authorization': f'Bearer {facility_token}'},
                          data=json.dumps({
                              'name': 'Training Room',
                              'capacity': 30,
                              'equipment': ['Projector', 'Sound System'],
                              'location': 'Building 3, Floor 1'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 201


def test_add_room_as_regular_user_denied(client, user_token):
    """Test that regular users cannot add rooms."""
    response = client.post('/api/rooms',
                          headers={'Authorization': f'Bearer {user_token}'},
                          data=json.dumps({
                              'name': 'Unauthorized Room',
                              'capacity': 10,
                              'equipment': ['Whiteboard'],
                              'location': 'Building 1'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 403


def test_add_room_missing_fields(client, admin_token):
    """Test adding room with missing required fields."""
    response = client.post('/api/rooms',
                          headers={'Authorization': f'Bearer {admin_token}'},
                          data=json.dumps({
                              'name': 'Incomplete Room',
                              'capacity': 10
                          }),
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_add_room_duplicate_name(client, admin_token):
    """Test adding room with duplicate name."""
    response = client.post('/api/rooms',
                          headers={'Authorization': f'Bearer {admin_token}'},
                          data=json.dumps({
                              'name': 'Conference Room A',
                              'capacity': 15,
                              'equipment': ['Projector'],
                              'location': 'Building 1'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 409
    data = json.loads(response.data)
    assert 'already exists' in data['error']


def test_add_room_invalid_capacity(client, admin_token):
    """Test adding room with invalid capacity."""
    response = client.post('/api/rooms',
                          headers={'Authorization': f'Bearer {admin_token}'},
                          data=json.dumps({
                              'name': 'Invalid Capacity Room',
                              'capacity': -5,
                              'equipment': [],
                              'location': 'Building 1'
                          }),
                          content_type='application/json')
    
    assert response.status_code == 400


def test_get_all_rooms(client, user_token):
    """Test getting all rooms."""
    response = client.get('/api/rooms',
                         headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'rooms' in data
    assert 'count' in data
    assert data['count'] >= 2


def test_get_rooms_with_capacity_filter(client, user_token):
    """Test getting rooms filtered by capacity."""
    response = client.get('/api/rooms?capacity=8',
                         headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    # Should only return rooms with capacity >= 8
    for room in data['rooms']:
        assert room['capacity'] >= 8


def test_get_rooms_with_location_filter(client, user_token):
    """Test getting rooms filtered by location."""
    response = client.get('/api/rooms?location=Building 1',
                         headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    for room in data['rooms']:
        assert 'Building 1' in room['location']


def test_get_rooms_with_equipment_filter(client, user_token):
    """Test getting rooms filtered by equipment."""
    response = client.get('/api/rooms?equipment=Projector',
                         headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    for room in data['rooms']:
        assert 'Projector' in room['equipment']


def test_get_specific_room(client, user_token):
    """Test getting specific room by ID."""
    response = client.get('/api/rooms/1',
                         headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['room']['id'] == 1


def test_get_nonexistent_room(client, user_token):
    """Test getting non-existent room."""
    response = client.get('/api/rooms/999',
                         headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 404


def test_update_room_as_admin(client, admin_token):
    """Test updating room as admin."""
    response = client.put('/api/rooms/1',
                         headers={'Authorization': f'Bearer {admin_token}'},
                         data=json.dumps({
                             'capacity': 12,
                             'equipment': ['Projector', 'Smart Board', 'TV']
                         }),
                         content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['room']['capacity'] == 12


def test_update_room_as_regular_user_denied(client, user_token):
    """Test that regular users cannot update rooms."""
    response = client.put('/api/rooms/1',
                         headers={'Authorization': f'Bearer {user_token}'},
                         data=json.dumps({
                             'capacity': 15
                         }),
                         content_type='application/json')
    
    assert response.status_code == 403


def test_update_room_status(client, admin_token):
    """Test updating room status."""
    response = client.patch('/api/rooms/1/status',
                           headers={'Authorization': f'Bearer {admin_token}'},
                           data=json.dumps({
                               'status': 'maintenance'
                           }),
                           content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['room']['status'] == 'maintenance'


def test_update_room_invalid_status(client, admin_token):
    """Test updating room with invalid status."""
    response = client.patch('/api/rooms/1/status',
                           headers={'Authorization': f'Bearer {admin_token}'},
                           data=json.dumps({
                               'status': 'invalid_status'
                           }),
                           content_type='application/json')
    
    assert response.status_code == 400


def test_get_available_rooms(client, user_token):
    """Test getting only available rooms."""
    response = client.get('/api/rooms/available',
                         headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    for room in data['rooms']:
        assert room['status'] == 'available'


def test_delete_room_as_admin(client, admin_token):
    """Test deleting room as admin."""
    response = client.delete('/api/rooms/2',
                           headers={'Authorization': f'Bearer {admin_token}'})
    
    assert response.status_code == 200


def test_delete_room_as_regular_user_denied(client, user_token):
    """Test that regular users cannot delete rooms."""
    response = client.delete('/api/rooms/1',
                           headers={'Authorization': f'Bearer {user_token}'})
    
    assert response.status_code == 403


def test_delete_nonexistent_room(client, admin_token):
    """Test deleting non-existent room."""
    response = client.delete('/api/rooms/999',
                           headers={'Authorization': f'Bearer {admin_token}'})
    
    assert response.status_code == 404


def test_unauthorized_access_to_protected_route(client):
    """Test accessing protected route without authentication."""
    response = client.get('/api/rooms')
    
    assert response.status_code == 401


def test_sql_injection_prevention(client, admin_token):
    """Test SQL injection prevention."""
    response = client.post('/api/rooms',
                          headers={'Authorization': f'Bearer {admin_token}'},
                          data=json.dumps({
                              'name': "Room'; DROP TABLE rooms--",
                              'capacity': 10,
                              'equipment': [],
                              'location': 'Building 1'
                          }),
                          content_type='application/json')
    
    # Should either succeed with sanitized input or fail validation
    assert response.status_code in [201, 400, 409]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=app', '--cov-report=html'])