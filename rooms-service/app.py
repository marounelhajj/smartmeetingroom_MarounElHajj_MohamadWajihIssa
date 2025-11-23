"""
Rooms Service - Smart Meeting Room Management System
Manages meeting room availability and details.
Author: mwidotcom
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import jwt
from functools import wraps
import os
import datetime

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///rooms.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

db = SQLAlchemy(app)


# Models
class Room(db.Model):
    """
    Room model for storing meeting room information.
    
    Attributes:
        id (int): Primary key
        name (str): Room name
        capacity (int): Maximum number of people
        equipment (str): Available equipment (comma-separated)
        location (str): Room location/building
        status (str): Room status (available, booked, maintenance)
        created_at (datetime): Room creation timestamp
    """
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    equipment = db.Column(db.String(500))
    location = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), default='available')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def to_dict(self):
        """Convert room object to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'capacity': self.capacity,
            'equipment': self.equipment.split(',') if self.equipment else [],
            'location': self.location,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }


# Helper Functions
def sanitize_input(text):
    """Sanitize input to prevent SQL injection."""
    if text is None:
        return None
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
            if token.startswith('Bearer '):
                token = token[7:]
            
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = {
                'user_id': data['user_id'],
                'username': data['username'],
                'role': data['role']
            }
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated


def admin_or_facility_required(f):
    """Decorator to require admin or facility manager role."""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user['role'] not in ['admin', 'facility_manager']:
            return jsonify({'error': 'Admin or Facility Manager privileges required'}), 403
        return f(current_user, *args, **kwargs)
    return decorated


# Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'rooms'}), 200


