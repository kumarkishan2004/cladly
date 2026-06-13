from django.core.mail import send_mail
from django.conf import settings


def send_welcome_email(user):
    subject = "Welcome to Cladly ✨ — Here's a gift for you!"

    message = f"""
Hi {user.full_name},

Welcome to Cladly! 🎉

We're so excited to have you here. Cladly is your go-to destination
for premium fashion accessories — delivered to your campus, same day.

🎁 As a welcome gift, here's an exclusive coupon just for you:

        ╔══════════════════════╗
        ║   WELCOME50          ║
        ║   Flat ₹50 OFF       ║
        ╚══════════════════════╝

Use code  WELCOME50  on your first order and get ₹50 off!
Minimum order: ₹299 | Valid for 30 days

👉 Shop now: http://cladly.in

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
🚀 Same-day campus delivery available

👉 Shop now: http://cladly.in

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