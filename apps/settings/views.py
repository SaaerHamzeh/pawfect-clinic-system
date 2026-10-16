from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST

from apps.audit.models import AuditLog
from apps.accounts.models import User
from apps.accounts.permissions import (
    admin_required,
    can_access_settings,
    can_backup_restore,
)
from apps.core.utils import get_client_ip

from .models import (
    AnimalSpecies,
    AnimalBreed,
    ClinicalVisitType,
    AppointmentTypeConfig,
    VaccineCatalogItem,
    VisitServiceCatalogItem,
)


@login_required
def settings(request):
    if not can_access_settings(request.user):
        raise PermissionDenied("ليس لديك الصلاحية للوصول إلى قائمة الإعدادات.")
    return render(request, "settings/settings.html")


@admin_required
def users(request):
    return render(request, "users/users.html")


@login_required
def backups(request):
    if not can_backup_restore(request.user):
        raise PermissionDenied("ليس لديك الصلاحية للوصول إلى إدارة النسخ الاحتياطية.")
    return render(request, "backups/backups.html")


@login_required
@admin_required
def audit_logs(request):
    logs = AuditLog.objects.select_related("user").all()

    q = request.GET.get("q", "").strip()
    if q:
        logs = logs.filter(
            Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(entity_type__icontains=q)
            | Q(entity_id__icontains=q)
            | Q(description__icontains=q)
            | Q(ip_address__icontains=q)
        )

    user_id = request.GET.get("user_id", "").strip()
    if user_id:
        logs = logs.filter(user_id=user_id)

    action = request.GET.get("action", "").strip()
    if action:
        logs = logs.filter(action=action)

    date = request.GET.get("date", "").strip()
    if date:
        logs = logs.filter(timestamp__date=date)

    logs = logs.order_by("-timestamp")

    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    users_list = User.objects.all().order_by("username")

    context = {
        "logs": page_obj,
        "page_obj": page_obj,
        "users_list": users_list,
        "actions": AuditLog.Action.choices,
        "selected_q": q,
        "selected_user": user_id,
        "selected_action": action,
        "selected_date": date,
    }
    return render(request, "audit/audit_logs.html", context)


# ==============================================================================
# Dynamic Lookups & Custom Categories Management
# ==============================================================================

@admin_required
def lookups_dashboard(request):
    """
    Main interactive dashboard for managing clinic taxonomies, dropdowns,
    and custom lookup categories.
    """
    active_tab = request.GET.get("tab", "species")

    species_list = AnimalSpecies.objects.all().prefetch_related("breeds")
    breeds_list = AnimalBreed.objects.select_related("species").all()
    visit_types = ClinicalVisitType.objects.all()
    appt_types = AppointmentTypeConfig.objects.all()
    vaccines = VaccineCatalogItem.objects.select_related("target_species").all()
    services = VisitServiceCatalogItem.objects.all()

    context = {
        "active_tab": active_tab,
        "species_list": species_list,
        "breeds_list": breeds_list,
        "visit_types": visit_types,
        "appt_types": appt_types,
        "vaccines": vaccines,
        "services": services,
    }
    return render(request, "settings/lookups.html", context)


# --- 1. Species Handlers ---

@admin_required
@require_POST
def save_species(request):
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    icon = request.POST.get("icon", "🐾").strip() or "🐾"
    order = int(request.POST.get("order", 0) or 0)

    if not name:
        messages.error(request, "يرجى إدخال اسم الفصيل.")
        return redirect("/settings/lookups/?tab=species")

    if pk:
        species = get_object_or_404(AnimalSpecies, pk=pk)
        species.name = name
        species.icon = icon
        species.order = order
        species.save()
        messages.success(request, f"تم تعديل فصيل '{name}' بنجاح.")
    else:
        if AnimalSpecies.objects.filter(name=name).exists():
            messages.error(request, f"الفصيل '{name}' موجود مسبقاً.")
            return redirect("/settings/lookups/?tab=species")
        species = AnimalSpecies.objects.create(name=name, icon=icon, order=order, is_system=False)
        messages.success(request, f"تمت إضافة الفصيل '{name}' بنجاح.")

    return redirect("/settings/lookups/?tab=species")


