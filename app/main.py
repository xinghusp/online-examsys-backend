from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
# Import database initialization if needed (e.g., for creating tables)
# from app.db import base  # Import your Base and engine if creating tables here

# --- Optional: Database table creation (run once or use Alembic migrations) ---
# async def create_tables():
#     async with engine.begin() as conn:
#         # await conn.run_sync(Base.metadata.drop_all) # Use with caution!
#         await conn.run_sync(Base.metadata.create_all)
# --- End Optional ---

# --- Exception Handlers ---
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log the error details if needed
    # print(f"Validation error for {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    # Log the error details if needed
    # print(f"HTTP exception for {request.url}: Status {exc.status_code}, Detail {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

async def general_exception_handler(request: Request, exc: Exception):
    # Log the full traceback for unexpected errors
    # import traceback
    # traceback.print_exc()
    print(f"Unhandled exception for {request.url}: {exc}") # Basic logging
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )
# --- End Exception Handlers ---


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # Add other FastAPI options like version, description etc.
    # version="0.1.0",
    # description="API for the Online Examination System",
)

# --- Add Middleware ---
# CORS Middleware: Allows requests from specified origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"], # Allows all standard methods
        allow_headers=["*"], # Allows all headers
    )

# Add other middleware here if needed (e.g., logging, rate limiting)
# --- End Middleware ---


# --- Add Event Handlers ---
# @app.on_event("startup")
# async def startup_event():
#    # Optional: Create tables on startup (better to use migrations)
#    # await create_tables()
#    # Optional: Initialize Redis connection pool, etc.
#    print("Application startup complete.")
#
# @app.on_event("shutdown")
# async def shutdown_event():
#    # Optional: Clean up resources like database connections
#    print("Application shutdown.")
# --- End Event Handlers ---


# --- Add Exception Handlers ---
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
# Catch all other exceptions (optional, but good for production)
app.add_exception_handler(Exception, general_exception_handler)
# --- End Exception Handlers ---


# --- Include API Router ---
app.include_router(api_router, prefix=settings.API_V1_STR)
# --- End Include API Router ---


# --- Root Endpoint (Optional) ---
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
# --- End Root Endpoint ---

# Example of how to run (using uvicorn):
# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000