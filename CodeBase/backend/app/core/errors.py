from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

CODES: dict[str, tuple[int, bool]] = {
    "UNAUTHORIZED": (401, False),
    "FORBIDDEN": (403, False),
    "NOT_FOUND": (404, False),
    "NOT_READY": (409, True),
    "FILE_TOO_LARGE": (413, False),
    "UNSUPPORTED_TYPE": (415, False),
    "INVALID_CLASSIFICATION": (422, False),
    "IMMUTABLE_FIELD": (422, False),
    "OCR_FAILED": (422, True),
    "EXTRACTION_FAILED": (422, True),
    "DOCUMENTS_NOT_EXPORTABLE": (422, False),
    "HOSTED_ENDPOINT_REFUSED": (422, False),
    "RATE_LIMITED": (429, True),
    "INTERNAL": (500, True),
}

STATUS_TO_CODE = {
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "NOT_FOUND",
    409: "NOT_READY",
    413: "FILE_TOO_LARGE",
    415: "UNSUPPORTED_TYPE",
    422: "EXTRACTION_FAILED",
    429: "RATE_LIMITED",
}


class ApiError(Exception):
    def __init__(self, code: str, message: str) -> None:
        if code not in CODES:
            raise KeyError(f"{code} is not in the API_CONTRACT §8 error table")
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code, self.retryable = CODES[code]


def envelope(code: str, message: str, trace_id: str) -> dict[str, Any]:
    status_code, retryable = CODES[code]
    return {
        "error": {
            "code": code,
            "message": message,
            "trace_id": trace_id,
            "retryable": retryable,
        }
    }


def _trace_id(request: Request) -> str:
    existing = getattr(request.state, "trace_id", None)
    return str(existing) if existing else str(uuid.uuid4())


def error_response(request: Request, code: str, message: str) -> JSONResponse:
    status_code, _ = CODES[code]
    return JSONResponse(
        status_code=status_code,
        content=envelope(code, message, _trace_id(request)),
        headers={"X-Trace-Id": _trace_id(request)},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(request, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = STATUS_TO_CODE.get(exc.status_code, "INTERNAL")
        return error_response(request, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(request, "EXTRACTION_FAILED", "Request body failed validation.")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        return error_response(request, "INTERNAL", "Internal error.")