@admin_required
@require_POST
def toggle_species(request, pk):
    species = get_object_or_404(AnimalSpecies, pk=pk)
    species.is_active = not species.is_active
    species.save()
    status_str = "تفعيل" if species.is_active else "تعطيل"
    messages.success(request, f"تم {status_str} فصيل '{species.name}'.")
    return redirect("/settings/lookups/?tab=species")


@admin_required
@require_POST
def delete_species(request, pk):
    species = get_object_or_404(AnimalSpecies, pk=pk)
    if species.is_system:
        messages.error(request, "لا يمكن حذف فصيل أساسي محمي من قِبل النظام.")
        return redirect("/settings/lookups/?tab=species")
    species_name = species.name
    species.delete()
    messages.success(request, f"تم حذف الفصيل '{species_name}' بنجاح.")
    return redirect("/settings/lookups/?tab=species")


# --- 2. Breeds Handlers ---

@admin_required
@require_POST
def save_breed(request):
    pk = request.POST.get("pk")
    species_id = request.POST.get("species_id")
    name = request.POST.get("name", "").strip()
    order = int(request.POST.get("order", 0) or 0)

    if not name or not species_id:
        messages.error(request, "يرجى اختيار الفصيل وإدخال اسم السلالة.")
        return redirect("/settings/lookups/?tab=species")

    species = get_object_or_404(AnimalSpecies, pk=species_id)

    if pk:
        breed = get_object_or_404(AnimalBreed, pk=pk)
        breed.species = species
        breed.name = name
        breed.order = order
        breed.save()
        messages.success(request, f"تم تعديل سلالة '{name}' بنجاح.")
    else:
        if AnimalBreed.objects.filter(species=species, name=name).exists():
            messages.error(request, f"السلالة '{name}' مسجلة مسبقاً لهذا الفصيل.")
            return redirect("/settings/lookups/?tab=species")
        AnimalBreed.objects.create(species=species, name=name, order=order)
        messages.success(request, f"تمت إضافة سلالة '{name}' بنجاح.")

    return redirect("/settings/lookups/?tab=species")


@admin_required
@require_POST
def toggle_breed(request, pk):
    breed = get_object_or_404(AnimalBreed, pk=pk)
    breed.is_active = not breed.is_active
    breed.save()
    status_str = "تفعيل" if breed.is_active else "تعطيل"
    messages.success(request, f"تم {status_str} سلالة '{breed.name}'.")
    return redirect("/settings/lookups/?tab=species")


@admin_required
@require_POST
def delete_breed(request, pk):
    breed = get_object_or_404(AnimalBreed, pk=pk)
    breed_name = breed.name
    breed.delete()
    messages.success(request, f"تم حذف سلالة '{breed_name}' بنجاح.")
    return redirect("/settings/lookups/?tab=species")


# --- 3. Clinical Visit Types Handlers ---

@admin_required
@require_POST
def save_visit_type(request):
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    icon = request.POST.get("icon", "🩺").strip() or "🩺"
    color = request.POST.get("color", "#1099a7").strip() or "#1099a7"
    requires_vaccine_logic = request.POST.get("requires_vaccine_logic") == "on"
    order = int(request.POST.get("order", 0) or 0)

    if not name:
        messages.error(request, "يرجى إدخال اسم نوع الزيارة.")
        return redirect("/settings/lookups/?tab=visits")

    if pk:
        vt = get_object_or_404(ClinicalVisitType, pk=pk)
        vt.name = name
        vt.icon = icon
        vt.color = color
        if not vt.is_system:
            vt.requires_vaccine_logic = requires_vaccine_logic
        vt.order = order
        vt.save()
        messages.success(request, f"تم تعديل نوع الزيارة '{name}' بنجاح.")
    else:
        if ClinicalVisitType.objects.filter(name=name).exists():
            messages.error(request, f"نوع الزيارة '{name}' مسجل مسبقاً.")
            return redirect("/settings/lookups/?tab=visits")
        ClinicalVisitType.objects.create(
            name=name,
            icon=icon,
            color=color,
            requires_vaccine_logic=requires_vaccine_logic,
            order=order,
            is_system=False,
        )
        messages.success(request, f"تمت إضافة نوع الزيارة '{name}' بنجاح.")

    return redirect("/settings/lookups/?tab=visits")


