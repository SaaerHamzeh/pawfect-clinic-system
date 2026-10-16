from django import forms
from .models import Client, ClientPhone
from apps.core.validators import validate_phone_number


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["full_name", "phone", "address", "notes"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "الاسم الكامل للمالك",
                    "required": True,
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-mono focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "رقم الهاتف الأساسي (مثال: 0935123456)",
                    "required": True,
                }
            ),
            "address": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "العنوان بالتفصيل (مثال: جرمانا - الروضة)",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "أي ملاحظات عامة حول المالك...",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaned_extra_phones = []

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        return validate_phone_number(phone)

    def _get_phone_variants(self, phone):
        variants = {phone}
        if phone.startswith("09") and len(phone) == 10:
            nine_digits = phone[1:]
            variants.update([f"0{nine_digits}", f"+963{nine_digits}", f"00963{nine_digits}"])
        elif phone.startswith("+963") and len(phone) == 13:
            nine_digits = phone[4:]
            variants.update([f"0{nine_digits}", f"+963{nine_digits}", f"00963{nine_digits}"])
        elif phone.startswith("00963") and len(phone) == 14:
            nine_digits = phone[5:]
            variants.update([f"0{nine_digits}", f"+963{nine_digits}", f"00963{nine_digits}"])
        return variants

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get("phone")
        confirm_override = (
            self.data.get("confirm_duplicate_phone")
            or self.data.get("confirm_duplicate")
            or self.data.get("override_duplicate")
        )

        # 1. Primary phone duplicate check
        if phone and not confirm_override:
            variants = self._get_phone_variants(phone)
            existing_qs = Client.objects.alive().filter(phone__in=variants)
            if self.instance and self.instance.pk:
                existing_qs = existing_qs.exclude(pk=self.instance.pk)

            existing_client = existing_qs.first()
            if existing_client:
                self.has_duplicate_phone_warning = True
                self.duplicate_client = existing_client
                raise forms.ValidationError({
                    "phone": forms.ValidationError(
                        f"يوجد عميل آخر مسجل بنفس رقم الهاتف الأساسي: {existing_client.full_name} ({existing_client.phone}). للمتابعة رغم ذلك، يرجى تأكيد الحفظ.",
                        code="duplicate_phone"
                    )
                })

        # 2. Extract and validate extra phone numbers
        raw_extra_phones = self.data.getlist("extra_phones") if hasattr(self.data, "getlist") else []
        raw_extra_labels = self.data.getlist("extra_labels") if hasattr(self.data, "getlist") else []

        valid_extras = []
        seen_phones = {phone} if phone else set()

        for idx, raw_p in enumerate(raw_extra_phones):
            p_str = (raw_p or "").strip()
            if not p_str:
                continue
            lbl = (raw_extra_labels[idx] if idx < len(raw_extra_labels) else "موبايل").strip() or "موبايل"

            try:
                clean_p = validate_phone_number(p_str)
            except forms.ValidationError as e:
                raise forms.ValidationError(f"رقم هاتف إضافي غير صالح «{p_str}»: {e.message}")

            if clean_p in seen_phones:
                raise forms.ValidationError(f"رقم الهاتف «{clean_p}» مكرر في بيانات نفس العميل.")
            seen_phones.add(clean_p)

            # Check duplicate against other clients if not confirmed
            if not confirm_override:
                extra_variants = self._get_phone_variants(clean_p)
                dup_qs = Client.objects.alive().filter(phone__in=extra_variants)
                if self.instance and self.instance.pk:
                    dup_qs = dup_qs.exclude(pk=self.instance.pk)
                dup_client = dup_qs.first()
                if dup_client:
                    self.has_duplicate_phone_warning = True
                    self.duplicate_client = dup_client
                    raise forms.ValidationError({
                        "phone": forms.ValidationError(
                            f"الرقم الإضافي «{clean_p}» مسجل بالفعل للعميل: {dup_client.full_name}. للمتابعة وتأكيد الحفظ اضغط تأكيد.",
                            code="duplicate_phone"
                        )
                    })

            valid_extras.append({"phone": clean_p, "label": lbl})

        self.cleaned_extra_phones = valid_extras
        return cleaned_data

    def save(self, commit=True):
        client = super().save(commit=commit)
        if commit:
            self.save_phones(client)
        return client

    def save_phones(self, client):
        """Synchronizes ClientPhone records with primary and extra phones."""
        # 1. Ensure primary phone record exists
        primary_record = client.phone_numbers.filter(is_primary=True, is_deleted=False).first()
        if primary_record:
            if primary_record.phone != client.phone:
                primary_record.phone = client.phone
                primary_record.save(update_fields=["phone", "updated_at"])
        else:
            ClientPhone.objects.create(
                client=client,
                phone=client.phone,
                label="أساسي",
                is_primary=True
            )

        # 2. Synchronize secondary phones
        current_secondaries = {cp.phone: cp for cp in client.phone_numbers.filter(is_primary=False, is_deleted=False)}
        submitted_phones = {item["phone"]: item["label"] for item in self.cleaned_extra_phones}

        # Delete any secondary phone removed by user
        for old_phone, obj in current_secondaries.items():
            if old_phone not in submitted_phones:
                obj.delete()

        # Add or update submitted extra phones
        for phone_val, label_val in submitted_phones.items():
            if phone_val in current_secondaries:
                cp = current_secondaries[phone_val]
                if cp.label != label_val:
                    cp.label = label_val
                    cp.save(update_fields=["label", "updated_at"])
            else:
                ClientPhone.objects.create(
                    client=client,
                    phone=phone_val,
                    label=label_val,
                    is_primary=False
                )