@app.route('/api/rooms', methods=['POST'])
@token_required
@admin_or_facility_required
def add_room(current_user):
    """
    Add a new meeting room (Admin or Facility Manager only).
    
    Request Body:
        name (str): Room name
        capacity (int): Maximum capacity
        equipment (list): List of available equipment
        location (str): Room location
        status (str): Room status (optional, defaults to 'available')
    
    Returns:
        JSON: Created room details
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'capacity', 'location']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Sanitize inputs
        name = sanitize_input(data['name'])
        location = sanitize_input(data['location'])
        capacity = data['capacity']
        
        # Validate capacity
        if not isinstance(capacity, int) or capacity < 1:
            return jsonify({'error': 'Capacity must be a positive integer'}), 400
        
        # Check if room name already exists
        if Room.query.filter_by(name=name).first():
            return jsonify({'error': 'Room name already exists'}), 409
        
        # Process equipment list
        equipment_list = data.get('equipment', [])
        if isinstance(equipment_list, list):
            equipment = ','.join([sanitize_input(item) for item in equipment_list])
        else:
            equipment = sanitize_input(equipment_list)
        
        # Validate status
        status = sanitize_input(data.get('status', 'available'))
        valid_statuses = ['available', 'booked', 'maintenance']
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        # Create new room
        new_room = Room(
            name=name,
            capacity=capacity,
            equipment=equipment,
            location=location,
            status=status
        )
        
        db.session.add(new_room)
        db.session.commit()
        
        return jsonify({
            'message': 'Room added successfully',
            'room': new_room.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to add room: {str(e)}'}), 500


@app.route('/api/rooms', methods=['GET'])
@token_required
def get_rooms(current_user):
    """
    Get all rooms with optional filters.
    
    Query Parameters:
        capacity (int): Minimum capacity
        location (str): Room location
        equipment (str): Required equipment (comma-separated)
        status (str): Room status
    
    Returns:
        JSON: List of rooms matching filters
    """
    try:
        query = Room.query
        
        # Apply filters
        capacity = request.args.get('capacity', type=int)
        if capacity:
            query = query.filter(Room.capacity >= capacity)
        
        location = sanitize_input(request.args.get('location'))
        if location:
            query = query.filter(Room.location.ilike(f'%{location}%'))
        
        status = sanitize_input(request.args.get('status'))
        if status:
            query = query.filter(Room.status == status)
        
        equipment = sanitize_input(request.args.get('equipment'))
        if equipment:
            # Filter rooms that have all required equipment
            for item in equipment.split(','):
                query = query.filter(Room.equipment.ilike(f'%{item.strip()}%'))
        
        rooms = query.all()
        
        return jsonify({
            'rooms': [room.to_dict() for room in rooms],
            'count': len(rooms)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve rooms: {str(e)}'}), 500


@app.route('/api/rooms/<int:room_id>', methods=['GET'])
@token_required
def get_room(current_user, room_id):
    """
    Get specific room by ID.
    
    Args:
        room_id (int): Room ID
    
    Returns:
        JSON: Room details
    """
    try:
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        return jsonify({'room': room.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve room: {str(e)}'}), 500


@app.route('/api/rooms/<int:room_id>', methods=['PUT'])
@token_required
@admin_or_facility_required
def update_room(current_user, room_id):
    """
    Update room details (Admin or Facility Manager only).
    
    Args:
        room_id (int): Room ID to update
    
    Request Body:
        name (str): New room name (optional)
        capacity (int): New capacity (optional)
        equipment (list): New equipment list (optional)
        location (str): New location (optional)
        status (str): New status (optional)
    
    Returns:
        JSON: Updated room details
    """
    try:
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        data = request.get_json()
        
        # Update name
        if 'name' in data:
            name = sanitize_input(data['name'])
            # Check if new name already exists for another room
            existing_room = Room.query.filter_by(name=name).first()
            if existing_room and existing_room.id != room_id:
                return jsonify({'error': 'Room name already exists'}), 409
            room.name = name
        
        # Update capacity
        if 'capacity' in data:
            capacity = data['capacity']
            if not isinstance(capacity, int) or capacity < 1:
                return jsonify({'error': 'Capacity must be a positive integer'}), 400
            room.capacity = capacity
        
        # Update equipment
        if 'equipment' in data:
            equipment_list = data['equipment']
            if isinstance(equipment_list, list):
                room.equipment = ','.join([sanitize_input(item) for item in equipment_list])
            else:
                room.equipment = sanitize_input(equipment_list)
        
        # Update location
        if 'location' in data:
            room.location = sanitize_input(data['location'])
        
        # Update status
        if 'status' in data:
            status = sanitize_input(data['status'])
            valid_statuses = ['available', 'booked', 'maintenance']
            if status not in valid_statuses:
                return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
            room.status = status
        
        db.session.commit()
        
        return jsonify({
            'message': 'Room updated successfully',
            'room': room.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Update failed: {str(e)}'}), 500


@app.route('/api/rooms/<int:room_id>', methods=['DELETE'])
@token_required
@admin_or_facility_required
def delete_room(current_user, room_id):
    """
    Delete a room (Admin or Facility Manager only).
    
    Args:
        room_id (int): Room ID to delete
    
    Returns:
        JSON: Success message
    """
    try:
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        db.session.delete(room)
        db.session.commit()
        
        return jsonify({'message': f'Room {room.name} deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Delete failed: {str(e)}'}), 500


@app.route('/api/rooms/<int:room_id>/status', methods=['PATCH'])
@token_required
@admin_or_facility_required
def update_room_status(current_user, room_id):
    """
    Update only the room status (Admin or Facility Manager only).
    
    Args:
        room_id (int): Room ID
    
    Request Body:
        status (str): New status (available, booked, maintenance)
    
    Returns:
        JSON: Updated room details
    """
    try:
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'error': 'Status is required'}), 400
        
        status = sanitize_input(data['status'])
        valid_statuses = ['available', 'booked', 'maintenance']
        
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        room.status = status
        db.session.commit()
        
        return jsonify({
            'message': 'Room status updated successfully',
            'room': room.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Status update failed: {str(e)}'}), 500


@app.route('/api/rooms/available', methods=['GET'])
@token_required
def get_available_rooms(current_user):
    """
    Get all available rooms with optional filters.
    
    Query Parameters:
        capacity (int): Minimum capacity
        location (str): Room location
        equipment (str): Required equipment (comma-separated)
    
    Returns:
        JSON: List of available rooms
    """
    try:
        query = Room.query.filter_by(status='available')
        
        # Apply filters
        capacity = request.args.get('capacity', type=int)
        if capacity:
            query = query.filter(Room.capacity >= capacity)
        
        location = sanitize_input(request.args.get('location'))
        if location:
            query = query.filter(Room.location.ilike(f'%{location}%'))
        
        equipment = sanitize_input(request.args.get('equipment'))
        if equipment:
            for item in equipment.split(','):
                query = query.filter(Room.equipment.ilike(f'%{item.strip()}%'))
        
        rooms = query.all()
        
        return jsonify({
            'rooms': [room.to_dict() for room in rooms],
            'count': len(rooms)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve available rooms: {str(e)}'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5002, debug=True)