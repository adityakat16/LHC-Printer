from rest_framework import serializers
from .models import Order, Device, PrintJob

class OrderSerializer(serializers.ModelSerializer):
    print_status = serializers.SerializerMethodField()
    print_error = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'

    def get_print_status(self, order):
        job = order.print_jobs.order_by('-created_at').first()
        return job.status if job else None

    def get_print_error(self, order):
        job = order.print_jobs.order_by('-created_at').first()
        return job.last_error if job else ''

class CreateOrderSerializer(serializers.Serializer):
    file_key = serializers.CharField()
    pages_spec = serializers.CharField(default='all')
    color_mode = serializers.ChoiceField(choices=['bw','color'], default='bw')
    user_id = serializers.CharField(required=False, allow_blank=True)

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'

class PrintJobSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)

    class Meta:
        model = PrintJob
        fields = '__all__'
