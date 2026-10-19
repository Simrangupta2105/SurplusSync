import hashlib
import secrets
from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication, exceptions
from .models import POSApiKey


class POSApiKeyUser(AnonymousUser):
    def __init__(self, organization):
        super().__init__()
        self.organization = organization

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def __str__(self):
        return f"POSApiKeyUser({self.organization.name})"


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """
    Authenticates requests with header:
    Authorization: Api-Key <raw_key>
    """
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'api-key':
            return None

        raw_key = parts[1]
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        try:
            pos_key = POSApiKey.objects.select_related('organization').get(key_hash=key_hash, is_active=True)
        except POSApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid or inactive API key.')

        return (POSApiKeyUser(pos_key.organization), pos_key.organization)


def create_pos_key(organization, label: str) -> str:
    """
    Generates a cryptographically secure key prefixed with 'ss_',
    stores only the SHA-256 hash in POSApiKey, and returns the raw key once.
    """
    raw_key = "ss_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    POSApiKey.objects.create(
        organization=organization,
        label=label,
        key_hash=key_hash,
        is_active=True,
    )
    return raw_key
