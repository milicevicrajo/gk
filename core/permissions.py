from __future__ import annotations

from typing import Iterable

from django.contrib.auth import get_user_model


def user_has_role(user, role: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if role == "admin":
        return user.is_staff or user.is_superuser
    if user.is_superuser:
        return True
    return user.groups.filter(name=role).exists()


def user_has_any_role(user, roles: Iterable[str]) -> bool:
    return any(user_has_role(user, role) for role in roles)


def get_role_emails(role: str) -> list[str]:
    User = get_user_model()
    return list(
        User.objects.filter(groups__name=role)
        .exclude(email="")
        .distinct()
        .values_list("email", flat=True)
    )
