from apps.common.repository import GenericRepository
from .models import Cart, CartProduct


class CartRepository(GenericRepository[Cart]):
    def __init__(self):
        super().__init__(Cart)

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
        return self.model.objects.filter(cart_id=cart_id)

    def delete_for_cart(self, cart: Cart):
        self.model.objects.filter(cart=cart).delete()

    def get_for_cart_product(self, cart_id: int, product_id: int):
        return self.model.objects.filter(cart_id=cart_id, product_id=product_id).first()

    def delete_product(self, cart: Cart, product_id: int):
        self.model.objects.filter(cart=cart, product_id=product_id).delete()
