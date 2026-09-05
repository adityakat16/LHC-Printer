from rest_framework import serializers
from .models import Order, Device, PrintJob

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'

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
    class Meta:
        model = PrintJob
        fields = '__all__'
