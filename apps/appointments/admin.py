from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["animal", "doctor", "date", "time", "duration", "status", "appointment_type", "is_deleted"]
    search_fields = ["animal__name", "doctor__username", "doctor__first_name", "doctor__last_name", "brought_by"]
    list_filter = ["status", "appointment_type", "date", "doctor", "is_deleted"]
