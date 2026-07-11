"""Assignment bounded context (spec 005-enterprise-platform §1, Wave 2).

Tracks which Relationship Manager owns an application and which Underwriter
is assigned to review it — the substrate for the RM/Banker Workspace.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library. No other bounded context is imported.
"""
