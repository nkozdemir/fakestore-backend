from django.db import models

class User(models.Model):
    id = models.IntegerField(primary_key=True)
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.CharField(max_length=150, unique=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)

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
