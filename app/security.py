"""Bound requests before parsing; keep limits shared in production."""
import asyncio
import hashlib
import ipaddress
import logging
import os
import threading
import time
from collections import OrderedDict
from uuid import uuid4

from fastapi import HTTPException
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 16 * 1024


def production():
    return os.getenv("APP_ENV", "development") == "production"


class RateLimiter:
    SCRIPT = """
    local n = redis.call('INCR', KEYS[1])
    if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
    return {n, redis.call('TTL', KEYS[1])}
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._local = OrderedDict()
        self._redis = None
        self._url = None

    def redis_client(self):
        url = os.getenv("REDIS_URL", "").strip()
        if not url:
            return None
        if self._redis is None or url != self._url:
            import redis
            self._redis = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, max_connections=20)
            self._url = url
        return self._redis

    def ready(self):
        try:
            client = self.redis_client()
            return bool(client.ping()) if client else not production()
        except Exception:
            return False

    def check(self, identity, limit, seconds=60):
        salt = os.getenv("RATE_LIMIT_SALT", "local-development")
        key = "creditsure:limit:" + hashlib.sha256(f"{salt}:{identity}".encode()).hexdigest()
        try:
            client = self.redis_client()
            if client:
                count, ttl = client.eval(self.SCRIPT, 1, key, seconds)
            elif production():
                raise RuntimeError("shared limiter required")
            else:
                with self._lock:
                    now = time.monotonic()
                    count, expiry = self._local.pop(key, (0, now + seconds))
                    if expiry <= now:
                        count, expiry = 0, now + seconds
                    count += 1
                    self._local[key] = (count, expiry)
                    while len(self._local) > 4096:
                        self._local.popitem(last=False)
                    ttl = max(1, int(expiry - now))
        except Exception:
            raise HTTPException(503, "Abuse protection is temporarily unavailable.") from None
        if count > limit:
            raise HTTPException(429, "Too many requests. Try again later.", headers={"Retry-After": str(max(1, ttl))})


limiter = RateLimiter()


def client_address(scope):
    peer = (scope.get("client") or ("unknown", 0))[0]
    trusted = [ipaddress.ip_network(c.strip()) for c in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",") if c.strip()]
    try:
        if any(ipaddress.ip_address(peer) in network for network in trusted):
            headers = dict(scope.get("headers", []))
            chain = headers.get(b"x-forwarded-for", b"").decode("ascii").split(",")
            for value in reversed(chain):
                address = ipaddress.ip_address(value.strip())
                if not any(address in network for network in trusted):
                    return str(address)
    except (ValueError, UnicodeError):
        pass
    return peer


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        path = scope.get("path", "")
        headers = dict(scope.get("headers", []))
        response_started = False
        csp = ("default-src 'self'; script-src 'self' https://challenges.cloudflare.com; "
               "style-src 'self'; img-src 'self' data:; font-src 'self'; "
               "connect-src 'self' https://*.supabase.co https://challenges.cloudflare.com; "
               "frame-src https://challenges.cloudflare.com; frame-ancestors 'none'; "
               "object-src 'none'; base-uri 'none'; form-action 'self'")

        async def secure_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                additions = {"content-security-policy": csp, "x-content-type-options": "nosniff",
                             "x-frame-options": "DENY", "referrer-policy": "no-referrer",
                             "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
                             "x-request-id": request_id}
                if production():
                    additions["strict-transport-security"] = "max-age=31536000"
                if path.startswith("/api/") or path in ("/signin", "/signup", "/workspace"):
                    additions["cache-control"] = "no-store"
                current = [(k, v) for k, v in message.get("headers", []) if k.decode().lower() not in additions]
                message["headers"] = current + [(k.encode(), v.encode()) for k, v in additions.items()]
            await send(message)

        async def reject(status, detail, extra=None):
            await JSONResponse({"detail": detail}, status_code=status, headers=extra)(scope, receive, secure_send)

        try:
            if path not in ("/api/health", "/api/ready"):
                await asyncio.to_thread(limiter.check, f"ip:{client_address(scope)}", 240)
            if len(headers.get(b"authorization", b"")) > 8192:
                return await reject(400, "Invalid authorization header.")
            if len(headers.get(b"range", b"")) > 256 or b"," in headers.get(b"range", b""):
                return await reject(400, "Multiple or oversized file ranges are not supported.")
            length = headers.get(b"content-length")
            if length is not None:
                try:
                    size = int(length)
                except ValueError:
                    return await reject(400, "Invalid request length.")
                if size < 0:
                    return await reject(400, "Invalid request length.")
                if size > MAX_BODY_BYTES:
                    return await reject(413, "Request exceeds the 16 KiB limit.")
            if scope["method"] in ("POST", "PUT", "PATCH", "DELETE"):
                media = headers.get(b"content-type", b"").split(b";")[0].strip().lower()
                if media != b"application/json" and (length != b"0" or scope["method"] != "DELETE"):
                    return await reject(415, "Send application/json.")
                body = bytearray()
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > MAX_BODY_BYTES:
                            return await reject(413, "Request exceeds the 16 KiB limit.")
                        if not message.get("more_body", False):
                            break
                delivered = False
                async def replay():
                    nonlocal delivered
                    if delivered:
                        return {"type": "http.request", "body": b"", "more_body": False}
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await self.app(scope, replay, secure_send)
            await self.app(scope, receive, secure_send)
        except HTTPException as error:
            await reject(error.status_code, error.detail, error.headers)
        except TimeoutError:
            await reject(408, "The request took too long to upload.")
        except Exception as error:
            if response_started:
                raise
            logging.getLogger("creditsure").error("request_failed id=%s type=%s", request_id, type(error).__name__)
            await reject(500, "The request could not be completed. Contact support with the request ID.")
