from celery import shared_task
from .models import Order
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import os
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


@shared_task
def delete_expired_uploads():
    cutoff = timezone.now() - timedelta(hours=24)
    deleted = 0
    media_root = os.path.realpath(str(settings.MEDIA_ROOT))

    for order in Order.objects.filter(created_at__lt=cutoff).only('file_key'):
        if not order.file_key.startswith('local/'):
            continue
        path = os.path.realpath(os.path.join(media_root, order.file_key.split('/', 1)[1]))
        if os.path.commonpath([media_root, path]) != media_root:
            continue
        if os.path.isfile(path):
            os.remove(path)
            deleted += 1

    return deleted
