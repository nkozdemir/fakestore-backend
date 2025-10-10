from __future__ import annotations

from typing import Dict, Any, Optional

from django.contrib.auth.hashers import make_password

from .protocols import UserRegistrationRepositoryProtocol


class RegistrationService:
    def __init__(self, users: UserRegistrationRepositoryProtocol):
        self.users = users

    def _build_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            'username': data['username'].strip(),
            'email': data['email'].strip(),
            'password': make_password(data['password']),
        }
        optional = {
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
        }
        payload.update(optional)
        if self.users.supports_field('firstname'):
            payload['firstname'] = optional['first_name']
        if self.users.supports_field('lastname'):
            payload['lastname'] = optional['last_name']
        return payload

    def _check_uniqueness(self, username: str, email: str) -> Optional[tuple]:
        if self.users.username_exists(username):
            return ('VALIDATION_ERROR', 'Username already exists', {'username': username})
        if self.users.email_exists(email):
            return ('VALIDATION_ERROR', 'Email already exists', {'email': email})
        return None

    def register(self, data: Dict[str, Any]):
        username = data['username'].strip()
        email = data['email'].strip()
        conflict = self._check_uniqueness(username, email)
        if conflict:
            return conflict
        payload = self._build_payload(data)
        password = payload.pop('password')
        user = self.users.create_user(password=password, **payload)
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }
