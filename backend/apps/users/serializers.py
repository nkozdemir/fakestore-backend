from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .dtos import UserDTO, AddressDTO
from .models import User

class AddressSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    street = serializers.CharField()
    number = serializers.IntegerField()
    city = serializers.CharField()
    zipcode = serializers.CharField()
    latitude = serializers.CharField()
    longitude = serializers.CharField()


class GeoSerializer(serializers.Serializer):
    lat = serializers.CharField()
    long = serializers.CharField()


class AddressWriteSerializer(serializers.Serializer):
    city = serializers.CharField()
    street = serializers.CharField()
    number = serializers.IntegerField()
    zipcode = serializers.CharField()
    geolocation = GeoSerializer()

class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    # For responses
    name = serializers.SerializerMethodField(read_only=True)
    email = serializers.EmailField(validators=[UniqueValidator(queryset=User.objects.all())])
    username = serializers.CharField(validators=[UniqueValidator(queryset=User.objects.all())])
    phone = serializers.CharField()
    addresses = AddressSerializer(many=True, read_only=True)
    # For writes
    firstname = serializers.CharField(write_only=True, required=False)
    lastname = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False)
    address = AddressWriteSerializer(write_only=True, required=False)
    # New write shape: name { firstname, lastname }
    class _Name(serializers.Serializer):
        firstname = serializers.CharField()
        lastname = serializers.CharField()
    name = _Name(write_only=True, required=False)

    def get_name(self, obj: UserDTO):
        return {
            'firstname': obj.firstname,
            'lastname': obj.lastname,
        }

    def validate(self, attrs):
        # Map nested name -> firstname/lastname if provided
        name = attrs.pop('name', None)
        if name:
            attrs['firstname'] = name.get('firstname')
            attrs['lastname'] = name.get('lastname')
        # Ensure we have firstname/lastname by one of the inputs when creating/updating
        # Leave detailed enforcement to service or model constraints if any
        return super().validate(attrs)