@admin_required
@require_POST
def toggle_visit_type(request, pk):
    vt = get_object_or_404(ClinicalVisitType, pk=pk)
    vt.is_active = not vt.is_active
    vt.save()
    status_str = "تفعيل" if vt.is_active else "تعطيل"
    messages.success(request, f"تم {status_str} نوع الزيارة '{vt.name}'.")
    return redirect("/settings/lookups/?tab=visits")


@admin_required
@require_POST
def delete_visit_type(request, pk):
    vt = get_object_or_404(ClinicalVisitType, pk=pk)
    if vt.is_system:
        messages.error(request, "لا يمكن حذف نوع زيارة أساسي محمي بالنظام.")
        return redirect("/settings/lookups/?tab=visits")
    vt_name = vt.name
    vt.delete()
    messages.success(request, f"تم حذف نوع الزيارة '{vt_name}' بنجاح.")
    return redirect("/settings/lookups/?tab=visits")


# --- 4. Appointment Types Handlers ---

@admin_required
@require_POST
def save_appointment_type(request):
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    default_duration = int(request.POST.get("default_duration", 30) or 30)
    color = request.POST.get("color", "#8b5cf6").strip() or "#8b5cf6"
    order = int(request.POST.get("order", 0) or 0)

    if not name:
        messages.error(request, "يرجى إدخال اسم نوع الموعد.")
        return redirect("/settings/lookups/?tab=appointments")

    if pk:
        at = get_object_or_404(AppointmentTypeConfig, pk=pk)
        at.name = name
        at.default_duration = default_duration
        at.color = color
        at.order = order
        at.save()
        messages.success(request, f"تم تعديل نوع الموعد '{name}' بنجاح.")
    else:
        if AppointmentTypeConfig.objects.filter(name=name).exists():
            messages.error(request, f"نوع الموعد '{name}' مسجل مسبقاً.")
            return redirect("/settings/lookups/?tab=appointments")
        AppointmentTypeConfig.objects.create(
            name=name,
            default_duration=default_duration,
            color=color,
            order=order,
            is_system=False,
        )
        messages.success(request, f"تمت إضافة نوع الموعد '{name}' بنجاح.")

    return redirect("/settings/lookups/?tab=appointments")


@admin_required
@require_POST
def toggle_appointment_type(request, pk):
    at = get_object_or_404(AppointmentTypeConfig, pk=pk)
    at.is_active = not at.is_active
    at.save()
    status_str = "تفعيل" if at.is_active else "تعطيل"
    messages.success(request, f"تم {status_str} نوع الموعد '{at.name}'.")
    return redirect("/settings/lookups/?tab=appointments")


@admin_required
@require_POST
def delete_appointment_type(request, pk):
    at = get_object_or_404(AppointmentTypeConfig, pk=pk)
    if at.is_system:
        messages.error(request, "لا يمكن حذف نوع موعد أساسي محمي بالنظام.")
        return redirect("/settings/lookups/?tab=appointments")
    at_name = at.name
    at.delete()
    messages.success(request, f"تم حذف نوع الموعد '{at_name}' بنجاح.")
    return redirect("/settings/lookups/?tab=appointments")


# --- 5. Vaccines Catalog Handlers ---

@admin_required
@require_POST
def save_vaccine(request):
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    species_id = request.POST.get("species_id") or None
    default_validity_days = int(request.POST.get("default_validity_days", 365) or 365)
    notes = request.POST.get("notes", "").strip()
    order = int(request.POST.get("order", 0) or 0)

    if not name:
        messages.error(request, "يرجى إدخال اسم اللقاح.")
        return redirect("/settings/lookups/?tab=vaccines")

    species = None
    if species_id:
        species = AnimalSpecies.objects.filter(pk=species_id).first()

    if pk:
        vac = get_object_or_404(VaccineCatalogItem, pk=pk)
        vac.name = name
        vac.target_species = species
        vac.default_validity_days = default_validity_days
        vac.notes = notes
        vac.order = order
        vac.save()
        messages.success(request, f"تم تعديل اللقاح '{name}' بنجاح.")
    else:
        if VaccineCatalogItem.objects.filter(name=name).exists():
            messages.error(request, f"اللقاح '{name}' مسجل مسبقاً.")
            return redirect("/settings/lookups/?tab=vaccines")
        VaccineCatalogItem.objects.create(
            name=name,
            target_species=species,
            default_validity_days=default_validity_days,
            notes=notes,
            order=order,
        )
        messages.success(request, f"تمت إضافة اللقاح '{name}' بنجاح.")

    return redirect("/settings/lookups/?tab=vaccines")


