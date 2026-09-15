import os
import uuid
from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def presign_upload(request):
    """Return a Django upload endpoint for the PDF."""
    requested_size = request.data.get('file_size')
    if requested_size is None:
        return Response({'error': 'file_size is required'}, status=400)
    try:
        requested_size = int(requested_size)
    except (TypeError, ValueError):
        return Response({'error': 'file_size must be an integer'}, status=400)
    if requested_size <= 0 or requested_size > settings.MAX_UPLOAD_SIZE_BYTES:
        return Response({'error': 'File size must not exceed 15 MB'}, status=400)

    token = str(uuid.uuid4())
    local_key = f"local/{token}.pdf"
    # Return a relative upload path for local fallback so frontend dev server proxy can route it
    upload_url = f"/api/uploads/local/{token}/"
    return Response({'upload_url': upload_url, 'file_key': local_key})

@csrf_exempt
@api_view(['PUT','POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def local_upload(request, token):
    """Accept raw PUT body or multipart POST and save to MEDIA_ROOT/local/<token>.pdf"""
    filename = f"local/{token}.pdf"
    dest = settings.MEDIA_ROOT / filename.split('/',1)[1]
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    try:
        # If multipart POST
        if request.FILES:
            fileobj = list(request.FILES.values())[0]
            if fileobj.size > settings.MAX_UPLOAD_SIZE_BYTES:
                return Response({'error': 'File size must not exceed 15 MB'}, status=400)
            with open(dest, 'wb') as f:
                for chunk in fileobj.chunks():
                    f.write(chunk)
        else:
            # Raw body from PUT
            if len(request.body) > settings.MAX_UPLOAD_SIZE_BYTES:
                return Response({'error': 'File size must not exceed 15 MB'}, status=400)
            with open(dest, 'wb') as f:
                f.write(request.body)
        return Response({'file_key': filename})
    except Exception as e:
        return Response({'error': str(e)}, status=500)
