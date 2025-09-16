from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    id = models.IntegerField(primary_key=True)  # keep original ids
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    image = models.TextField()
    rate = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    count = models.IntegerField(default=0)
    categories = models.ManyToManyField(Category, related_name='products', through='ProductCategory')

    def __str__(self):
        return self.title

class ProductCategory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('product', 'category')
        db_table = 'product_categories'
