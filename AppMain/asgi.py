"""
ASGI.

This is MAIN entrypoint to the application.
It exposes the ASGI callable as a module-level variable named ``app``.

"""
import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from AppMain.settings import AppSettings
from sap.loggers import logger

# Initialize application
app = FastAPI(docs_url=None, redoc_url=None, routes=[])


# Register middleware
# app.add_middleware(middleware.InitBeanieMiddleware, document_models=document_models)
app.add_middleware(SessionMiddleware, session_cookie="starlette", secret_key=AppSettings.CRYPTO_SECRET, max_age=None)
# if AppSettings.APP_ENV != "PROD":
#     app.add_middleware(middleware.LogServerErrorMiddleware)


# # Events to run on startups
# @app.on_event("startup")
# async def initialize_beanie() -> None:
#     """Initialize beanie on startup."""
#     await middleware.InitBeanieMiddleware.init_beanie(document_models=document_models, force=True)


# Always log exception
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Log all request validation errors to a file."""
    logger.exception(exc.errors())
    return await request_validation_exception_handler(request=request, exc=exc)


# @app.on_event("startup")
async def update_uvicorn_logger() -> None:
    """Log all uvicorn errors."""
    logger = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


class UvicornAccessLogFilter(logging.Filter):
    """Prevent health check to pollute access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Exclude /health/ from access logging."""
        if record.name == "uvicorn.access" and record.args:
            _, verb, path, _, response_status = record.args
            if verb == "GET" and path == "/health/" and response_status == 200:
                return False
        return True


# Filter out /health
logging.getLogger("uvicorn.access").addFilter(UvicornAccessLogFilter())
