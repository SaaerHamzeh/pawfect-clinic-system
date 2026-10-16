from django import forms
from .models import MedicalRecord, FileAttachment, VaccinationRecord, validate_attachment_size
from apps.patients.models import Animal
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.settings.models import ClinicalVisitType, VaccineCatalogItem, VisitServiceCatalogItem


class MedicalRecordForm(forms.ModelForm):
    attachment_file = forms.FileField(
        required=False,
        validators=[validate_attachment_size],
        widget=forms.FileInput(
            attrs={
                "class": "w-full text-xs text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100",
            }
        ),
        label="مرفق طبي إضافي (أشعة / تحليل / تقرير - حتى 15MB)",
    )

    # Doctor-created reminder fields
    create_reminder = forms.BooleanField(
        required=False,
        label="إنشاء تذكير متابعة آلي للمريض",
        widget=forms.CheckboxInput(
            attrs={"class": "w-4 h-4 text-primary-600 rounded border-gray-300 focus:ring-primary-500"}
        ),
    )
    reminder_type = forms.ChoiceField(
        required=False,
        choices=[
            ("APPOINTMENT", "موعد"),
            ("GENERAL", "تذكير عام / متابعة"),
            ("VACCINATION", "تطعيم"),
            ("CHECKUP", "فحص دوري"),
            ("FOLLOW_UP", "متابعة حالة"),
            ("MEDICATION", "دواء / علاج"),
        ],
        initial="FOLLOW_UP",
        widget=forms.Select(
            attrs={"class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white"}
        ),
        label="نوع التذكير",
    )
    reminder_due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none"}
        ),
        label="تاريخ استحقاق التذكير",
    )
    reminder_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 2, "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none", "placeholder": "ملاحظات التذكير والمتابعة..."}
        ),
        label="ملاحظات التذكير",
    )

    class Meta:
        model = MedicalRecord
        fields = [
            "animal",
            "doctor",
            "appointment",
            "record_type",
            "date_time",
            "weight_at_visit",
            "symptoms",
            "diagnosis",
            "treatment",
            "medication",
            "prescription",
            "follow_up",
            "notes",
            "vaccine_name",
            "next_vaccine_name",
            "next_vaccination_date",
            "batch_number",
        ]
        widgets = {
            "animal": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "doctor": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "appointment": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                }
            ),
            "record_type": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "date_time": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "required": True,
                }
            ),
            "weight_at_visit": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "مثال: 4.5",
                }
            ),
            "symptoms": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "الأعراض المشكو منها وملاحظات الفحص البدني الأولي...",
                    "rows": 2,
                }
            ),
            "diagnosis": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "التشخيص الطبي لحالة المريض...",
                    "rows": 2,
                }
            ),
            "treatment": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "العلاج المطبق والإجراءات الطبية المتخذة بالعيادة...",
                    "rows": 2,
                }
            ),
            "medication": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "الأدوية والحقن التي تم إعطاؤها...",
                    "rows": 2,
                }
            ),
            "prescription": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "الوصفة الطبية المنزلية (الجرعات وأوقات تناول الدواء)...",
                    "rows": 2,
                }
            ),
            "follow_up": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "مواعيد المراجعة وإرشادات العناية المنزلية...",
                    "rows": 2,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "أي ملاحظات سريرية أو إدارية إضافية...",
                    "rows": 2,
                }
            ),
            "vaccine_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "اسم اللقاح (مثال: Rabies / FVRCP)",
                }
            ),
            "next_vaccine_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "اسم اللقاح اللاحق المستحق (اختياري، يطابق اللقاح الحالي إن ترك فارغاً)",
                }
            ),
            "next_vaccination_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                }
            ),
            "batch_number": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "رقم التشغيلة / Lot Number (اختياري)",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        from apps.accounts.permissions import get_visible_patients, can_view_other_doctors_records, is_admin
        self.fields["animal"].queryset = get_visible_patients(user, Animal.objects.alive()).select_related("client").order_by("name")
        self.fields["animal"].empty_label = "-- اختر المريض (الحيوان) --"

        self.fields["doctor"].queryset = User.objects.filter(
            role=User.Role.VET,
            is_active=True,
        ).order_by("first_name", "username")
        self.fields["doctor"].empty_label = "-- اختر الطبيب المعالج --"

        if user and user.is_authenticated and user.role == User.Role.VET and not user.is_superuser and not getattr(user, "is_admin_user", False):
            self.fields["doctor"].required = False
            self.fields["doctor"].initial = user.pk
            self.initial["doctor"] = user.pk
            if not can_view_other_doctors_records(user):
                self.fields["doctor"].queryset = User.objects.filter(pk=user.pk)

        from django.db.models import Q
        from django.utils import timezone
        today = timezone.localdate()
        appt_qs = Appointment.objects.alive().exclude(status=Appointment.Status.CANCELLED).filter(date__lte=today)
        if self.instance and self.instance.pk and self.instance.appointment_id:
            appt_qs = Appointment.objects.alive().exclude(status=Appointment.Status.CANCELLED).filter(
                Q(date__lte=today) | Q(pk=self.instance.appointment_id)
            )
        if user and not can_view_other_doctors_records(user) and user.role == User.Role.VET:
            appt_qs = appt_qs.filter(doctor=user)

        self.fields["appointment"].queryset = appt_qs.select_related("animal", "doctor").order_by("-date", "-time")
        self.fields["appointment"].empty_label = "-- زيارة مباشرة بدون موعد (Walk-in) --"
        self.fields["appointment"].required = False

        # Dynamically load active visit types from ClinicalVisitType
        try:
            active_vt = ClinicalVisitType.objects.filter(is_active=True).order_by("order", "name")
            if active_vt.exists():
                choices = [(vt.code or vt.name, vt.name) for vt in active_vt]
                self.fields["record_type"].choices = choices
        except Exception:
            pass

        # Dynamically load active vaccines from VaccineCatalogItem
        try:
            active_vacs = VaccineCatalogItem.objects.filter(is_active=True).order_by("order", "name")
            if active_vacs.exists():
                choices = [("", "-- اختر اللقاح المعتمد من القائمة --")] + [(v.name, f"{v.name} (صلاحية: {v.default_validity_days} يوم)") for v in active_vacs]
                self.fields["vaccine_name"].widget = forms.Select(
                    choices=choices,
                    attrs={
                        "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    }
                )
        except Exception:
            pass

    def clean(self):
        cleaned_data = super().clean()
        rec_type = cleaned_data.get("record_type")
        next_vac_date = cleaned_data.get("next_vaccination_date")
        vac_name = cleaned_data.get("vaccine_name")

        # Multi-vaccine payload fallback for validation
        if hasattr(self, "data"):
            if not next_vac_date:
                vac_dates = self.data.getlist("vac_next_date[]") or self.data.getlist("vac_next_date")
                for vd in vac_dates:
                    if vd.strip():
                        import datetime
                        try:
                            next_vac_date = datetime.date.fromisoformat(vd.strip())
                            cleaned_data["next_vaccination_date"] = next_vac_date
                            break
                        except (ValueError, TypeError):
                            pass

            if not vac_name:
                v_names = self.data.getlist("vac_name[]") or self.data.getlist("vac_name")
                for vn in v_names:
                    if vn.strip() and vn.strip() != "OTHER":
                        vac_name = vn.strip()
                        cleaned_data["vaccine_name"] = vac_name
                        break

        if rec_type == MedicalRecord.RecordType.VACCINATION:
            if not next_vac_date:
                self.add_error("next_vaccination_date", "تاريخ الجرعة القادمة المستحقة إلزامي لزيارات التطعيم.")

        create_rem = cleaned_data.get("create_reminder")
        rem_due = cleaned_data.get("reminder_due_date")
        if create_rem and not rem_due:
            self.add_error("reminder_due_date", "يرجى تحديد تاريخ استحقاق التذكير.")

        animal = cleaned_data.get("animal")
        doctor = cleaned_data.get("doctor")
        if not doctor and self.user and self.user.is_authenticated and self.user.role == User.Role.VET:
            doctor = self.user

        appointment = cleaned_data.get("appointment")
        if appointment:
            if animal and appointment.animal_id != animal.pk:
                self.add_error(
                    "appointment",
                    f"الموعد المحدد يخص مريضاً آخر ({appointment.animal.name}) ولا يطابق هذا المريض ({animal.name}).",
                )
            if doctor and appointment.doctor_id != doctor.pk:
                doc_name = appointment.doctor.get_full_name() or appointment.doctor.username
                self.add_error(
                    "appointment",
                    f"الموعد المحدد مسجل لطبيب آخر ({doc_name}) ولا يطابق الطبيب المعالج للزيارة.",
                )
            if appointment.status == Appointment.Status.CANCELLED or appointment.is_deleted:
                self.add_error("appointment", "لا يمكن ربط زيارة سريرية بموعد ملغى أو محذوف.")

            dt = cleaned_data.get("date_time")
            from django.utils import timezone
            visit_date = dt.date() if dt else timezone.localdate()
            if appointment.date > visit_date:
                self.add_error(
                    "appointment",
                    f"لا يمكن ربط الزيارة بموعد مستقبلي بتاريخ ({appointment.date}). إذا حضر المريض كزيارة مباشرة (Walk-in) قبل موعده، يرجى تسجيل الزيارة بدون تحديد موعد، وإضافة تذكير يدوي للاستقبال إن لزم تعديل الموعد المستقبلي.",
                )

        return cleaned_data


class FileAttachmentForm(forms.ModelForm):
    class Meta:
        model = FileAttachment
        fields = ["animal", "medical_record", "file"]
        widgets = {
            "animal": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "medical_record": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                }
            ),
            "file": forms.FileInput(
                attrs={
                    "class": "w-full text-sm text-gray-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100",
                    "required": True,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["animal"].queryset = Animal.objects.alive().order_by("name")
        self.fields["medical_record"].queryset = MedicalRecord.objects.alive().order_by("-date_time")
        self.fields["medical_record"].required = False
        self.fields["medical_record"].empty_label = "-- غير مرتبط بزيارة محددة (مرفق عام للمريض) --"


class VaccinationRecordForm(forms.ModelForm):
    class Meta:
        model = VaccinationRecord
        fields = [
            "animal",
            "doctor",
            "vaccine_name",
            "date_administered",
            "next_due_date",
            "batch_number",
            "notes",
        ]
        widgets = {
            "animal": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "doctor": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "vaccine_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "مثال: لقاح داء الكلب (Rabies) / اللقاح الرباعي",
                    "required": True,
                }
            ),
            "date_administered": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "required": True,
                }
            ),
            "next_due_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                }
            ),
            "batch_number": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "رقم التشغيلة / Lot Number (اختياري)",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                    "placeholder": "ملاحظات حول رد الفعل أو الجرعة...",
                    "rows": 2,
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["animal"].queryset = Animal.objects.alive().select_related("client").order_by("name")
        self.fields["animal"].empty_label = "-- اختر المريض (الحيوان) --"

        self.fields["doctor"].queryset = User.objects.filter(
            role=User.Role.VET,
            is_active=True,
        ).order_by("first_name", "username")
        self.fields["doctor"].empty_label = "-- الطبيب المشرف على التطعيم --"

        if user and user.is_authenticated and user.role == User.Role.VET and not user.is_superuser and not getattr(user, "is_admin_user", False):
            self.fields["doctor"].required = False
            self.fields["doctor"].initial = user.pk
            self.initial["doctor"] = user.pk

        # Dynamically load active vaccines from VaccineCatalogItem
        try:
            active_vacs = VaccineCatalogItem.objects.filter(is_active=True).order_by("order", "name")
            if active_vacs.exists():
                choices = [("", "-- اختر اللقاح المعتمد من القائمة --")] + [(v.name, f"{v.name} (صلاحية: {v.default_validity_days} يوم)") for v in active_vacs]
                self.fields["vaccine_name"].widget = forms.Select(
                    choices=choices,
                    attrs={
                        "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                        "required": True,
                    }
                )
        except Exception:
            pass
