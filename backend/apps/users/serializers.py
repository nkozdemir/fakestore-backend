from rest_framework import serializers
from .dtos import UserDTO, AddressDTO

class AddressSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    street = serializers.CharField()
    number = serializers.IntegerField()
    city = serializers.CharField()
    zipcode = serializers.CharField()
    latitude = serializers.CharField()
    longitude = serializers.CharField()

class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    firstname = serializers.CharField()
    lastname = serializers.CharField()
    email = serializers.CharField()
    username = serializers.CharField()
    phone = serializers.CharField()
    addresses = AddressSerializer(many=True)
