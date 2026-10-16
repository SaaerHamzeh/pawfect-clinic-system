from django import forms
from .models import Animal
from apps.clients.models import Client
from apps.settings.models import AnimalSpecies


class AnimalForm(forms.ModelForm):
    class Meta:
        model = Animal
        fields = [
            "name",
            "species",
            "breed",
            "gender",
            "birth_date",
            "weight",
            "color",
            "identification",
            "photo",
            "notes",
            "client",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "اسم الحيوان (مثال: لونا / ريكس)",
                    "required": True,
                }
            ),
            "species": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "breed": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "السلالة (اختياري - مثال: شيرازي / جيرمن)",
                }
            ),
            "gender": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                }
            ),
            "birth_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none",
                }
            ),
            "weight": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-mono focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "الوزن بالكيلوغرام (مثال: 4.5)",
                    "step": "0.01",
                }
            ),
            "color": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "اللون والعلامات المميزة (مثال: أبيض ثلجي)",
                }
            ),
            "identification": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "علامات تمييزية أو رقم طوق (اختياري)",
                }
            ),
            "photo": forms.FileInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none file:mr-4 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100",
                    "accept": "image/*",
                }
            ),
            "client": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:outline-none bg-white",
                    "required": True,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none",
                    "placeholder": "ملاحظات طبية أو سلوكية خاصة بالحيوان...",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show active clients, plus the current client if editing
        if self.instance and self.instance.pk and self.instance.client_id:
            from django.db.models import Q
            self.fields["client"].queryset = Client.objects.all_with_deleted().filter(
                Q(is_deleted=False) | Q(pk=self.instance.client_id)
            ).order_by("full_name")
        else:
            self.fields["client"].queryset = Client.objects.alive().order_by("full_name")
        self.fields["client"].empty_label = "-- اختر المالك الأساسي --"

        # Dynamically load active species from AnimalSpecies lookup table with fallback
        try:
            active_species = AnimalSpecies.objects.filter(is_active=True).order_by("order", "name")
            if active_species.exists():
                choices = [(sp.code or sp.name, sp.name) for sp in active_species]
                self.fields["species"].choices = choices
        except Exception:
            pass

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        client = cleaned_data.get("client") or (self.instance.client if self.instance and self.instance.pk else None)
        confirm_override = (
            self.data.get("confirm_duplicate_name")
            or self.data.get("confirm_duplicate")
            or self.data.get("override_duplicate")
        )

        if name and client and not confirm_override:
            clean_name = name.strip()
            existing_qs = Animal.objects.alive().filter(client=client, name__iexact=clean_name)
            if self.instance and self.instance.pk:
                existing_qs = existing_qs.exclude(pk=self.instance.pk)

            existing_animal = existing_qs.first()
            if existing_animal:
                self.has_duplicate_name_warning = True
                self.duplicate_animal = existing_animal
                raise forms.ValidationError({
                    "name": forms.ValidationError(
                        f"العميل «{client.full_name}» لديه مريض آخر مسجل بالفعل بنفس الاسم: «{existing_animal.name}» (المعرف: #{existing_animal.animal_id or existing_animal.pk}). للمتابعة وتأكيد إضافة هذا الحيوان، يرجى تأكيد الحفظ.",
                        code="duplicate_name"
                    )
                })

        return cleaned_data
