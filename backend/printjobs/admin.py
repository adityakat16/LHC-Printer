from django.contrib import admin
from .models import Order, Device, PrintJob

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id','file_key','status','price_cents','created_at')
    actions = ('retry_print_jobs',)

    @admin.action(description='Retry failed print jobs for selected orders')
    def retry_print_jobs(self, request, queryset):
        count = PrintJob.objects.filter(order__in=queryset, status='error').update(
            status='queued',
            last_error='',
        )
        self.message_user(request, f'{count} print job(s) requeued for retry.')

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('id','name','printer_name','last_seen')

@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ('id','order','device','status','attempts','last_error','created_at')
    list_filter = ('status', 'device')
    search_fields = ('order__id', 'order__provider_payment_id', 'last_error')
    actions = ('retry_print_jobs',)

    @admin.action(description='Retry selected print jobs')
    def retry_print_jobs(self, request, queryset):
        retryable = queryset.filter(status='error')
        count = retryable.update(status='queued', last_error='')
        self.message_user(request, f'{count} print job(s) requeued for retry.')
