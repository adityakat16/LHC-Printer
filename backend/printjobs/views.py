import os
import io
import os.path
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from .models import Order, Device, PrintJob
from .serializers import OrderSerializer, CreateOrderSerializer, DeviceSerializer, PrintJobSerializer
from .razorpay_utils import create_razorpay_order, verify_payment_signature, verify_webhook_signature, fetch_order, fetch_payment
from django.shortcuts import get_object_or_404
from celery import shared_task
import boto3
from botocore.exceptions import ClientError
import uuid
from .tasks import process_order_async
from PyPDF2 import PdfReader
from .views_uploads import presign_upload


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return



@api_view(['PUT','POST'])
def local_upload(request, token):
    from .views_uploads import local_upload as local_impl
    return local_impl(request, token)

@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"detail": "CSRF cookie set"})

@csrf_exempt
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def create_order(request):
    s = CreateOrderSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data
    file_key = data['file_key']

    # Load file bytes from S3 or local storage
    file_bytes = None
    if settings.AWS_S3_BUCKET and file_key and not file_key.startswith('local/'):
        s3 = boto3.client('s3', aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, region_name=settings.AWS_S3_REGION)
        try:
            obj = s3.get_object(Bucket=settings.AWS_S3_BUCKET, Key=file_key)
            file_bytes = obj['Body'].read()
        except Exception as e:
            return Response({'error': f'Failed to fetch from S3: {str(e)}'}, status=500)
    else:
        # local storage
        if file_key and file_key.startswith('local/'):
            rel = file_key.split('/',1)[1]
            path = settings.MEDIA_ROOT / rel
            if path.exists():
                with open(path, 'rb') as f:
                    file_bytes = f.read()
            else:
                return Response({'error':'local file not found', 'file_key': file_key}, status=400)

    # Parse PDF for page count
    pages = 1
    try:
        if file_bytes:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = len(reader.pages)
    except Exception:
        # fallback to 1 page
        pages = 1

    # Pricing is per page with no base charge.
    price_per_page = (
        settings.PRINT_PRICE_COLOR_PAISE
        if data['color_mode'] == 'color'
        else settings.PRINT_PRICE_BW_PAISE
    )
    price = price_per_page * pages

    order = Order.objects.create(
        file_key=file_key,
        pages_spec=data.get('pages_spec', 'all'),
        color_mode=data['color_mode'],
        user_id=str(request.user.id),
        price_cents=price,
    )

    # Optionally kick background tasks for thumbnails
    process_order_async.delay(order.id)

    # Initiate Razorpay order to get order_id for client-side Checkout
    razorpay_key_id = os.getenv('RAZORPAY_KEY_ID','')
    razorpay_key_secret = os.getenv('RAZORPAY_KEY_SECRET','')
    try:
        # price is stored in paise/cents in this codebase (e.g., 1400 == Rs.14.00)
        rp_order = create_razorpay_order(price, str(order.id), razorpay_key_id, razorpay_key_secret)
        pay_info = {'razorpay': {'order_id': rp_order.get('id'), 'amount': rp_order.get('amount'), 'currency': rp_order.get('currency'), 'key_id': razorpay_key_id}}
    except Exception as e:
        pay_info = {'error': str(e)}
    return Response({'order': OrderSerializer(order).data, 'pay_info': pay_info})


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def razorpay_confirm(request):
    """Confirm payment after client-side Checkout (verifies signature and amount)."""
    data = request.data
    order_id = data.get('order_id')
    payment_id = data.get('razorpay_payment_id')
    rp_order_id = data.get('razorpay_order_id')
    signature = data.get('razorpay_signature')
    if not order_id or not payment_id or not rp_order_id or not signature:
        return Response({'error':'missing params'}, status=400)
    order = get_object_or_404(Order, id=order_id)
    razorpay_key_id = os.getenv('RAZORPAY_KEY_ID','')
    razorpay_key_secret = os.getenv('RAZORPAY_KEY_SECRET','')

    ok = verify_payment_signature(rp_order_id, payment_id, signature, razorpay_key_secret)
    if not ok:
        order.webhook_payload = data
        order.save()
        return Response({'error':'invalid signature'}, status=400)

    # Optionally verify amount by fetching payment
    try:
        payment = fetch_payment(payment_id, razorpay_key_id, razorpay_key_secret)
        paid_amount = payment.get('amount')
        expected = order.price_cents
        if paid_amount is not None and int(paid_amount) != int(expected):
            order.webhook_payload = {'payment': payment}
            order.save()
            return Response({'error':'amount_mismatch','expected':expected,'got':paid_amount}, status=400)
    except Exception:
        # best-effort; continue to mark paid if signature verified
        pass

    order.status = 'paid'
    order.provider = 'razorpay'
    order.provider_payment_id = payment_id
    order.webhook_payload = data
    order.save()

    device = Device.objects.first()
    if device:
        PrintJob.objects.create(order=order, device=device, status='queued')
    # return updated order for frontend convenience
    return Response({'status':'ok', 'order': OrderSerializer(order).data})


