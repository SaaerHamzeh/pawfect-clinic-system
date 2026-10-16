from django.db import models, transaction
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel


class Animal(TimeStampedModel, SoftDeleteModel):
    """Animal / Patient model representing pets under clinic care."""

    class Species(models.TextChoices):
        CAT = "CAT", "قطة"
        DOG = "DOG", "كلب"
        BIRD = "BIRD", "طائر"
        OTHER = "OTHER", "أخرى"

    class Gender(models.TextChoices):
        MALE = "MALE", "ذكر"
        FEMALE = "FEMALE", "أنثى"
        UNKNOWN = "UNKNOWN", "غير محدد"

    animal_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        db_index=True,
        editable=False,
        verbose_name="رقم المريض المميز",
        help_text="معرف تسلسلي عالمي فريد مكون من 7 أرقام (مثال: 0000001)",
    )
    name = models.CharField(max_length=100, db_index=True, verbose_name="اسم الحيوان")
    species = models.CharField(
        max_length=20,
        choices=Species.choices,
        default=Species.CAT,
        verbose_name="النوع",
    )
    breed = models.CharField(max_length=100, blank=True, verbose_name="السلالة")
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
        verbose_name="الجنس",
    )
    birth_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="الوزن بالكيلوغرام",
        verbose_name="الوزن (كغ)",
    )
    color = models.CharField(max_length=100, blank=True, verbose_name="اللون والعلامات المميزة")
    identification = models.CharField(
        max_length=100,
        blank=True,
        help_text="علامات تمييزية أو رقم طوق",
        verbose_name="علامات تمييزية",
    )
    photo = models.ImageField(
        upload_to="animals/photos/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="الصورة",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="animals",
        verbose_name="المالك الأساسي",
    )

    class Meta:
        verbose_name = "مريض (حيوان)"
        verbose_name_plural = "المرضى (الحيوانات)"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name", "species"]),
            models.Index(fields=["client", "is_deleted"]),
        ]

    def __str__(self):
        id_display = f" [{self.animal_id}]" if self.animal_id else ""
        return f"{self.name}{id_display} ({self.get_species_display()}) - {self.client.full_name}"

    @classmethod
    def generate_next_animal_id(cls):
        """
        Generate the next sequential 7-digit animal ID (e.g. 0000001, 0000002).
        Uses a lock on existing animal IDs to ensure concurrency safety.
        """
        with transaction.atomic():
            existing_ids = (
                cls.all_objects.select_for_update()
                .exclude(animal_id="")
                .values_list("animal_id", flat=True)
            )
            max_seq = 0
            for aid in existing_ids:
                digits = "".join(filter(str.isdigit, str(aid)))
                if digits:
                    val = int(digits)
                    if val > max_seq:
                        max_seq = val
            next_seq = max_seq + 1
            return f"{next_seq:07d}"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        today = timezone.localdate()
        if self.birth_date and self.birth_date > today:
            raise ValidationError({"birth_date": "تاريخ ميلاد الحيوان لا يمكن أن يكون في المستقبل."})
        if self.weight is not None and self.weight <= 0:
            raise ValidationError({"weight": "وزن الحيوان يجب أن يكون قيمة رقمية موجبة أكبر من الصفر."})

    def save(self, *args, **kwargs):
        if self.weight is not None:
            from decimal import Decimal, ROUND_HALF_UP
            self.weight = Decimal(str(self.weight)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.full_clean()
        if not self.animal_id:
            with transaction.atomic():
                self.animal_id = self.generate_next_animal_id()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def soft_delete(self, timestamp=None):
        now = timestamp or timezone.now()
        super().soft_delete(timestamp=now)
        Appointment = self.appointments.model
        for appt in Appointment.all_objects.filter(animal=self, is_deleted=False):
            appt.soft_delete(timestamp=now)

    def restore(self):
        animal_deleted_at = self.deleted_at
        super().restore()
        if animal_deleted_at:
            Appointment = self.appointments.model
            for appt in Appointment.all_objects.filter(
                animal=self,
                is_deleted=True,
                deleted_at=animal_deleted_at,
            ):
                appt.restore()

