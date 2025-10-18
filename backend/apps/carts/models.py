from django.db import models
from django.utils import timezone
from apps.users.models import User
from apps.catalog.models import Product


class Cart(models.Model):
    # Use auto-incrementing PK so DB assigns IDs on insert
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="cart")
    date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"Cart {self.id} for {self.user_id}"


class CartProduct(models.Model):
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="cart_products"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()

    class Meta:
        unique_together = ("cart", "product")
        db_table = "cart_products"
