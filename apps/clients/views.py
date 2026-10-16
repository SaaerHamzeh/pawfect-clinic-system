from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from apps.core.utils import get_client_ip

import json
from .models import Client
from .forms import ClientForm
from apps.patients.models import Animal
from apps.patients.forms import AnimalForm
from apps.settings.models import AnimalBreed
from apps.audit.models import AuditLog
from apps.accounts.permissions import (
    can_restore_records,
    can_delete_records,
    restore_permission_required,
    delete_permission_required,
    client_manage_permission_required,
    get_visible_patients,
)


@login_required
def clients(request):
    """List clients with search, status filtering, sorting, and stats."""
    status = request.GET.get("status", "active")
    q = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "newest")

    # Base QuerySet
    if status == "deleted":
        queryset = Client.objects.deleted_only()
    else:
        queryset = Client.objects.alive()

    # Annotate active animals count and prefetch phone numbers
    queryset = queryset.annotate(
        pets_count=Count("animals", filter=Q(animals__is_deleted=False))
    ).prefetch_related("phone_numbers")

    # Search filter (searches primary and all secondary phone numbers)
    if q:
        queryset = queryset.filter(
            Q(full_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(phone_numbers__phone__icontains=q)
            | Q(address__icontains=q)
            | Q(notes__icontains=q)
        ).distinct()

    # Sorting
    if sort_by == "name":
        queryset = queryset.order_by("full_name")
    elif sort_by == "pets_count":
        queryset = queryset.order_by("-pets_count", "-created_at")
    else:  # newest
        queryset = queryset.order_by("-created_at")

    # Stats
    total_clients_count = Client.objects.alive().count()
    total_pets_count = Animal.objects.alive().count()

    # Try checking today's appointments if app available
    today_appointments_count = 0
    try:
        from apps.appointments.models import Appointment
        today = timezone.localdate()
        today_appointments_count = Appointment.objects.alive().filter(
            date=today, status=Appointment.Status.SCHEDULED
        ).count()
    except Exception:
        pass

    # Pagination
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    form = ClientForm()

    context = {
        "clients": page_obj,
        "page_obj": page_obj,
        "total_clients_count": total_clients_count,
        "total_pets_count": total_pets_count,
        "today_appointments_count": today_appointments_count,
        "form": form,
        "status": status,
        "q": q,
        "sort_by": sort_by,
        "can_restore": can_restore_records(request.user),
    }
    return render(request, "clients/clients.html", context)


@login_required
def client_detail(request, client_id):
    """View client profile details and owned animals."""
    # Find client even if deleted to support view / restore
    client_obj = get_object_or_404(Client.all_objects.prefetch_related("phone_numbers"), pk=client_id)
    animals = get_visible_patients(request.user, client_obj.animals.filter(is_deleted=False)).order_by("-created_at")

    edit_form = ClientForm(instance=client_obj)
    animal_form = AnimalForm(initial={"client": client_obj})

    # Stats for this client
    total_clinical_visits = 0
    try:
        from apps.clinical.models import MedicalRecord
        total_clinical_visits = MedicalRecord.objects.filter(
            animal__client=client_obj, is_deleted=False
        ).count()
    except Exception:
        pass

    upcoming_appointments = 0
    try:
        from apps.appointments.models import Appointment
        upcoming_appointments = Appointment.objects.alive().filter(
            animal__client=client_obj,
            date__gte=timezone.localdate(),
            status=Appointment.Status.SCHEDULED,
        ).count()
    except Exception:
        pass

    context = {
        "client": client_obj,
        "animals": animals,
        "edit_form": edit_form,
        "animal_form": animal_form,
        "species_breeds_json": json.dumps(AnimalBreed.get_species_breeds_map(), ensure_ascii=False),
        "total_clinical_visits": total_clinical_visits,
        "upcoming_appointments": upcoming_appointments,
        "can_restore": can_restore_records(request.user),
    }
    return render(request, "clients/clients_details.html", context)


@login_required
@client_manage_permission_required
@require_POST
def client_create(request):
    """Handle client creation and audit logging."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    form = ClientForm(request.POST)
    if form.is_valid():
        client_obj = form.save()

        # Audit Log
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity=client_obj,
            entity_id=str(client_obj.pk),
            description=f"إضافة عميل جديد: {client_obj.full_name} ({client_obj.phone})",
            ip_address=get_client_ip(request),
        )

        msg = f"تمت إضافة العميل «{client_obj.full_name}» بنجاح."
        redirect_url = reverse("clients:detail", kwargs={"client_id": client_obj.pk})
        if is_ajax:
            messages.success(request, msg)
            return JsonResponse({"success": True, "redirect_url": redirect_url, "message": msg})

        messages.success(request, msg)
        return redirect("clients:detail", client_id=client_obj.pk)

    error_list = [err for sublist in form.errors.values() for err in sublist]
    error_msg = "; ".join(error_list) if error_list else "يرجى التحقق من صحة البيانات المدخلة."
    is_duplicate = getattr(form, "has_duplicate_phone_warning", False)
    if is_ajax:
        return JsonResponse({
            "success": False,
            "error": error_msg,
            "duplicate_warning": is_duplicate,
            "duplicate_field": "phone" if is_duplicate else None,
            "field_errors": {k: [str(e) for e in v] for k, v in form.errors.items()}
        }, status=400)

    messages.error(request, error_msg)
    return redirect("clients:list")


@login_required
@client_manage_permission_required
@require_POST
def client_update(request, client_id):
    """Handle client update and audit logging."""
    client_obj = get_object_or_404(Client.all_objects, pk=client_id)
    form = ClientForm(request.POST, instance=client_obj)
    if form.is_valid():
        client_obj = form.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity=client_obj,
            entity_id=str(client_obj.pk),
            description=f"تعديل بيانات العميل: {client_obj.full_name}",
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تم تحديث بيانات العميل «{client_obj.full_name}» بنجاح.")
        return redirect("clients:detail", client_id=client_obj.pk)

    messages.error(request, "فشل تعديل البيانات. يرجى مراجعة الحقول المطلوبة.")
    return redirect("clients:detail", client_id=client_obj.pk)


@login_required
@delete_permission_required
@require_POST
def client_delete(request, client_id):
    """Handle client soft-deletion."""
    client_obj = get_object_or_404(Client.objects.alive(), pk=client_id)
    client_name = client_obj.full_name
    client_obj.soft_delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity=client_obj,
        entity_id=str(client_obj.pk),
        description=f"حذف العميل مؤقتاً (نقل للسلة): {client_name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم نقل العميل «{client_name}» إلى سلة المحذوفات.")
    return redirect("clients:list")


@login_required
@restore_permission_required
@require_POST
def client_restore(request, client_id):
    """Handle client restoration from soft-delete."""
    client_obj = get_object_or_404(Client.objects.deleted_only(), pk=client_id)
    client_obj.restore()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.RESTORE,
        entity=client_obj,
        entity_id=str(client_obj.pk),
        description=f"استعادة العميل من سلة المحذوفات: {client_obj.full_name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تمت استعادة العميل «{client_obj.full_name}» بنجاح.")
    return redirect("clients:detail", client_id=client_obj.pk)


@login_required
@delete_permission_required
@require_POST
def client_hard_delete(request, client_id):
    """Handle client permanent deletion from trash."""
    client_obj = get_object_or_404(Client.objects.deleted_only(), pk=client_id)
    client_name = client_obj.full_name
    c_pk = client_obj.pk
    client_obj.delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity_type="Client",
        entity_id=str(c_pk),
        description=f"حذف نهائي للعميل «{client_name}» من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم حذف العميل «{client_name}» نهائياً وبشكل قطعي.")
    return redirect("clients:list")


@login_required
@delete_permission_required
@require_POST
def client_bulk_hard_delete(request):
    """Handle bulk permanent deletion of clients from trash."""
    ids = request.POST.getlist("selected_ids") or request.POST.getlist("selected_ids[]")
    if not ids:
        messages.warning(request, "لم يتم تحديد أي عملاء للحذف النهائي.")
        return redirect("clients:list")

    deleted_qs = Client.objects.deleted_only().filter(pk__in=ids)
    count = deleted_qs.count()
    if count > 0:
        deleted_qs.delete()
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            entity_type="Client",
            entity_id=f"Bulk-{count}",
            description=f"حذف نهائي جماعي لـ ({count}) عميل من سلة المحذوفات",
            ip_address=get_client_ip(request),
        )
        messages.success(request, f"تم الحذف النهائي لـ {count} عميل بنجاح من سلة المحذوفات.")
    else:
        messages.warning(request, "لم يتم العثور على العملاء المحددين في سلة المحذوفات.")

    return redirect("clients:list")


@login_required
def client_quick_search(request):
    """
    Fast JSON search endpoint for typeahead/combobox autocomplete for owners/clients.
    Searches across:
    - full_name
    - phone
    - phone_numbers__phone (secondary phones)
    - address
    """
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"results": []})

    qs = (
        Client.objects.alive()
        .prefetch_related("phone_numbers")
        .filter(
            Q(full_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(phone_numbers__phone__icontains=q)
            | Q(address__icontains=q)
        )
        .distinct()
        .order_by("full_name")[:15]
    )

    results = []
    for client in qs:
        sec_phones = [p.phone for p in client.phone_numbers.all() if p.phone]
        results.append({
            "id": client.pk,
            "name": client.full_name,
            "phone": client.phone,
            "secondary_phones": sec_phones,
            "address": client.address or "",
        })

    return JsonResponse({"results": results})

