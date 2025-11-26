Reviews Service
===============

Overview
--------
The Reviews service lets authenticated users submit feedback on meeting rooms, edit or delete their own reviews, and allows moderators/admins to flag, hide, or unhide inappropriate content.

Key Models
----------
- ``Review``: ``user_id``, ``username``, ``room_id``, ``rating`` (1-5), ``comment``, ``is_flagged``, ``hidden``.

Endpoints
---------
- ``GET /health`` - Health probe.
- ``GET /api/reviews`` - List reviews (all for moderators/admins; visible-only for others).
- ``GET /api/reviews/room/<room_id>`` - Public list for a room (hidden reviews excluded).
- ``POST /api/reviews`` - Submit review (auth required).
- ``PUT /api/reviews/<review_id>`` - Update own review (or moderator/admin).
- ``DELETE /api/reviews/<review_id>`` - Delete own review (or moderator/admin).
- ``PATCH /api/reviews/<review_id>/flag`` - Flag or unflag; clearing requires moderator/admin.
- ``PATCH /api/reviews/<review_id>/moderate`` - Moderator/admin hide/unhide and clear flags.

Part II Enhancements
--------------------
- **Rate limiting**: sliding window throttling per IP/endpoint to prevent abuse.
- **Auditing/logging**: rotating file logs (``logs/reviews.log``) capturing user, role, path, and status.
- **Caching**: in-memory TTL cache for per-room review lists to speed repeated reads.

Submit Review Example
---------------------

.. code-block:: http

   POST /api/reviews HTTP/1.1
   Host: localhost:5004
   Authorization: Bearer <JWT_TOKEN>
   Content-Type: application/json

   {
     "room_id": 2,
     "rating": 5,
     "comment": "Great AV quality and clean space."
   }
