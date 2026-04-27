"""Roles, scopes, and FastAPI dependencies for authorization.

Keep this pure — no DB lookups. The dependencies here only inspect the already
authenticated :class:`CurrentUser` attached by ``deps.get_current_user``.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Callable, Iterable, Optional

from fastapi import Depends

from app.core.errors import ForbiddenError

if TYPE_CHECKING:
    from app.deps import CurrentUser


class Role(str, Enum):
    CUSTOMER = "customer"
    MECHANIC = "mechanic"
    OWNER = "owner"
    ADMIN = "admin"


ADMIN_ROLES = frozenset({Role.ADMIN})
STAFF_ROLES = frozenset({Role.MECHANIC, Role.OWNER, Role.ADMIN})
OWNER_ROLES = frozenset({Role.OWNER, Role.ADMIN})
ANY_ROLE = frozenset(Role)


def require_role(*roles: Role) -> Callable:
    """Return a FastAPI dependency that enforces one of ``roles``.

    Usage::

        @router.get("/stats", dependencies=[Depends(require_role(Role.OWNER))])
        def stats(...): ...
    """
    allowed = frozenset(roles) or ANY_ROLE
    from app.deps import get_current_user  # local import breaks the cycle

    def _dep(user: "CurrentUser" = Depends(get_current_user)) -> "CurrentUser":
        if Role(user.role) not in allowed:
            raise ForbiddenError(
                "Insufficient permissions",
                code="AUTH_FORBIDDEN",
                details={"required": [r.value for r in allowed]},
            )
        return user

    return _dep


def allow_roles(roles: Iterable[Role], user_role: str) -> bool:
    try:
        return Role(user_role) in frozenset(roles)
    except ValueError:
        return False


def has_any_role(user_role: Optional[str], roles: Iterable[Role]) -> bool:
    if user_role is None:
        return False
    return allow_roles(roles, user_role)