@admin_required
@require_POST
def toggle_vaccine(request, pk):
    vac = get_object_or_404(VaccineCatalogItem, pk=pk)
    vac.is_active = not vac.is_active
    vac.save()
    status_str = "تفعيل" if vac.is_active else "تعطيل"
    messages.success(request, f"تم {status_str} اللقاح '{vac.name}'.")
    return redirect("/settings/lookups/?tab=vaccines")


@admin_required
@require_POST
def delete_vaccine(request, pk):
    vac = get_object_or_404(VaccineCatalogItem, pk=pk)
    vac_name = vac.name
    vac.delete()
    messages.success(request, f"تم حذف اللقاح '{vac_name}' بنجاح.")
    return redirect("/settings/lookups/?tab=vaccines")


# --- 6. Visit Services Catalog Handlers ---

@admin_required
@require_POST
def save_service(request):
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    default_notes = request.POST.get("default_notes", "").strip()
    order = int(request.POST.get("order", 0) or 0)

    if not name:
        messages.error(request, "يرجى إدخال اسم الخدمة.")
        return redirect("/settings/lookups/?tab=services")

    if pk:
        srv = get_object_or_404(VisitServiceCatalogItem, pk=pk)
        srv.name = name
        srv.default_notes = default_notes
        srv.order = order
        srv.save()
        messages.success(request, f"تم تعديل الخدمة '{name}' بنجاح.")
    else:
        if VisitServiceCatalogItem.objects.filter(name=name).exists():
            messages.error(request, f"الخدمة '{name}' مسجلة مسبقاً.")
            return redirect("/settings/lookups/?tab=services")
        VisitServiceCatalogItem.objects.create(
            name=name,
            default_notes=default_notes,
            order=order,
        )
        messages.success(request, f"تمت إضافة الخدمة '{name}' بنجاح.")

    return redirect("/settings/lookups/?tab=services")


@admin_required
@require_POST
def toggle_service(request, pk):
    srv = get_object_or_404(VisitServiceCatalogItem, pk=pk)
    srv.is_active = not srv.is_active
    srv.save()
    status_str = "تفعيل" if srv.is_active else "تعطيل"
    messages.success(request, f"تم {status_str} الخدمة '{srv.name}'.")
    return redirect("/settings/lookups/?tab=services")


@admin_required
@require_POST
def delete_service(request, pk):
    srv = get_object_or_404(VisitServiceCatalogItem, pk=pk)
    srv_name = srv.name
    srv.delete()
    messages.success(request, f"تم حذف الخدمة '{srv_name}' بنجاح.")
    return redirect("/settings/lookups/?tab=services")


# --- 7. Public/Staff API Endpoints for Dropdowns ---

@login_required
def api_species_breeds(request, species_key):
    """
    Returns active breeds for a selected species (by ID or code/name).
    """
    species = None
    if str(species_key).isdigit():
        species = AnimalSpecies.objects.filter(pk=species_key, is_active=True).first()
    if not species:
        species = AnimalSpecies.objects.filter(
            Q(code=species_key) | Q(name=species_key),
            is_active=True
        ).first()

    if not species:
        return JsonResponse({"breeds": []})

    breeds = species.breeds.filter(is_active=True).values("id", "name")
    return JsonResponse({"species": species.name, "breeds": list(breeds)})


@login_required
def api_vaccines_catalog(request):
    """
    Returns active catalog of vaccines and default validity days.
    """
    vaccines = VaccineCatalogItem.objects.filter(is_active=True).values(
        "id", "name", "default_validity_days", "notes"
    )
    return JsonResponse({"vaccines": list(vaccines)})
