"""Error model and FastAPI exception handlers.

All errors cross the wire in a single shape so the frontend can localise by
``code`` and surface the message. The response envelope is:

    {"error": {"code": "...", "message": "...", "details": {...}}}

Business code raises :class:`AppError` (or a subclass); everything else is
caught and converted to 500.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import current_request_id, get_logger

log = get_logger(__name__)


class AppError(Exception):
    """Base exception for all expected, user-visible errors.

    Subclasses set a stable ``code`` the frontend keys translations off.
    """

    status_code: int = 400
    code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}

    def to_payload(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


# ---------------------------------------------------------------------------
# Common subclasses — import where needed instead of redefining codes ad-hoc.
# ---------------------------------------------------------------------------
class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"


# ---------------------------------------------------------------------------
# FastAPI wiring
# ---------------------------------------------------------------------------
def _json_error(
    status_code: int, code: str, message: str, details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    rid = current_request_id()
    body: Dict[str, Any] = {"error": {"code": code, "message": message, "details": details or {}}}
    if rid:
        body["error"]["request_id"] = rid
    return JSONResponse(status_code=status_code, content=body)


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    log.warning("app_error", code=exc.code, status=exc.status_code, path=request.url.path)
    return _json_error(exc.status_code, exc.code, exc.message, exc.details)


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Translate pydantic errors into a predictable field list.
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        fields.append(
            {"field": ".".join(loc), "code": err.get("type", "invalid"), "message": err.get("msg")}
        )
    return _json_error(422, "VALIDATION", "Request validation failed", {"fields": fields})


async def _handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    # Fallback for endpoints that still raise HTTPException directly.
    code = "HTTP_" + str(exc.status_code)
    return _json_error(exc.status_code, code, str(exc.detail))


async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", path=request.url.path)
    # Do not leak internals in prod.
    return _json_error(500, "INTERNAL", "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unhandled)
