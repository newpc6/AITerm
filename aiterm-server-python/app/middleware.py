import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings

logger = logging.getLogger("aiterm")


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next):
        if not self.settings.log.enabled:
            return await call_next(request)

        start_time = time.time()

        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    request_body = body[:self.settings.log.request_body].decode("utf-8", errors="replace")
            except Exception:
                pass

        response = await call_next(request)

        duration = time.time() - start_time

        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2)
        }

        if request_body:
            log_data["request_body"] = request_body

        if response.status_code >= 400:
            logger.warning(f"Request: {log_data}")
        else:
            logger.info(f"Request: {log_data}")

        return response


class CORSMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.settings = get_settings()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                origin = None
                for name, value in scope.get("headers", []):
                    if name == b"origin":
                        origin = value.decode("utf-8")
                        break

                if origin and origin in self.settings.cors.allowed_origins:
                    headers[b"access-control-allow-origin"] = origin.encode("utf-8")
                    headers[b"access-control-allow-credentials"] = b"true"
                    headers[b"access-control-allow-methods"] = b"GET, POST, PUT, DELETE, OPTIONS"
                    headers[b"access-control-allow-headers"] = b"Content-Type, Authorization"

                message["headers"] = list(headers.items())

            await send(message)

        if scope["method"] == "OPTIONS":
            response = Response(status_code=204)
            await response(scope, receive, send_wrapper)
            return

        await self.app(scope, receive, send_wrapper)
