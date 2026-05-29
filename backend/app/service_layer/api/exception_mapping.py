from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .errors import ConflictError, DomainError, NotFoundError, ServiceUnavailableError, ValidationError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationError)
    async def handle_validation_error(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(NotFoundError)
    async def handle_not_found_error(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(ConflictError)
    async def handle_conflict_error(request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(ServiceUnavailableError)
    async def handle_service_unavailable_error(request: Request, exc: ServiceUnavailableError):
        return JSONResponse(status_code=503, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"code": "internal_error", "message": "内部错误"})
