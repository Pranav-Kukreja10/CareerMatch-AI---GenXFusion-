from ninja import NinjaAPI
from ninja.errors import ValidationError
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import OperationalError, IntegrityError, DatabaseError
from django.http import Http404
import logging

from accounts.api import router as accounts_router
from accounts.identity_api import identity_router
from students.api import router as students_router
from students.careermatch_live import router as careermatch_router

logger = logging.getLogger("careermatch.api")

api = NinjaAPI(
    title="CareerMatch AI",
    version="2.0.0",
    docs_url="/docs"
)

@api.exception_handler(ValidationError)
def validation_error_handler(request, exc: ValidationError):
    return api.create_response(
        request,
        {
            "status": "error",
            "code": "VALIDATION_ERROR",
            "message": "Validation failed for incoming request parameters.",
            "details": exc.errors
        },
        status=422
    )

@api.exception_handler(ObjectDoesNotExist)
@api.exception_handler(Http404)
def not_found_handler(request, exc):
    return api.create_response(
        request,
        {
            "status": "error",
            "code": "NOT_FOUND",
            "message": str(exc) if str(exc) else "Requested resource was not found."
        },
        status=404
    )

@api.exception_handler(PermissionDenied)
def permission_denied_handler(request, exc: PermissionDenied):
    return api.create_response(
        request,
        {
            "status": "error",
            "code": "FORBIDDEN",
            "message": str(exc) if str(exc) else "You do not have permission to perform this action."
        },
        status=403
    )

@api.exception_handler(OperationalError)
def operational_error_handler(request, exc: OperationalError):
    logger.warning(f"Database row contention or operational error: {exc}")
    return api.create_response(
        request,
        {
            "status": "error",
            "code": "CONCURRENCY_CONFLICT",
            "message": "Database row contention: Operation locked by a concurrent transaction. Please retry."
        },
        status=409
    )

@api.exception_handler(IntegrityError)
def integrity_error_handler(request, exc: IntegrityError):
    logger.error(f"Database integrity violation: {exc}")
    return api.create_response(
        request,
        {
            "status": "error",
            "code": "INTEGRITY_ERROR",
            "message": "A database constraint violation occurred (e.g. duplicate key or foreign key dependency)."
        },
        status=400
    )

@api.exception_handler(DatabaseError)
def database_error_handler(request, exc: DatabaseError):
    logger.error(f"Database system error: {exc}")
    return api.create_response(
        request,
        {
            "status": "error",
            "code": "DATABASE_ERROR",
            "message": "A transient database error occurred. The operation has been safely aborted."
        },
        status=503
    )

@api.exception_handler(Exception)
def global_internal_error_handler(request, exc: Exception):
    logger.exception(f"Unhandled internal server error: {exc}")
    return api.create_response(
        request,
        {
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred. Our engineers have been alerted."
        },
        status=500
    )

# Register Core CareerMatch AI API Routers
api.add_router("/auth", accounts_router)
api.add_router("/auth", identity_router)
api.add_router("/students", careermatch_router)
api.add_router("/students", students_router)


# -------------------------------------------------------------------------
# System Uptime & Database Health Endpoints
# -------------------------------------------------------------------------

@api.get("/ping", auth=None, tags=["System"])
def uptime_ping(request):
    """Lightweight zero-DB endpoint for external uptime monitors."""
    return {
        "status": "ok",
        "service": "careermatch-ai-backend",
        "alive": True,
        "message": "CareerMatch AI web service is warm and operational."
    }


@api.get("/health", auth=None, tags=["System"])
def system_health(request):
    """Diagnostic health check endpoint: reports system status and DB connectivity."""
    from django.conf import settings
    from django.db import connection
    import time

    start = time.perf_counter()
    db_ok = True
    detail = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        db_ok = False
        detail = str(e)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "CareerMatch AI",
        "database": {
            "status": "connected" if db_ok else "error",
            "latency_ms": latency_ms,
            "detail": detail
        },
        "environment": "development" if settings.DEVELOPMENT else "production"
    }
