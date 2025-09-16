from apps.common.repository import GenericRepository
from .models import Cart, CartProduct

class CartRepository(GenericRepository[Cart]):
    def __init__(self):
        super().__init__(Cart)

class CartProductRepository(GenericRepository[CartProduct]):
    def __init__(self):
        super().__init__(CartProduct)

    def list_for_cart(self, cart_id: int):
        return self.model.objects.filter(cart_id=cart_id)
