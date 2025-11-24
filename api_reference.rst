API Reference
=============

Users Service Endpoints
-----------------------

.. list-table::
   :header-rows: 1

   * - Method
     - Path
     - Description
   * - ``GET``
     - ``/health``
     - Health check for Users Service.
   * - ``POST``
     - ``/api/users/register``
     - Register a new user account.
   * - ``POST``
     - ``/api/users/login``
     - Login and receive a JWT token.
   * - ``GET``
     - ``/api/users``
     - List all users (admin / auditor only).
   * - ``GET``
     - ``/api/users/<username>``
     - Get details for a specific user.
   * - ``PUT``
     - ``/api/users/<username>``
     - Update user profile (self or admin).
   * - ``DELETE``
     - ``/api/users/<username>``
     - Delete a user (admin only, cannot delete self).

Example: Login
~~~~~~~~~~~~~~

**Request**

.. code-block:: http

   POST /api/users/login HTTP/1.1
   Host: localhost:5001
   Content-Type: application/json

   {
     "username": "admin",
     "password": "admin123"
   }

**Response**

.. code-block:: json

   {
     "message": "Login successful",
     "token": "<JWT_TOKEN>",
     "user": {
       "id": 1,
       "username": "admin",
       "email": "admin@test.com",
       "role": "admin"
     }
   }

Rooms Service Endpoints
-----------------------

.. list-table::
   :header-rows: 1

   * - Method
     - Path
     - Description
   * - ``GET``
     - ``/health``
     - Health check for Rooms Service.
   * - ``POST``
     - ``/api/rooms``
     - Create a new room (admin / facility).
   * - ``GET``
     - ``/api/rooms``
     - List rooms with optional filters.
   * - ``GET``
     - ``/api/rooms/<room_id>``
     - Get a single room by ID.
   * - ``PUT``
     - ``/api/rooms/<room_id>``
     - Update an existing room.
   * - ``DELETE``
     - ``/api/rooms/<room_id>``
     - Delete a room.

Example: List Rooms
~~~~~~~~~~~~~~~~~~~

.. code-block:: http

   GET /api/rooms?min_capacity=5&available=true HTTP/1.1
   Host: localhost:5002

Example: Authorization Header
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   Authorization: Bearer <JWT_TOKEN>
