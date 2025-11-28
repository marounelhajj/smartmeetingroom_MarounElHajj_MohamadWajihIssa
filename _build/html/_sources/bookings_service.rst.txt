Bookings Service
================

Overview
--------
The Bookings service manages room reservations, prevents double bookings, and exposes booking history and availability checks. It expects JWT tokens created by the Users service and respects the RBAC profile (admin, facility_manager, auditor can view/manage all bookings; other roles can manage only their own).

Key Models
----------
- ``Booking``: ``user_id``, ``username``, ``room_id``, ``room_name``, ``start_time``, ``end_time``, ``status``.

Endpoints
---------
- ``GET /health`` - Service health probe.
- ``GET /api/bookings`` - List bookings (scope depends on role).
- ``GET /api/bookings/history/<user_id>`` - Booking history for a specific user.
- ``GET /api/bookings/check`` - Availability check for a room and time window.
- ``POST /api/bookings`` - Create booking, prevents overlaps.
- ``PUT /api/bookings/<booking_id>`` - Update booking (owner or admin/facility/auditor).
- ``DELETE /api/bookings/<booking_id>`` - Cancel booking (soft delete).

Part II Enhancements
--------------------
- **Rate limiting**: sliding window throttling per IP/endpoint to prevent abuse.
- **Auditing/logging**: rotating file logs (``logs/bookings.log``) capturing user, role, path, and status.
- **Caching**: in-memory TTL cache for availability checks and booking history to accelerate repeat reads.

Availability Check Example
--------------------------

.. code-block:: http

   GET /api/bookings/check?room_id=10&start_time=2025-01-01T10:00&end_time=2025-01-01T11:00 HTTP/1.1
   Host: localhost:5003

Create Booking Example
----------------------

.. code-block:: http

   POST /api/bookings HTTP/1.1
   Host: localhost:5003
   Authorization: Bearer <JWT_TOKEN>
   Content-Type: application/json

   {
     "room_id": 3,
     "room_name": "Conference A",
     "start_time": "2025-01-01T14:00",
     "end_time": "2025-01-01T15:00"
   }
