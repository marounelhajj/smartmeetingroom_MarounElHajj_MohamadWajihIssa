# Smart Meeting Room System
**EECE 435 - Flask + SQLite + Docker + Testing**

Authors: **Maroun El Hajj, Mohamad Wajih Issa**

---

## 1. Project Overview

Microservice-based backend for a Smart Meeting Room & Management System:

- **Users Service** (`users-service/`): registration, login, profile management, JWT issuance, RBAC.
- **Rooms Service** (`rooms-service/`): CRUD for meeting rooms (name, capacity, equipment, location, availability).
- **Bookings Service** (`bookings-service/`): create/update/cancel bookings, prevent overlaps, booking history, availability checks.
- **Reviews Service** (`reviews-service/`): submit/update/delete reviews, rating validation, moderation (flag/hide/unhide).

Each service is built with **Flask + SQLite**, containerized with **Docker**, orchestrated via **docker-compose**, tested using **pytest**, and documented using **Sphinx**.

Part II enhancements implemented:
- **Rate limiting**: sliding-window limiter (env-configurable) on Bookings and Reviews services to prevent abuse.
- **Auditing/logging**: rotating file logs for Bookings (`logs/bookings.log`) and Reviews (`logs/reviews.log`) capturing user, role, path, and status.
- **Caching**: in-memory TTL caches for bookings availability/history and per-room reviews to speed frequent reads.
- **Load balancing**: Nginx reverse proxy (`load-balancer` service) fronting Bookings/Reviews on port `8080` for future horizontal scaling.

---

## 2. Folder Structure

```text
smartmeetingroom_MarounElHajj_MohamadWajihIssa/
├── users-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
├── rooms-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
├── bookings-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
├── reviews-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
├── docker-compose.yml
├── docs (Sphinx sources: index.rst, architecture.rst, users_service.rst,
│            rooms_service.rst, bookings_service.rst, reviews_service.rst,
│            api_reference.rst, installation.rst)
└── _build/ (generated HTML documentation)
```

---

## 3. Quick Start

```bash
docker-compose up --build
```

Services will be available on:
- Users: `http://localhost:5001`
- Rooms: `http://localhost:5002`
- Bookings: `http://localhost:5003`
- Reviews: `http://localhost:5004`
- Load Balancer (Bookings/Reviews proxy): `http://localhost:8080` (`/bookings/*`, `/reviews/*`)

To run tests inside a service:

```bash
cd bookings-service && pytest -q
```
