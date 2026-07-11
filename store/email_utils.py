import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def send_welcome_email(user):
    subject = "Welcome to Cladly ✨ — Here's a gift for you!"

    message = f"""
Hi {user.full_name},

Welcome to Cladly! 🎉

We're so excited to have you here. Cladly is your go-to destination
for premium fashion accessories — delivered to your campus and city Bhubaneswar, same day.

🎁 As a welcome gift, here's an exclusive coupon just for you:

        ╔══════════════════════╗
        ║   WELCOME50          ║
        ║   Flat ₹50 OFF       ║
        ╚══════════════════════╝

Use code  WELCOME50  on your first order and get ₹50 off!
Minimum order: ₹199 | Valid for 10 days

👉 Shop now: {settings.FRONTEND_URL}

With love,
The Cladly Team 🖤
——————————————————————————
Instagram: @cladly.in
"""

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,  # won't crash if email fails
    )


def send_welcome_back_email(user):
    subject = f"Welcome back, {user.full_name}! 👋"

    message = f"""
Hi {user.full_name},

Great to see you again! 😊

We've missed you at Cladly. Check out what's new —
fresh arrivals and exciting deals are waiting for you.

✨ New arrivals just dropped
🏷️ Use code  CLADLY10  for 10% off today
🚀 Same-day all campus and city delivery available in bhubaneswar

👉 Shop now: {settings.FRONTEND_URL}

See you soon,
The Cladly Team 🖤
——————————————————————————
Instagram: @cladly Fashion
"""

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )



def send_password_reset_email(user, reset_link):
    subject = "Reset your Cladly password 🔐"

    message = f"""
Hi {user.full_name},

We received a request to reset your Cladly account password.

Click the link below to reset your password:

👉 {reset_link}

⚠️  This link will expire in 30 minutes.

If you did NOT request a password reset, please ignore this email.
Your password will remain unchanged.

Stay safe,
The Cladly Team 🖤
——————————————————————————
Instagram: @cladly fashion
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send password reset email to %s", user.email)


def send_order_cancelled_email(user, order):
    subject = f"Order {order.order_id} Cancelled — Cladly"

    message = f"""
Hi {user.full_name},

Your order has been cancelled successfully.

Order ID   : {order.order_id}
Amount     : ₹{order.grand_total}
Cancelled  : {order.cancelled_at.strftime('%d %b %Y, %I:%M %p') if order.cancelled_at else 'Just now'}

If you paid online, refund will be processed in 5-7 business days.

Want to shop again?
👉 {settings.FRONTEND_URL}

The Cladly Team 🖤
"""

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )