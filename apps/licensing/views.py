from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from .utils import (
    get_machine_id,
    is_system_licensed,
    save_license_token,
)


def activate_view(request):
    """
    Hardware Activation View:
    Displays current Machine ID to the user and handles license key submission.
    """
    machine_id = get_machine_id()
    is_licensed, status_msg, payload = is_system_licensed()

    # If already licensed and user directly visits /licensing/activate/, show details
    if request.method == "POST":
        license_key = request.POST.get("license_key", "").strip()

        # Also support uploading a .lic file directly
        license_file = request.FILES.get("license_file")
        if license_file:
            try:
                license_key = license_file.read().decode("utf-8").strip()
            except Exception:
                messages.error(request, "تعذر قراءة ملف الترخيص المرفوع. تأكد من سلامة الملف.")
                return render(
                    request,
                    "licensing/activate.html",
                    {
                        "machine_id": machine_id,
                        "is_licensed": is_licensed,
                        "status_msg": status_msg,
                        "payload": payload,
                    },
                )

        if not license_key:
            messages.error(request, "يرجى إدخال مفتاح الترخيص أو رفع ملف الترخيص.")
        else:
            success, msg, payload_data = save_license_token(license_key)
            if success:
                messages.success(request, "تهانينا! تم تفعيل نظام Pawfect Clinic على هذا الجهاز بنجاح.")
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    has_admin = User.objects.filter(role=User.Role.ADMIN, is_active=True).exists()
                except Exception:
                    has_admin = False

                if has_admin:
                    return redirect("core:dashboard")
                return redirect("setup:wizard")
            else:
                messages.error(request, msg)

    return render(
        request,
        "licensing/activate.html",
        {
            "machine_id": machine_id,
            "is_licensed": is_licensed,
            "status_msg": status_msg,
            "payload": payload,
        },
    )
