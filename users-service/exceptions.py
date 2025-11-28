# users-service/exceptions.py

class AppError(Exception):
    """Base class for all application-level errors."""

    status_code = 400
    error_code = "app_error"

    def __init__(self, message, status_code=None, error_code=None, payload=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.payload = payload or {}

    def to_dict(self):
        data = dict(self.payload or {})
        data.update(
            {
                "error": {
                    "code": self.error_code,
                    "message": self.message,
                }
            }
        )
        return data


class ValidationError(AppError):
    status_code = 400
    error_code = "validation_error"


class AuthError(AppError):
    status_code = 401
    error_code = "auth_error"


class PermissionError(AppError):
    status_code = 403
    error_code = "permission_denied"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"
