from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel

MAX_ATTACHMENT_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB limit per requirements


def validate_attachment_size(file):
    if file.size > MAX_ATTACHMENT_SIZE_BYTES:
        raise ValidationError(
            f"حجم الملف يتجاوز الحد الأقصى المسموح به (15 ميغابايت). الحجم الحالي: {file.size / (1024 * 1024):.2f} MB"
        )


class MedicalRecord(TimeStampedModel, SoftDeleteModel):
    """Medical Record model representing clinical visits and examinations."""

    class RecordType(models.TextChoices):
        VISIT = "VISIT", "زيارة سريرية عامة"
        CHECKUP = "CHECKUP", "فحص دوري"
        VACCINATION = "VACCINATION", "تطعيم ووقاية"
        SURGERY = "SURGERY", "إجراء جراحي"
        EMERGENCY = "EMERGENCY", "طوارئ"

    animal = models.ForeignKey(
        "patients.Animal",
        on_delete=models.CASCADE,
        related_name="medical_records",
        verbose_name="المريض (الحيوان)",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="medical_records_as_doctor",
        verbose_name="الطبيب البيطري المعالج",
    )
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medical_record",
        verbose_name="الموعد المرتبط (اختياري للزيارات المباشرة)",
    )
    record_type = models.CharField(
        max_length=30,
        choices=RecordType.choices,
        default=RecordType.VISIT,
        verbose_name="نوع السجل / الزيارة",
    )
    date_time = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="تاريخ ووقت الزيارة",
    )
    weight_at_visit = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="الوزن بالكيلوغرام أثناء الزيارة",
        verbose_name="الوزن عند الزيارة (كغ)",
    )
    symptoms = models.TextField(blank=True, verbose_name="الأعراض المشكو منها (Symptoms)")
    diagnosis = models.TextField(blank=True, verbose_name="التشخيص (Diagnosis)")
    treatment = models.TextField(blank=True, verbose_name="العلاج الموصوف والإجراءات (Treatment)")
    medication = models.TextField(blank=True, verbose_name="الأدوية المعطاة (Medication)")
    prescription = models.TextField(blank=True, verbose_name="الوصفة الطبية المنزلية (Prescription)")
    follow_up = models.TextField(blank=True, verbose_name="خطة المتابعة ومواعيد المراجعة (Follow-up)")
    notes = models.TextField(blank=True, verbose_name="ملاحظات سريرية إضافية")

    # Direct Vaccination Integration fields
    vaccine_name = models.CharField(max_length=255, blank=True, verbose_name="اسم اللقاح / التطعيم")
    next_vaccine_name = models.CharField(max_length=255, blank=True, verbose_name="اسم التطعيم اللاحق المستحق")
    next_vaccination_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الجرعة القادمة المستحقة")
    batch_number = models.CharField(max_length=100, blank=True, verbose_name="رقم التشغيلة (Batch No.)")

    class Meta:
        verbose_name = "سجل طبي / زيارة سريرية"
        verbose_name_plural = "السجلات والزيارات السريرية"
        ordering = ["-date_time"]
        indexes = [
            models.Index(fields=["animal", "-date_time"]),
            models.Index(fields=["doctor", "-date_time"]),
        ]

    def __str__(self):
        return f"سجل {self.animal.name} في {self.date_time.strftime('%Y-%m-%d')} - د. {self.doctor.get_full_name() or self.doctor.username}"

    def clean(self):
        super().clean()
        # Mandatory validation: If visit is of type VACCINATION or vaccine_name is entered, next_vaccination_date is mandatory
        if self.record_type == self.RecordType.VACCINATION:
            if not self.next_vaccination_date:
                raise ValidationError({
                    "next_vaccination_date": "تاريخ الجرعة القادمة المستحقة إلزامي لزيارات التطعيم."
                })
            visit_date = self.date_time.date() if self.date_time else timezone.localdate()
            if self.next_vaccination_date <= visit_date:
                raise ValidationError({
                    "next_vaccination_date": "تاريخ الجرعة القادمة المستحقة يجب أن يكون بعد تاريخ إعطاء اللقاح."
                })

        # Validate linked appointment matches animal and doctor, and is active
        if self.appointment_id:
            from apps.appointments.models import Appointment
            appt = self.appointment
            if self.animal_id and appt.animal_id != self.animal_id:
                raise ValidationError({
                    "appointment": f"الموعد المحدد يخص مريضاً آخر ({appt.animal.name}) ولا يطابق هذا المريض ({self.animal.name})."
                })
            if self.doctor_id and appt.doctor_id != self.doctor_id:
                doc_name = appt.doctor.get_full_name() or appt.doctor.username
                raise ValidationError({
                    "appointment": f"الموعد المحدد مسجل لطبيب آخر ({doc_name}) ولا يطابق الطبيب المعالج للزيارة."
                })
            if appt.status == Appointment.Status.CANCELLED or appt.is_deleted:
                raise ValidationError({
                    "appointment": "لا يمكن ربط زيارة سريرية بموعد ملغى أو محذوف."
                })

            # Prevent linking future appointments to a current/past visit
            visit_date = self.date_time.date() if self.date_time else timezone.localdate()
            if appt.date > visit_date:
                raise ValidationError({
                    "appointment": f"لا يمكن ربط الزيارة بموعد مستقبلي بتاريخ ({appt.date}). إذا حضر المريض كزيارة مباشرة (Walk-in) قبل موعده، يرجى تسجيل الزيارة بدون تحديد موعد، وإضافة تذكير يدوي للاستقبال إن لزم تعديل الموعد المستقبلي."
                })

        if self.weight_at_visit is not None and self.weight_at_visit <= 0:
            raise ValidationError({
                "weight_at_visit": "الوزن المسجل عند الزيارة يجب أن يكون قيمة رقمية موجبة أكبر من الصفر."
            })

    def save(self, *args, **kwargs):
        if self.weight_at_visit is not None:
            from decimal import Decimal, ROUND_HALF_UP
            self.weight_at_visit = Decimal(str(self.weight_at_visit)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.full_clean()
        super().save(*args, **kwargs)


class VisitService(TimeStampedModel):
    """Service item performed during a clinical visit (e.g. Treatment, Injection, Nail Trimming, Bath, etc.)."""

    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="الزيارة السريرية المرتبطة",
    )
    name = models.CharField(max_length=150, verbose_name="اسم الخدمة / الإجراء")
    notes = models.TextField(blank=True, verbose_name="تفاصيل أو ملاحظات الخدمة")

    class Meta:
        verbose_name = "خدمة سريرية"
        verbose_name_plural = "الخدمات السريرية"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.name} ({self.medical_record})"


