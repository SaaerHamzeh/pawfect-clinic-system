import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel


class Appointment(TimeStampedModel, SoftDeleteModel):
    """Appointment model for scheduled clinic visits."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "مجدول (Scheduled)"
        COMPLETED = "COMPLETED", "مكتمل (Completed)"
        CANCELLED = "CANCELLED", "ملغى (Cancelled)"
        NO_SHOW = "NO_SHOW", "لم يحضر (No-show)"

    class AppointmentType(models.TextChoices):
        CHECKUP = "CHECKUP", "فحص دوري / استشارة"
        TREATMENT = "TREATMENT", "علاج / متابعة"
        VACCINATION = "VACCINATION", "تطعيم"
        BATH = "BATH", "حمام وتجفيف / Bath"
        GROOMING = "GROOMING", "عناية وتنظيف / Grooming"
        SURGERY = "SURGERY", "إجراء جراحي / Surgery"
        EMERGENCY = "EMERGENCY", "حالة طارئة"

    class Duration(models.IntegerChoices):
        MIN_15 = 15, "15 دقيقة"
        MIN_30 = 30, "30 دقيقة"
        MIN_45 = 45, "45 دقيقة"
        MIN_60 = 60, "60 دقيقة"
        MIN_90 = 90, "90 دقيقة"

    CLINIC_OPENING_TIME = datetime.time(9, 0)
    CLINIC_CLOSING_TIME = datetime.time(22, 0)

    animal = models.ForeignKey(
        "patients.Animal",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name="المريض (الحيوان)",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments_as_doctor",
        verbose_name="الطبيب البيطري المعالج",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_appointments",
        verbose_name="الموظف المنشئ",
    )
    date = models.DateField(db_index=True, verbose_name="تاريخ الموعد")
    time = models.TimeField(verbose_name="وقت الموعد")
    duration = models.PositiveIntegerField(
        choices=Duration.choices,
        default=Duration.MIN_30,
        verbose_name="مدة الموعد (بالدقائق)",
    )
    appointment_type = models.CharField(
        max_length=30,
        choices=AppointmentType.choices,
        default=AppointmentType.CHECKUP,
        verbose_name="نوع الموعد",
    )
    vaccine_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="نوع التطعيم / اللقاح",
        help_text="اسم اللقاح المطلوب إعطاؤه في موعد التطعيم",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
        verbose_name="حالة الموعد",
    )
    brought_by = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="الشخص المُحضر للحيوان",
        help_text="اسم المرافق في الزيارة إذا لم يكن المالك الدائم",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات الموعد")

    class Meta:
        verbose_name = "موعد"
        verbose_name_plural = "المواعيد"
        ordering = ["date", "time"]
        indexes = [
            models.Index(fields=["doctor", "date", "time"]),
            models.Index(fields=["status", "date"]),
            models.Index(fields=["animal", "date"]),
        ]

    def __str__(self):
        return f"موعد {self.animal.name} مع د. {self.doctor.get_full_name() or self.doctor.username} في {self.date} {self.time}"

    @property
    def start_datetime(self):
        return datetime.datetime.combine(self.date, self.time)

    @property
    def end_datetime(self):
        return self.start_datetime + datetime.timedelta(minutes=self.duration)

    @property
    def is_due_now(self):
        """Returns True if appointment is currently happening today (between start and end time)."""
        if self.status != self.Status.SCHEDULED or self.is_deleted:
            return False
        now = timezone.localtime(timezone.now())
        if self.date != now.date():
            return False
        start = self.time
        end = (datetime.datetime.combine(self.date, self.time) + datetime.timedelta(minutes=self.duration)).time()
        return start <= now.time() <= end

    @property
    def is_overdue(self):
        """Returns True if appointment was scheduled for today or past and its time has already passed while still SCHEDULED."""
        if self.status != self.Status.SCHEDULED or self.is_deleted:
            return False
        now = timezone.localtime(timezone.now())
        if self.date < now.date():
            return True
        if self.date == now.date():
            end = (datetime.datetime.combine(self.date, self.time) + datetime.timedelta(minutes=self.duration)).time()
            return now.time() > end
        return False

    @property
    def time_status(self):
        if self.is_due_now:
            return "DUE_NOW"
        if self.is_overdue:
            return "OVERDUE"
        return "UPCOMING"

    def clean(self):
        super().clean()
        if not self.date or not self.time:
            return

        # Working hours validation: Appointments must fall strictly within clinic operating hours (09:00 - 22:00)
        start_time = self.time
        duration_mins = self.duration or self.Duration.MIN_30
        end_dt = self.start_datetime + datetime.timedelta(minutes=duration_mins)

        if (
            start_time < self.CLINIC_OPENING_TIME
            or end_dt.date() != self.date
            or end_dt.time() > self.CLINIC_CLOSING_TIME
        ):
            raise ValidationError(
                f"لا يمكن حجز موعد خارج أوقات دوام العيادة. "
                f"أوقات الدوام الرسمية من الساعة {self.CLINIC_OPENING_TIME.strftime('%H:%M')} صباحاً "
                f"حتى {self.CLINIC_CLOSING_TIME.strftime('%H:%M')} مساءً."
            )

        if not self.doctor_id:
            return

        # Conflict prevention rules
        if self.status != self.Status.CANCELLED and not self.is_deleted:
            start = self.start_datetime
            end = self.end_datetime

            # Rule A: Two BATH appointments must never overlap in time, regardless of doctor
            if self.appointment_type == self.AppointmentType.BATH:
                bath_overlapping = Appointment.objects.filter(
                    date=self.date,
                    appointment_type=self.AppointmentType.BATH,
                    is_deleted=False,
                ).exclude(status=self.Status.CANCELLED)

                if self.pk:
                    bath_overlapping = bath_overlapping.exclude(pk=self.pk)

                for appt in bath_overlapping:
                    if start < appt.end_datetime and end > appt.start_datetime:
                        doc_name = appt.doctor.get_full_name() or appt.doctor.username
                        raise ValidationError(
                            f"يوجد تضارب في قسم الحمام والعناية: يوجد موعد حمام آخر محجوز بالفعل لـ ({appt.animal.name} مع د. {doc_name}) "
                            f"من {appt.time.strftime('%H:%M')} إلى {appt.end_datetime.time().strftime('%H:%M')}. "
                            f"لا يمكن حجز أكثر من موعد حمام في نفس التوقيت."
                        )

            # Rule B: Same-doctor overlap is strictly disallowed for all appointment type combinations
            doctor_overlapping = Appointment.objects.filter(
                doctor=self.doctor,
                date=self.date,
                is_deleted=False,
            ).exclude(status=self.Status.CANCELLED)

            if self.pk:
                doctor_overlapping = doctor_overlapping.exclude(pk=self.pk)

            for appt in doctor_overlapping:
                if start < appt.end_datetime and end > appt.start_datetime:
                    raise ValidationError(
                        f"يوجد تضارب في المواعيد: الطبيب د. {self.doctor.get_full_name() or self.doctor.username} "
                        f"لديه موعد آخر ({appt.animal.name} - {appt.get_appointment_type_display()}) من {appt.time.strftime('%H:%M')} "
                        f"إلى {appt.end_datetime.time().strftime('%H:%M')}."
                    )

        # Conflict prevention rule: The same animal cannot have overlapping active appointments (regardless of doctor)
        if self.animal_id and self.status != self.Status.CANCELLED and not self.is_deleted:
            start = self.start_datetime
            end = self.end_datetime

            animal_overlapping = Appointment.objects.filter(
                animal=self.animal,
                date=self.date,
                is_deleted=False,
            ).exclude(status=self.Status.CANCELLED)

            if self.pk:
                animal_overlapping = animal_overlapping.exclude(pk=self.pk)

            for appt in animal_overlapping:
                appt_start = appt.start_datetime
                appt_end = appt.end_datetime

                if start < appt_end and end > appt_start:
                    doc_name = appt.doctor.get_full_name() or appt.doctor.username
                    raise ValidationError(
                        f"يوجد تضارب للمريض: الحيوان «{self.animal.name}» لديه موعد آخر مسجل بالفعل في نفس التوقيت "
                        f"({appt.get_appointment_type_display()} مع د. {doc_name}) "
                        f"من الساعة {appt.time.strftime('%H:%M')} إلى {appt_end.time().strftime('%H:%M')}."
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
