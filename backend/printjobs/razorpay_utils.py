import os
import razorpay


def create_razorpay_order(amount_paise: int, receipt: str, key_id: str, key_secret: str):
    """
    Create a Razorpay Order. amount_paise should be integer (e.g., 1400 for Rs.14.00).
    Returns the raw order dict from Razorpay.
    """
    client = razorpay.Client(auth=(key_id, key_secret))
    payload = {
        'amount': int(amount_paise),
        'currency': 'INR',
        'receipt': str(receipt),
        'payment_capture': 1,
    }
    order = client.order.create(payload)
    return order


def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str, key_secret: str) -> bool:
    """
    Verify the signature returned to client after a checkout. Returns True if valid.
    """
    client = razorpay.Client(auth=("", key_secret))
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
        return True
    except Exception:
        return False


def verify_webhook_signature(body: bytes, signature: str, webhook_secret: str) -> bool:
    client = razorpay.Client(auth=("", webhook_secret))
    try:
        client.utility.verify_webhook_signature(body, signature, webhook_secret)
        return True
    except Exception:
        return False


def fetch_order(razorpay_order_id: str, key_id: str, key_secret: str) -> dict:
    client = razorpay.Client(auth=(key_id, key_secret))
    return client.order.fetch(razorpay_order_id)


def fetch_payment(razorpay_payment_id: str, key_id: str, key_secret: str) -> dict:
    client = razorpay.Client(auth=(key_id, key_secret))
    return client.payment.fetch(razorpay_payment_id)


def create_payment_link(amount_paise: int, description: str, key_id: str, key_secret: str, callback_url: str = None) -> dict:
    """
    Create a Razorpay Payment Link. Returns the raw payment link dict.
    amount_paise: integer amount in paise (e.g., 1400)
    description: description for the link (receipt/order info)
    callback_url: optional callback when payment completes
    """
    client = razorpay.Client(auth=(key_id, key_secret))
    payload = {
        'amount': int(amount_paise),
        'currency': 'INR',
        'description': description,
        'reference_id': description,
        'callback_method': 'get',
    }
    if callback_url:
        payload['callback_url'] = callback_url
    # minimal customer object; you can extend with email/phone
    payload['customer'] = {'name': 'Customer', 'contact': ''}
    link = client.payment_link.create(payload)
    return link
