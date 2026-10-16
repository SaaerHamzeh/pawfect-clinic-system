from django.contrib import admin
from .models import MedicalRecord, FileAttachment


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ["animal", "doctor", "record_type", "date_time", "weight_at_visit", "is_deleted"]
    search_fields = ["animal__name", "doctor__username", "diagnosis", "treatment", "symptoms"]
    list_filter = ["record_type", "date_time", "doctor", "is_deleted"]


@admin.register(FileAttachment)
class FileAttachmentAdmin(admin.ModelAdmin):
    list_display = ["file_name", "animal", "medical_record", "file_size", "file_type", "uploaded_by", "created_at"]
    search_fields = ["file_name", "animal__name", "uploaded_by__username"]
    list_filter = ["file_type", "created_at", "is_deleted"]
