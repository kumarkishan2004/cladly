import razorpay
import hmac
import hashlib
from django.conf import settings


def get_razorpay_client():
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def create_razorpay_order(amount_in_rupees, order_id):
    """
    Create a Razorpay order.
    Amount must be in paise (multiply by 100).
    """
    client = get_razorpay_client()
    amount_in_paise = int(float(amount_in_rupees) * 100)

    razorpay_order = client.order.create({
        'amount': amount_in_paise,
        'currency': settings.RAZORPAY_CURRENCY,
        'receipt': str(order_id),
        'payment_capture': 1,  # auto capture
    })
    return razorpay_order


def verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify payment signature from Razorpay.
    Returns True if valid, False if tampered.
    """
    try:
        client = get_razorpay_client()
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
        return True
    except Exception:
        return False