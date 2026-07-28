from __future__ import annotations

from typing import Any


class SIPError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int = 400,
        *,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        self.retryable = status_code >= 500 if retryable is None else retryable

    def as_dict(self, *, request_id: str | None = None, trace_id: str | None = None) -> dict[str, Any]:
        correlation = {
            "request_id": request_id or "none",
            "trace_id": trace_id or "none",
        }
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "retryable": self.retryable,
                "correlation": correlation,
            }
        }


class ValidationError(SIPError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, details, 422, retryable=False)


class AuthorizationError(SIPError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, details, 403, retryable=False)


class AuthenticationError(SIPError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, details, 401, retryable=False)


class ConflictError(SIPError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, details, 409, retryable=False)


class NotFoundError(SIPError):
    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(
            "NOT_FOUND",
            f"{resource_type} not found",
            {"resource_type": resource_type, "resource_id": resource_id},
            404,
            retryable=False,
        )
