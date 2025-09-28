from django.db import models
from django.utils import timezone
from apps.users.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    # Auto-increment primary key (previously manual integer)
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    image = models.TextField()
    rate = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    count = models.IntegerField(default=0)
    categories = models.ManyToManyField(Category, related_name='products', through='ProductCategory')

    def __str__(self):
        return self.title

    class Meta:
        indexes = [
            models.Index(fields=['title'], name='product_title_idx'),
            models.Index(fields=['rate'], name='product_rate_idx'),
        ]

class Rating(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_ratings')
    value = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'user')
        db_table = 'product_ratings'
        indexes = [
            models.Index(fields=['product'], name='rating_product_idx'),
        ]

    def __str__(self):
        return f"Rating {self.value} for product {self.product_id} by user {self.user_id}"

class ProductCategory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('product', 'category')
        db_table = 'product_categories'
        indexes = [
            models.Index(fields=['product', 'category'], name='prod_cat_combo_idx'),
        ]