class FileAttachment(TimeStampedModel, SoftDeleteModel):
    """File Attachment model attached to Animal or MedicalRecord with max 15MB size."""

    animal = models.ForeignKey(
        "patients.Animal",
        on_delete=models.CASCADE,
        related_name="file_attachments",
        verbose_name="المريض (الحيوان)",
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
        verbose_name="السجل الطبي المرتبط (اختياري)",
    )
    file = models.FileField(
        upload_to="clinical/attachments/%Y/%m/",
        validators=[validate_attachment_size],
        verbose_name="الملف المرفق",
    )
    file_name = models.CharField(max_length=255, verbose_name="اسم الملف الأصلي")
    file_size = models.PositiveIntegerField(help_text="حجم الملف بالبايت", verbose_name="حجم الملف (Bytes)")
    file_type = models.CharField(max_length=100, blank=True, verbose_name="نوع الملف / الصيغة")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_attachments",
        verbose_name="المستخدم الرافع للملف",
    )

    class Meta:
        verbose_name = "مرفق طبي"
        verbose_name_plural = "المرفقات الطبية"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["animal", "is_deleted"]),
            models.Index(fields=["medical_record", "is_deleted"]),
        ]

    def __str__(self):
        return f"{self.file_name} ({self.file_size_display}) - {self.animal.name}"

    @property
    def file_size_display(self):
        if not self.file_size:
            return "0 B"
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.2f} MB"

    @property
    def is_image(self):
        ext = (self.file_name or (self.file.name if self.file else "")).split(".")[-1].lower()
        return ext in ["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"] or (bool(self.file_type) and self.file_type.startswith("image/"))

    @property
    def is_pdf(self):
        ext = (self.file_name or (self.file.name if self.file else "")).split(".")[-1].lower()
        return ext == "pdf" or self.file_type == "application/pdf"

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        if self.file and not self.file_name:
            self.file_name = self.file.name.split("/")[-1]
        super().save(*args, **kwargs)


class VaccinationRecord(TimeStampedModel, SoftDeleteModel):
    """Vaccination record documenting administered vaccines and generating future reminders."""

    animal = models.ForeignKey(
        "patients.Animal",
        on_delete=models.CASCADE,
        related_name="vaccination_records",
        verbose_name="المريض (الحيوان)",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vaccinations_administered",
        verbose_name="الطبيب المشرف على التطعيم",
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="vaccination_records",
        verbose_name="الزيارة السريرية المرتبطة",
    )
    vaccine_name = models.CharField(max_length=255, verbose_name="اسم اللقاح / التطعيم")
    next_vaccine_name = models.CharField(max_length=255, blank=True, verbose_name="اسم التطعيم اللاحق المستحق")
    date_administered = models.DateField(default=timezone.localdate, verbose_name="تاريخ إعطاء اللقاح")
    next_due_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الجرعة القادمة المستحقة")
    batch_number = models.CharField(max_length=100, blank=True, verbose_name="رقم التشغيلة (Batch/Lot No.)")
    notes = models.TextField(blank=True, verbose_name="ملاحظات التطعيم")
    reminder = models.ForeignKey(
        "reminders.Reminder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_from_vaccination",
        verbose_name="التذكير الآلي المولد للجرعة القادمة",
    )

    class Meta:
        verbose_name = "سجل تطعيم"
        verbose_name_plural = "سجلات التطعيمات"
        ordering = ["-date_administered"]
        indexes = [
            models.Index(fields=["animal", "-date_administered"]),
            models.Index(fields=["next_due_date"]),
        ]

    def clean(self):
        super().clean()
        if self.next_due_date and self.date_administered:
            if self.next_due_date <= self.date_administered:
                raise ValidationError({
                    "next_due_date": "تاريخ الجرعة القادمة المستحقة يجب أن يكون بعد تاريخ إعطاء اللقاح."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"تطعيم {self.vaccine_name} لـ {self.animal.name} في {self.date_administered}"
