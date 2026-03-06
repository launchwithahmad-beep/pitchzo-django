# Pitchzo Backend

REST API backend for Pitchzo using Django, Django REST Framework, and JWT authentication.

## Tech Stack

- Python
- Django
- Django REST Framework
- SQLite (Django default database)
- JWT (JSON Web Token) authentication

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py makemigrations authapp
python manage.py migrate
```

4. (Optional) Create a superuser for Django admin:

```bash
python manage.py createsuperuser
```

## Run Locally

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/api/`.

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create user (returns access + refresh tokens) |
| POST | `/api/auth/login` | Login (returns access + refresh tokens) |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/profile` | Get current user info (requires access token) |
| POST | `/api/auth/password-reset/request/` | Request password reset (sends 6-digit OTP to email) |
| POST | `/api/auth/password-reset/verify-otp/` | Verify OTP (returns reset_token) |
| POST | `/api/auth/password-reset/confirm/` | Set new password (requires reset_token) |

### Workspaces

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workspaces/` | List user's workspaces |
| POST | `/api/workspaces/` | Create workspace |
| GET | `/api/workspaces/<id>/` | Get workspace |
| PUT | `/api/workspaces/<id>/` | Update workspace |
| DELETE | `/api/workspaces/<id>/` | Delete workspace |

### Branding

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workspaces/<id>/branding/` | Get workspace branding |
| POST | `/api/workspaces/<id>/branding/` | Create branding |
| PUT | `/api/workspaces/<id>/branding/` | Update branding |
| DELETE | `/api/workspaces/<id>/branding/` | Delete branding |

## Authentication

Include the access token in the `Authorization` header for protected endpoints:

```
Authorization: Bearer <your-access-token>
```

Example with curl:

```bash
curl -H "Authorization: Bearer <access-token>" http://127.0.0.1:8000/api/auth/profile/
```

**Token refresh:** When the access token expires, POST to `/api/auth/refresh/` with the refresh token in the body:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<your-refresh-token>"}'
```

## Request/Response Format

All endpoints accept and return JSON. Example:

**Register:**
```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com", "password": "secret123", "first_name": "Jane", "last_name": "Doe"}'
# Returns: {"id": 1, "email": "jane@example.com", "first_name": "Jane", "last_name": "Doe", "access": "...", "refresh": "..."}
```

**Login:**
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com", "password": "secret123"}'
# Returns: {"access": "...", "refresh": "..."}
```

**Password reset (OTP flow):**
```bash
# 1. Request OTP (OTP is printed to Django console in dev)
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/request/ \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com"}'

# 2. Verify OTP
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/verify-otp/ \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com", "otp": "123456"}'
# Returns: {"success": true, "reset_token": "..."}

# 3. Set new password
curl -X POST http://127.0.0.1:8000/api/auth/password-reset/confirm/ \
  -H "Content-Type: application/json" \
  -d '{"reset_token": "...", "new_password": "newsecret123", "confirm_password": "newsecret123"}'
```

**Create workspace:**
```bash
curl -X POST http://127.0.0.1:8000/api/workspaces/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access-token>" \
  -d '{"name": "My Workspace"}'
```
