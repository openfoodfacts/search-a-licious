"""Custom ASGI middlewares"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils import get_logger

logger = get_logger(__name__)


class CatchAllErrorsMiddleware:
    """Turn unhandled exceptions into a regular 500 response.

    Starlette's `ServerErrorMiddleware` is the outermost middleware, so the
    500 it builds never goes through `CORSMiddleware` and has no CORS headers:
    browsers then report a CORS error instead of the real failure.
    Add this middleware *before* `CORSMiddleware` so that it sits inside it.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def send_wrapper(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("Unhandled error on %s", scope.get("path"))
            if response_started:
                # too late to send a clean error response
                raise
            response = JSONResponse({"detail": "Internal Server Error"}, 500)
            await response(scope, receive, send)
