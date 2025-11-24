# Smart Meeting Room System  
**EECE 435 – Lab 5 – Flask + SQLite + Docker + Testing**

Authors: **Maroun El Hajj, Mohamad Wajih Issa**

---

## 1. Project Overview

This project implements a small **microservice-based Smart Meeting Room System**:

- **Users Service** (`users-service/`)
  - Manages users: registration, login, profile update, delete
  - Passwords are hashed
  - Issues **JWT tokens** used for authentication
- **Rooms Service** (`rooms-service/`)
  - Manages meeting rooms (name, capacity, equipment, location, availability)
  - Protects write operations with JWT (admin / facility_manager only)
  - Provides rich filtering for listing rooms

Both services use **Flask + SQLite**, are containerized with **Docker**, orchestrated with **docker-compose**, tested with **pytest + coverage**, and documented using **Sphinx**.

---

## 2. Folder Structure

```text
smartmeetingroom_MarounElHajj_MohamadWajihIssa/
├── users-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── tests/
│   │   └── test_app.py
│   └── instance/ (SQLite DB)
├── rooms-service/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── tests/
│   │   └── test_app.py
│   └── instance/ (SQLite DB)
├── docker-compose.yml
├── docs (Sphinx sources: index.rst, architecture.rst, users_service.rst, rooms_service.rst, api_reference.rst, installation.rst)
└── _build/ (generated HTML documentation)
