"""
Policy bounded context.

Owns Policy Pack lifecycle (create, activate, deactivate — at most one active
pack per tenant) and its rule catalogue (``PolicyRule``, static configuration).
Evaluates a Finding against the active pack's rules via the registered
``PolicyProvider`` (resolved exclusively through ``ProviderRegistry``) and
persists the immutable outcome as a ``PolicyResult``.

``mil.policy`` never hardcodes verification logic — a rule's actual
triggering condition lives in the concrete ``PolicyProvider`` implementation
(``src/providers/policy/``), never in this package.

Public interface: policy.service.PolicyService
"""
