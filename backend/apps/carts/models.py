from django.db import models
from apps.users.models import User
from apps.catalog.models import Product

class Cart(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')
    date = models.DateField()

    def __str__(self):
        return f"Cart {self.id} for {self.user_id}"

class CartProduct(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='cart_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()

    class Meta:
        unique_together = ('cart', 'product')
        db_table = 'cart_products'
