Users Service
=============

Database Model
--------------

The Users Service stores all account information in the ``users`` table.

**Table: users**

===================  ============================
Column               Description
===================  ============================
``id``               Integer primary key
``name``             Full name of the user
``username``         Unique username (indexed)
``password``         Hashed password (Werkzeug)
``email``            Unique email (indexed)
``role``             User role (RBAC)
``created_at``       UTC timestamp of creation
===================  ============================

Supported roles:

* ``admin``
* ``regular_user``
* ``facility_manager``
* ``moderator``
* ``auditor``
* ``service_account``

All routes return **JSON** responses.

JWT Authentication
------------------

On successful login, the service returns a JWT token that contains:

* ``user_id``
* ``username``
* ``role``
* ``exp`` (24 hours after login)

The token is signed with ``HS256`` using ``SECRET_KEY`` from the Flask config.

Protected Endpoints
-------------------

Most endpoints use a ``@token_required`` decorator which:

1. Reads the ``Authorization`` header.
2. Extracts the token from either:

   * ``Bearer <token>`` or
   * ``<token>`` directly.

3. Decodes the JWT.
4. Loads the current user from the database.
5. Passes ``current_user`` into the view function.

Administrative endpoints additionally use ``@admin_required``.

Example Workflows
-----------------

**Register + Login**

1. ``POST /api/users/register`` with name, username, email and password
2. ``POST /api/users/login`` with username and password
3. Copy the returned ``token`` and use it in:

   ``Authorization: Bearer <token>``

**List All Users (admin / auditor only)**

* ``GET /api/users`` with a valid admin/auditor token.
