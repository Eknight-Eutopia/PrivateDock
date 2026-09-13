from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any = None) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data})


def error(code: str, message: str, details: Any = None, status_code: int = 200) -> JSONResponse:
    body = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status_code)
