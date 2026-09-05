from celery import shared_task
from .models import Order
import time

@shared_task
def process_order_async(order_id):
    # placeholder: parse PDF, generate thumbnail, count pages
    time.sleep(1)
    try:
        order = Order.objects.get(id=order_id)
        # For MVP, set pages to 1 if not parsed and leave price as-is
        # In production download S3 object and parse with PyPDF2
        return True
    except Order.DoesNotExist:
        return False
