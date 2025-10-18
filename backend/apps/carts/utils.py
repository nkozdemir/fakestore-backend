from __future__ import annotations

from django.utils import timezone

from apps.carts.models import Cart


def ensure_user_cart(user):
    """
    Guarantee that the provided user has an associated cart.
    Staff and superusers are excluded.
    """
    if not user or getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return None
    defaults = {"date": timezone.now().date()}
    cart, _ = Cart.objects.get_or_create(user=user, defaults=defaults)
    return cart
