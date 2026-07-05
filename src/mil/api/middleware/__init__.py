"""
Request middleware — applied to every inbound request before route handlers.

Middleware execution order (outermost to innermost, as added in
``main.create_app``):

  1. ``security_headers.py`` — adds defensive response headers (Sprint 8).
  2. ``telemetry.py``        — binds request_id/correlation_id to the
                                structured log context and records basic
                                HTTP metrics (Sprint 8).

Authentication is not ASGI middleware in this platform — it is the
``get_current_user`` FastAPI dependency in ``mil.api.deps``, resolved
per-route so it can raise a typed ``HTTPException`` with a JSON body
consistent with the rest of the API's error contract.
"""
