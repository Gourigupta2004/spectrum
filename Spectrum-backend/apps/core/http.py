"""Minimal JSON API helpers: routing guard, body parsing, errors, CORS and rate limiting."""

import functools
import ipaddress
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .cache import dumps

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, **extra):
        super().__init__(message)
        self.status = status
        self.extra = extra


def json_response(data, status: int = 200, max_age: int | None = None) -> HttpResponse:
    body = data if isinstance(data, bytes) else dumps(data)
    response = HttpResponse(body, status=status, content_type="application/json")
    if max_age is None:
        response["Cache-Control"] = "no-store"
    else:
        response["Cache-Control"] = f"public, max-age={max_age}, s-maxage={max_age * 5}"
    return response


def api(methods=("GET",), max_age: int | None = None):
    """JSON view decorator: method check, JSON body parsing, ApiError -> JSON response."""

    def decorator(view):
        @csrf_exempt
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return json_response({"error": "Method not allowed"}, status=405)
            request.json = {}
            content_type = request.content_type or ""
            if request.method in {"POST", "PUT", "PATCH"} and content_type.startswith("application/json"):
                try:
                    request.json = json.loads(request.body or b"{}")
                except ValueError:
                    return json_response({"error": "Invalid JSON"}, status=400)
                if not isinstance(request.json, dict):
                    return json_response({"error": "Expected a JSON object"}, status=400)
            try:
                result = view(request, *args, **kwargs)
            except ApiError as exc:
                return json_response({"error": str(exc), **exc.extra}, status=exc.status)
            if isinstance(result, HttpResponse):
                return result
            return json_response(result, max_age=max_age if request.method == "GET" else None)

        return wrapper

    return decorator


def client_ip(request) -> str:
    """
    The visitor's IP. nginx sets X-Real-IP to the connecting address (clients cannot
    forge it); without a proxy we use REMOTE_ADDR. X-Forwarded-For is never trusted.
    """
    for value in (request.META.get("HTTP_X_REAL_IP", ""), request.META.get("REMOTE_ADDR", "")):
        try:
            return str(ipaddress.ip_address(value.strip()))
        except ValueError:
            continue
    return ""


def rate_limit(request, scope: str, limit: int, window: int, extra: str = "") -> None:
    key = f"rl:{scope}:{client_ip(request)}{':' + extra if extra else ''}"
    count = cache.get(key, 0)
    if count >= limit:
        raise ApiError("Too many requests. Please try again shortly.", status=429)
    cache.set(key, count + 1, window)


def text(data: dict, key: str, max_length: int = 200, required: bool = False) -> str:
    value = data.get(key, "")
    value = value.strip() if isinstance(value, str) else ""
    if required and not value:
        raise ApiError(f"{key} is required", field=key)
    return value[:max_length]


class CorsMiddleware:
    """Credential-less CORS for /api/ (the site sends bearer tokens, never cookies)."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed = set(settings.CORS_ALLOWED_ORIGINS)

    def __call__(self, request):
        if request.path.startswith("/media/public/"):
            # Public image variants may be drawn onto a canvas (roster PDF).
            response = self.get_response(request)
            response["Access-Control-Allow-Origin"] = "*"
            return response
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        origin = request.headers.get("Origin")
        if request.method == "OPTIONS" and origin:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        if origin and (origin in self.allowed or "*" in self.allowed):
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Headers"] = "authorization, content-type"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Max-Age"] = "86400"
            response["Vary"] = "Origin"
        return response
