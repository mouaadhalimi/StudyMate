from starlette.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter
from starlette.responses import Response
from slowapi.util import get_remote_address
from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, rags, documents, search, discussions
from dotenv import load_dotenv
import os
from .db import Base, engine

# Initialize database schema
Base.metadata.create_all(bind=engine)


# --- Security Headers Configuration ---------------------------------------------------------
try:
    from secure import SecureHeaders
except ImportError:

    class SecureHeaders:
        """Fallback security headers middleware generator."""
        def starlette(self, response)-> Response:
            """
            Apply standard security headers to a Starlette/FastAPI response.

            Args:
                response (Response): Outgoing HTTP response object.

            Returns:
                Response: Response with security headers injected.
            """
            headers = {
                "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "geolocation=()",
                "X-XSS-Protection": "1; mode=block",
                "Content-Security-Policy": "default-src 'self'"
            }
            for k, v in headers.items():
                response.headers[k] = v
            return response

# --- Rate Limiting --------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)
secure_headers = SecureHeaders()

# --- Environment Configuration --------------------------------------------------------------
ALLOW_ORIGINS = os.getenv('ALLOW_ORIGINS','http://localhost:3000,http://localhost:8000').split(',')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1').split(',')

# Load environment variables from .env file
load_dotenv()

def create_app()-> FastAPI:
    """
    Create and configure the FastAPI application instance.

    This function builds the app, attaches middleware for compression,
    CORS, and includes all modular routers (auth, rags, documents, etc.).

    Returns:
        FastAPI: Configured FastAPI application.
    """
    app = FastAPI(title="RAG Backend", version="1.0.0")
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(auth.router)
    app.include_router(rags.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(discussions.router)
    return app

# Instantiate application
app = create_app()

# --- Middleware Setup -----------------------------------------------------------------------

try:
    app.add_middleware(GZipMiddleware, minimum_size=1000)
except Exception:
    pass

try:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
except Exception:
    pass

try:
    app.add_middleware(CORSMiddleware, allow_origins=ALLOW_ORIGINS, allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
except Exception:
    pass

# --- Secure Headers Middleware --------------------------------------------------------------
def _inject_secure_headers()-> None:
    """
    Inject middleware to attach security headers to every HTTP response.

    Adds common headers like:
    - HSTS
    - X-Frame-Options
    - Content-Security-Policy
    - X-Content-Type-Options
    """
    try:
        from fastapi import Request
        from starlette.responses import Response
        @app.middleware("http")
        async def set_secure_headers(request: Request, call_next):
            response: Response = await call_next(request)
            try:
                secure_headers.starlette(response)
            except Exception:
                pass
            return response
    except Exception:
        pass
    return _inject_secure_headers
_inject_secure_headers()

# --- Rate Limiting Middleware ---------------------------------------------------------------
def _inject_rate_limit()-> None:
    """
    Inject middleware for global API rate limiting.

    Default configuration: `60 requests per minute per IP`.
    """
    try:
        @app.middleware("http")
        @limiter.limit("60/minute")
        async def rate_limit(request, call_next):
            return await call_next(request)
    except Exception:
        pass
    return _inject_rate_limit
_inject_rate_limit()
