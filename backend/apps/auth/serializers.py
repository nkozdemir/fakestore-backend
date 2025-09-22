from rest_framework import serializers


class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class RegisterResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()


class MeResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    firstname = serializers.CharField(allow_blank=True)
    lastname = serializers.CharField(allow_blank=True)
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
