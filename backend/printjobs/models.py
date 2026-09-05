from django.db import models

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
        ('paid', 'Paid'),
        ('printed', 'Printed'),
        ('failed', 'Failed'),
    ]
    file_key = models.CharField(max_length=512)
    user_id = models.CharField(max_length=128, blank=True)
    pages_spec = models.CharField(max_length=128, default='all')
    color_mode = models.CharField(max_length=16, choices=[('bw', 'BlackWhite'), ('color', 'Color')], default='bw')
    price_cents = models.IntegerField(default=0)
    currency = models.CharField(max_length=8, default='INR')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending_payment')
    provider = models.CharField(max_length=64, blank=True)
    provider_payment_id = models.CharField(max_length=256, blank=True)
    webhook_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} ({self.status})"

class Device(models.Model):
    name = models.CharField(max_length=128)
    device_token = models.CharField(max_length=256)
    owner_user_id = models.CharField(max_length=128, blank=True)
    printer_name = models.CharField(max_length=256, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

class PrintJob(models.Model):
    STATUS = [
        ('queued', 'Queued'),
        ('downloading', 'Downloading'),
        ('printing', 'Printing'),
        ('done', 'Done'),
        ('error', 'Error'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='print_jobs')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='jobs')
    status = models.CharField(max_length=32, choices=STATUS, default='queued')
    attempts = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job {self.id} for Order {self.order_id} -> {self.device} ({self.status})"
