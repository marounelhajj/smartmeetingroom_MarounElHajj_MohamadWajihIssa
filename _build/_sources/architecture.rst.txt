System Architecture
===================

Overview
--------

The Smart Meeting Room System is a small microservices-based backend
designed for managing meeting rooms at AUB and handling basic user
authentication and authorization.

The system is composed of two Flask microservices:

* **Users Service** – handles user accounts, passwords, and JWT tokens.
* **Rooms Service** – manages meeting rooms, availability and filtering.

Each service has:

* its own **SQLite database** (``users.db`` and ``rooms.db``),
* its own **Flask application** and REST API,
* independent **unit tests** with ``pytest``.

High-Level Design
-----------------

* Clients (Postman / browser / other apps) send HTTP requests to the
  appropriate service:

  * ``localhost:5001`` → Users Service
  * ``localhost:5002`` → Rooms Service

* The **Users Service** authenticates users and issues a **JWT token**.
  The token encodes:

  * ``user_id``
  * ``username``
  * ``role`` (``admin``, ``regular_user``, ``facility_manager``, etc.)
  * expiration time (24 hours)

* The **Rooms Service** expects the JWT token in the ``Authorization``
  header (``Bearer <token>``). It decodes the token and checks the
  user's role before allowing changes to rooms.

Data Flow
---------

1. A new user registers using the Users Service.
2. The user logs in and receives a JWT token.
3. The client includes ``Authorization: Bearer <token>`` in requests
   to the Rooms Service.
4. The Rooms Service verifies the token and checks the role:

   * **Admin / Facility Manager** → allowed to create, update or delete rooms.
   * Any authenticated user → allowed to list rooms and read details.

Technology Stack
----------------

* Python 3.12
* Flask & Flask-SQLAlchemy
* SQLite (for simplicity in the lab)
* PyJWT for token creation/validation
* pytest for automated tests
* Sphinx for documentation
* Docker & docker-compose for containerized deployment
