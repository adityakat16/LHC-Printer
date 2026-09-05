from django.contrib import admin
from .models import Order, Device, PrintJob

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id','file_key','status','price_cents','created_at')

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('id','name','printer_name','last_seen')

@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ('id','order','device','status','created_at')
