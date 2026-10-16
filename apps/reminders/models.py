from django.db import models
from apps.core.models import TimeStampedModel, SoftDeleteModel


class Reminder(TimeStampedModel, SoftDeleteModel):
    """Reminder model for animals' due appointments, vaccinations, and medications."""

    class ReminderType(models.TextChoices):
        APPOINTMENT = "APPOINTMENT", "موعد"
        VACCINATION = "VACCINATION", "تطعيم"
        MEDICATION = "MEDICATION", "دواء / علاج"
        CHECKUP = "CHECKUP", "فحص دوري"
        FOLLOW_UP = "FOLLOW_UP", "متابعة حالة"
        GENERAL = "GENERAL", "تذكير عام / متابعة"

    class Status(models.TextChoices):
        PENDING = "PENDING", "معلق (Pending)"
        CONVERTED = "CONVERTED", "تم تحويله إلى موعد (Converted to appointment)"
        COMPLETED = "COMPLETED", "مكتمل (Completed)"
        CANCELLED = "CANCELLED", "ملغى (Cancelled)"

    animal = models.ForeignKey(
        "patients.Animal",
        on_delete=models.CASCADE,
        related_name="reminders",
        verbose_name="المريض (الحيوان)",
    )
    medical_record = models.ForeignKey(
        "clinical.MedicalRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminders",
        verbose_name="الزيارة السريرية المرتبطة (اختياري)",
    )
    reminder_type = models.CharField(
        max_length=30,
        choices=ReminderType.choices,
        default=ReminderType.CHECKUP,
        verbose_name="نوع التذكير",
    )
    due_date = models.DateField(db_index=True, verbose_name="تاريخ الاستحقاق")
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="حالة التذكير",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات / سبب التذكير")
    converted_appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_reminders",
        verbose_name="الموعد المحول إليه (اختياري)",
    )

    class Meta:
        verbose_name = "تذكير"
        verbose_name_plural = "التذكيرات"
        ordering = ["due_date"]
        indexes = [
            models.Index(fields=["animal", "status"]),
            models.Index(fields=["status", "due_date"]),
        ]

    def __str__(self):
        return f"تذكير {self.animal.name} - {self.get_reminder_type_display()} ({self.due_date})"

    @property
    def assigned_doctor(self):
        """Returns the doctor who created the clinical visit or administered the vaccination for this reminder, if any."""
        if self.medical_record_id and self.medical_record and self.medical_record.doctor:
            return self.medical_record.doctor
        try:
            vac = self.generated_from_vaccination.select_related("doctor").first()
            if vac and vac.doctor:
                return vac.doctor
        except Exception:
            pass
        return None

    def mark_as_converted(self, appointment):
        """Helper to mark reminder as converted to appointment."""
        self.status = self.Status.CONVERTED
        self.converted_appointment = appointment
        self.save(update_fields=["status", "converted_appointment", "updated_at"])

    def mark_as_completed(self):
        """Helper to mark reminder as completed."""
        self.status = self.Status.COMPLETED
        self.save(update_fields=["status", "updated_at"])
