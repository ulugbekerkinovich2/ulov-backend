"""Internal sqladmin panel for devops/DBA — mounted at /admin.

Disabled when ``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` / ``ADMIN_SESSION_SECRET``
are unset, so dev environments stay open and prod has to opt in explicitly.
"""

from app.admin.setup import mount_admin

__all__ = ["mount_admin"]
