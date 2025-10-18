from __future__ import annotations

from django.utils import timezone

from apps.carts.models import Cart


def ensure_user_cart(user) -> Cart:
    """
    Guarantee that the provided user has an associated cart. Returns the cart.
    """
    defaults = {"date": timezone.now().date()}
    cart, _ = Cart.objects.get_or_create(user=user, defaults=defaults)
    return cart
