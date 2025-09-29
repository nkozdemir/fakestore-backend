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
