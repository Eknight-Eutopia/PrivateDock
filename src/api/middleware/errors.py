from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


def _error_code(status: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        429: "rate_limited",
        500: "internal",
    }
    return mapping.get(status, str(status).lower().replace(" ", "_"))


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            if response.status_code >= 400:
                body = {"ok": False, "error": {"code": _error_code(response.status_code), "message": response.reason_phrase}}
                return JSONResponse(body, status_code=response.status_code)
            return response
        except Exception as e:
            return JSONResponse(
                {"ok": False, "error": {"code": "internal", "message": str(e)}},
                status_code=500,
            )
