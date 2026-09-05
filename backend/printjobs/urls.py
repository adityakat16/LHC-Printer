from django.urls import path
from . import views
from .views import csrf

urlpatterns = [
    path('uploads/presign/', views.presign_upload, name='presign_upload'),
    path('uploads/local/<str:token>/', views.local_upload, name='local_upload'),
    path('orders/', views.create_order, name='create_order'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('payments/razorpay/webhook/', views.razorpay_webhook, name='razorpay_webhook'),
    path('payments/razorpay/confirm/', views.razorpay_confirm, name='razorpay_confirm'),
    path('auth/user/', views.auth_user, name='auth_user'),
    path('auth/logout/', views.logout_user, name='logout_user'),
    path('devices/register/', views.device_register, name='device_register'),
    path('devices/<int:device_id>/jobs/', views.device_jobs, name='device_jobs'),
    path('devices/<int:device_id>/jobs/<int:job_id>/status/', views.job_update, name='job_update'),
    path("csrf/", csrf),
]
