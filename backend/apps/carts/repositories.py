from apps.common.repository import GenericRepository
from .models import Cart, CartProduct


class CartRepository(GenericRepository[Cart]):
    def __init__(self):
        super().__init__(Cart)

    def _base_queryset(self):
        return (
            self.model.objects.select_related("user")
            .prefetch_related("cart_products__product__categories")
            .prefetch_related("cart_products__product")
        )

    def list(self, **filters):
        return self._base_queryset().filter(**filters)

    def get(self, **filters):
        return self._base_queryset().filter(**filters).first()

    def update_scalar(self, cart: Cart, **fields):
        dirty = False
        for k, v in fields.items():
            if v is not None:
                setattr(cart, k, v)
                dirty = True
        if dirty:
            cart.save()
        return cart


class CartProductRepository(GenericRepository[CartProduct]):
    def __init__(self):
        super().__init__(CartProduct)

    def list_for_cart(self, cart_id: int):
        return (
            self.model.objects.filter(cart_id=cart_id)
            .select_related("product")
            .prefetch_related("product__categories")
        )

    def delete_for_cart(self, cart: Cart):
        self.model.objects.filter(cart=cart).delete()

    def get_for_cart_product(self, cart_id: int, product_id: int):
        return (
            self.model.objects.filter(cart_id=cart_id, product_id=product_id)
            .select_related("product")
            .prefetch_related("product__categories")
            .first()
        )

    def delete_product(self, cart: Cart, product_id: int):
        self.model.objects.filter(cart=cart, product_id=product_id).delete()
