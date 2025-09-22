from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # id, username, email, password, is_active, is_staff, is_superuser, groups, user_permissions are inherited
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, blank=True, null=True)
    # Ensure email uniqueness across users
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    street = models.CharField(max_length=150)
    number = models.IntegerField()
    city = models.CharField(max_length=100)
    zipcode = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)

    def __str__(self):
        return f"{self.street} {self.number}, {self.city}"
