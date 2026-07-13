"""Notification bounded context (spec 005-enterprise-platform §13, Wave 2).

Deliberately does not define its own event/type taxonomy — a ``Notification``
is a per-recipient pointer to an existing ``AuditEvent`` row plus read state,
never a duplicate copy of what happened. Display text is derived at read
time from the referenced audit event's real ``event_type``/``event_data``,
the same discipline the frontend's own ``buildApplicationTimeline`` already
uses for the human-readable Timeline (spec 005 §9's own precedent).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library. No other bounded context is imported — the composition that
decides *when* to notify someone about an audit event lives in the API
route layer (``mil.api.v1.*``), not here.
"""
