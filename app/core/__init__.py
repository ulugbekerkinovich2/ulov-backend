"""Shared infrastructure: security, errors, logging, events, rate-limiting, RBAC.

Modules never depend on each other's ``core`` helpers for business logic; only
for framework-level plumbing (logging, errors, auth primitives).
"""
