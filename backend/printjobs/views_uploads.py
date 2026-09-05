import os
import uuid
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from botocore.exceptions import ClientError
import boto3
from botocore.config import Config

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def presign_upload(request):
    """Return an upload URL for S3 if configured; otherwise return a local upload endpoint URL.
    The frontend will PUT the file bytes to the returned upload_url.
    """
    bucket = settings.AWS_S3_BUCKET
    key = f"uploads/{uuid.uuid4()}.pdf"
    if bucket and settings.AWS_ACCESS_KEY_ID:
        s3 = boto3.client('s3', aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, region_name=settings.AWS_S3_REGION,config=Config(signature_version='s3v4'))
        try:
            url = s3.generate_presigned_url('put_object', Params={'Bucket': bucket, 'Key': key,'ContentType': 'application/pdf',}, ExpiresIn=3600)
            return Response({'upload_url': url, 'file_key': key})
        except ClientError as e:
            return Response({'error': str(e)}, status=500)
    # fallback to local upload endpoint
    token = str(uuid.uuid4())
    local_key = f"local/{token}.pdf"
    # Return a relative upload path for local fallback so frontend dev server proxy can route it
    upload_url = f"/api/uploads/local/{token}/"
    return Response({'upload_url': upload_url, 'file_key': local_key})

@csrf_exempt
@api_view(['PUT','POST'])
@permission_classes([IsAuthenticated])
def local_upload(request, token):
    """Accept raw PUT body or multipart POST and save to MEDIA_ROOT/local/<token>.pdf"""
    filename = f"local/{token}.pdf"
    dest = settings.MEDIA_ROOT / filename.split('/',1)[1]
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    try:
        # If multipart POST
        if request.FILES:
            fileobj = list(request.FILES.values())[0]
            with open(dest, 'wb') as f:
                for chunk in fileobj.chunks():
                    f.write(chunk)
        else:
            # Raw body from PUT
            with open(dest, 'wb') as f:
                f.write(request.body)
        return Response({'file_key': filename})
    except Exception as e:
        return Response({'error': str(e)}, status=500)
