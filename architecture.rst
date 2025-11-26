System Architecture
===================

Overview
--------

The Smart Meeting Room System is a microservices-based backend that manages users, rooms, bookings, and reviews with JWT authentication and role-based access control.

Services
--------

* **Users Service** - issues JWT tokens and manages accounts/roles.
* **Rooms Service** - manages meeting rooms, capacity, equipment, and availability flags.
* **Bookings Service** - handles room reservations, conflict detection, and booking history.
* **Reviews Service** - collects room feedback, supports moderation and flagging.

Cross-cutting enhancements:

* **Rate limiting** (Bookings/Reviews): sliding window per IP + endpoint to throttle abusive callers.
* **Auditing/logging** (Bookings/Reviews): rotating file logs capturing user/role/method/path/status for traceability.
* **Caching** (Bookings availability, Reviews per-room): in-memory TTL caches to speed frequent reads.
* **Load balancing**: Nginx reverse proxy (``load-balancer`` service) to front Bookings and Reviews for horizontal scaling.

Each service has its own **SQLite database**, **Flask application**, and **pytest** suite.

High-Level Design
-----------------

* Clients (Postman / backend consumers) call the appropriate service:

  * ``localhost:5001`` - Users Service
  * ``localhost:5002`` - Rooms Service
  * ``localhost:5003`` - Bookings Service
  * ``localhost:5004`` - Reviews Service

* The **Users Service** authenticates users and issues a **JWT** containing:

  * ``user_id``
  * ``username``
  * ``role`` (``admin``, ``regular_user``, ``facility_manager``, ``moderator``, ``auditor``, etc.)
  * expiration time (24 hours)

* The other services expect the JWT in the ``Authorization`` header (``Bearer <token>``) and enforce RBAC on the decoded payload.

Data Flow
---------

1. A user registers through the Users Service.
2. The user logs in and receives a JWT token.
3. The client includes ``Authorization: Bearer <token>`` when calling Rooms, Bookings, or Reviews.
4. Each service validates the token and checks roles:

   * **Admin / Facility Manager** - manage rooms and all bookings.
   * **Regular User** - manage own bookings and reviews.
   * **Moderator/Admin** - moderate reviews (hide/flag/unflag).
   * **Auditor** - read-only access where applicable.

Technology Stack
----------------

* Python 3.12
* Flask & Flask-SQLAlchemy
* SQLite
* PyJWT for token creation/validation
* pytest for automated tests
* Sphinx for documentation
* Docker & docker-compose for containerized deployment