@csrf_exempt
@api_view(['POST'])
def razorpay_webhook(request):
    """Razorpay webhook handler. Verifies webhook signature and marks order paid.
    Expects the Razorpay webhook body structure. Uses RAZORPAY_WEBHOOK_SECRET for verification.
    """
    raw_body = request.body
    signature = request.headers.get('X-Razorpay-Signature','')
    webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET','')
    ok = False
    try:
        if webhook_secret:
            ok = verify_webhook_signature(raw_body, signature, webhook_secret)
        else:
            # If no webhook secret configured, do not verify and treat as unverified
            ok = True
    except Exception:
        ok = False

    payload = request.data
    if not ok:
        # record payload for diagnosis
        # try to attach to any order if present
        try:
            Order.objects.create(webhook_payload=payload)
        except Exception:
            pass
        return Response({'error':'invalid signature'}, status=400)

    # extract payment entity if present
    payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
    rp_payment_id = payment_entity.get('id')
    rp_order_id = payment_entity.get('order_id')
    amount = payment_entity.get('amount')

    # try to locate our order via receipt in razorpay order
    razorpay_key_id = os.getenv('RAZORPAY_KEY_ID','')
    razorpay_key_secret = os.getenv('RAZORPAY_KEY_SECRET','')
    our_order = None
    if rp_order_id:
        try:
            rp_order_obj = fetch_order(rp_order_id, razorpay_key_id, razorpay_key_secret)
            receipt = rp_order_obj.get('receipt')
            if receipt:
                try:
                    our_order = Order.objects.get(id=int(receipt))
                except Exception:
                    our_order = None
        except Exception:
            our_order = None

    if not our_order and rp_payment_id:
        our_order = Order.objects.filter(provider_payment_id=rp_payment_id).first()

    if not our_order:
        return Response({'error':'order not found'}, status=400)

    expected = our_order.price_cents
    if amount is not None and int(amount) != int(expected):
        our_order.webhook_payload = payload
        our_order.save()
        return Response({'error':'amount mismatch','expected':expected,'got':amount}, status=400)

    our_order.status = 'paid'
    our_order.provider = 'razorpay'
    our_order.provider_payment_id = rp_payment_id or ''
    our_order.webhook_payload = payload
    our_order.save()

    device = Device.objects.first()
    if device:
        PrintJob.objects.create(order=our_order, device=device, status='queued')
    return Response({'status':'ok'})


@api_view(['GET'])
def auth_user(request):
    if not request.user.is_authenticated:
        return Response({'authenticated': False})
    return Response({
        'authenticated': True,
        'id': request.user.id,
        'email': request.user.email,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'full_name': request.user.get_full_name(),
    })


@csrf_exempt
@api_view(['POST'])
def logout_user(request):
    logout(request)
    return Response({'logged_out': True})


@api_view(['GET'])
def device_register(request):
    # For MVP: create a device record and return token
    name = request.query_params.get('name','local-agent')
    token = str(uuid.uuid4())
    device = Device.objects.create(name=name, device_token=token)
    return Response(DeviceSerializer(device).data)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def order_history(request):
    orders = Order.objects.filter(user_id=str(request.user.id)).order_by('-created_at')
    return Response(OrderSerializer(orders, many=True).data)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user_id=str(request.user.id))
    return Response(OrderSerializer(order).data)


@api_view(['GET'])
def device_jobs(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    jobs = PrintJob.objects.filter(device=device, status='queued')
    return Response(PrintJobSerializer(jobs, many=True).data)


@api_view(['POST'])
def job_update(request, device_id, job_id):
    device = get_object_or_404(Device, id=device_id)
    job = get_object_or_404(PrintJob, id=job_id, device=device)
    status_ = request.data.get('status')
    job.status = status_
    job.attempts = request.data.get('attempts', job.attempts)
    job.last_error = request.data.get('last_error','')
    job.save()
    return Response(PrintJobSerializer(job).data)
