import logging
import random
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_otp():
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))


def send_otp_email(user_email, user_name, otp, purpose='verify'):
    """Send OTP via email."""

    if purpose == 'register':
        subject = "Verify your Cladly account — OTP Inside 🔐"
        message = f"""
Hi {user_name},

Welcome to Cladly! 🎉

Your account verification OTP is:

        ╔══════════════════════╗
        ║                      ║
        ║      {otp}         ║
        ║                      ║
        ╚══════════════════════╝

⏱  This OTP expires in 10 minutes.
🔒 Do not share this OTP with anyone.

If you did not create a Cladly account, ignore this email.

The Cladly Team 🖤
"""
    else:  # login
        subject = "Your Cladly login OTP 🔐"
        message = f"""
Hi {user_name},

Your login verification OTP is:

        ╔══════════════════════╗
        ║                      ║
        ║      {otp}         ║
        ║                      ║
        ╚══════════════════════╝

⏱  This OTP expires in 10 minutes.
🔒 Do not share this OTP with anyone.

If you did not attempt to login, please reset your password immediately.

The Cladly Team 🖤
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send OTP email to %s", user_email)


def store_otp(identifier, otp, extra_data=None):
    """Store OTP in cache for 10 minutes."""
    data = {'otp': otp}
    if extra_data:
        data.update(extra_data)
    cache.set(f'otp_{identifier}', data, timeout=600)  # 10 minutes


def verify_otp(identifier, entered_otp):
    data = cache.get(f'otp_{identifier}')

    if not data:
        return None

    stored_otp = str(data.get('otp', '')).strip()
    entered_otp = str(entered_otp).strip()

    if stored_otp == entered_otp:
        # ── Immediately delete after correct match ──
        delete_otp(identifier)
        return data

    return None


def delete_otp(identifier):
    """Delete OTP after successful verification."""
    cache.delete(f'otp_{identifier}')


def increment_otp_attempts(identifier):
    """Track wrong attempts — block after 5 wrong tries."""
    key = f'otp_attempts_{identifier}'
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, timeout=600)
    return attempts


def get_otp_attempts(identifier):
    return cache.get(f'otp_attempts_{identifier}', 0)


def clear_otp_attempts(identifier):
    cache.delete(f'otp_attempts_{identifier}')