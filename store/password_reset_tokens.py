import secrets
from django.core.cache import cache


def generate_reset_token(user_id):
    """Generate a secure token and store in cache for 30 minutes."""
    token = secrets.token_urlsafe(32)
    cache.set(f'password_reset_{token}', user_id, timeout=1800)  # 30 minutes
    return token


def verify_reset_token(token):
    """Returns user_id if token is valid, None if expired or invalid."""
    user_id = cache.get(f'password_reset_{token}')
    return user_id


def delete_reset_token(token):
    """Delete token after use so it cannot be reused."""
    cache.delete(f'password_reset_{token}')