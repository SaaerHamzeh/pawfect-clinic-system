from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

import json
from .models import Animal
from .forms import AnimalForm
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.settings.models import (
    AnimalSpecies,
    AnimalBreed,
    ClinicalVisitType,
    VaccineCatalogItem,
    VisitServiceCatalogItem,
    AppointmentTypeConfig,
)
from django.core.exceptions import PermissionDenied
from apps.core.utils import get_client_ip
from apps.accounts.permissions import (
    can_restore_records,
    can_delete_records,
    restore_permission_required,
    delete_permission_required,
    client_manage_permission_required,
    get_visible_patients,
    can_view_other_doctors_records,
    can_manage_appointments,
)


@login_required
def patients(request):
    """List animals/patients with search, species filtering, sorting, and stats."""
    status = request.GET.get("status", "active")
    species = request.GET.get("species", "all")
    q = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "newest")

    # Base QuerySet respecting Vet visibility rules
    if status == "deleted":
        base_qs = Animal.objects.deleted_only()
    else:
        base_qs = Animal.objects.alive()

    queryset = get_visible_patients(request.user, base_qs).select_related("client")

    # Species filter
    if species and species != "all":
        queryset = queryset.filter(species=species.upper())

    # Search filter
    if q:
        queryset = queryset.filter(
            Q(animal_id__icontains=q)
            | Q(name__icontains=q)
            | Q(breed__icontains=q)
            | Q(color__icontains=q)
            | Q(identification__icontains=q)
            | Q(notes__icontains=q)
            | Q(client__full_name__icontains=q)
            | Q(client__phone__icontains=q)
        )

    # Sorting
    if sort_by == "name":
        queryset = queryset.order_by("name")
    elif sort_by == "client":
        queryset = queryset.order_by("client__full_name", "-created_at")
    elif sort_by == "weight":
        queryset = queryset.order_by("-weight")
    else:  # newest
        queryset = queryset.order_by("-created_at")

    # Stats (respecting visible patients)
    all_visible = get_visible_patients(request.user, Animal.objects.alive())
    total_patients_count = all_visible.count()
    dogs_count = all_visible.filter(species=Animal.Species.DOG).count()
    cats_count = all_visible.filter(species=Animal.Species.CAT).count()
    others_count = all_visible.exclude(species__in=[Animal.Species.DOG, Animal.Species.CAT]).count()

    # Pagination
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    form = AnimalForm()

    context = {
        "patients": page_obj,
        "page_obj": page_obj,
        "total_patients_count": total_patients_count,
        "dogs_count": dogs_count,
        "cats_count": cats_count,
        "others_count": others_count,
        "form": form,
        "status": status,
        "species_filter": species,
        "species_list": AnimalSpecies.objects.filter(is_active=True).order_by("order", "name"),
        "species_breeds_json": json.dumps(AnimalBreed.get_species_breeds_map(), ensure_ascii=False),
        "q": q,
        "sort_by": sort_by,
        "can_restore": can_restore_records(request.user),
    }
    return render(request, "patients/patients.html", context)


@login_required
def patient_detail(request, patient_id):
    """View patient medical profile, owner info, and medical history."""
    visible_qs = get_visible_patients(request.user, Animal.all_objects)
    if not visible_qs.filter(pk=patient_id).exists():
        raise PermissionDenied("عذراً، ليس لديك صلاحية استعراض ملف هذا المريض حيث أنه غير مخصص لك ولا تملك صلاحية رؤية مرضى الأطباء الآخرين.")

    patient_obj = get_object_or_404(
        Animal.all_objects.select_related("client"), pk=patient_id
    )

    # Clinical records for timeline
    medical_records = (
        patient_obj.medical_records.filter(is_deleted=False)
        .select_related("doctor", "appointment")
        .prefetch_related("attachments", "services", "vaccination_records__reminder", "reminders")
        .order_by("-date_time")
    )

    if not can_view_other_doctors_records(request.user):
        medical_records = medical_records.filter(doctor=request.user)

    # Compute timeline clinical statistics
    total_visits_count = medical_records.count()
    records_list = list(medical_records)
    total_services_count = sum(len(rec.services.all()) for rec in records_list)
    latest_visit = records_list[0] if records_list else None
    first_visit = records_list[-1] if records_list else None
    
    weight_diff = None
    if latest_visit and first_visit and len(records_list) > 1:
        if latest_visit.weight_at_visit and first_visit.weight_at_visit:
            diff = float(latest_visit.weight_at_visit) - float(first_visit.weight_at_visit)
            weight_diff = round(diff, 2)

    # Reminders
    reminders = patient_obj.reminders.filter(is_deleted=False).order_by("due_date")

    # Vaccinations
    vaccinations = patient_obj.vaccination_records.filter(is_deleted=False).select_related("doctor").order_by("-date_administered")

    # File Attachments
    attachments = patient_obj.file_attachments.filter(is_deleted=False).select_related("uploaded_by", "medical_record").order_by("-created_at")

    # Doctors for modals (Vets only)
    doctors = User.objects.filter(role=User.Role.VET, is_active=True).order_by("first_name", "username")

    # Lookup catalogs for modals
    catalog_services = VisitServiceCatalogItem.objects.filter(is_active=True).order_by("order", "name")
    catalog_vaccines = VaccineCatalogItem.objects.filter(is_active=True).order_by("order", "name")
    visit_types = ClinicalVisitType.objects.filter(is_active=True).order_by("order", "name")
    appointment_types = AppointmentTypeConfig.objects.filter(is_active=True).order_by("order", "name")

    edit_form = AnimalForm(instance=patient_obj)

    # Appointments for linking in visit create/edit
    patient_appointments = (
        patient_obj.appointments.alive()
        .exclude(status=Appointment.Status.CANCELLED)
        .select_related("doctor")
        .order_by("-date", "-time")
    )
    if not can_view_other_doctors_records(request.user):
        patient_appointments = patient_appointments.filter(doctor=request.user)

    context = {
        "patient": patient_obj,
        "medical_records": medical_records,
        "total_visits_count": total_visits_count,
        "total_services_count": total_services_count,
        "latest_visit": latest_visit,
        "weight_diff": weight_diff,
        "reminders": reminders,
        "vaccinations": vaccinations,
        "attachments": attachments,
        "doctors": doctors,
        "patient_appointments": patient_appointments,
        "edit_form": edit_form,
        "species_breeds_json": json.dumps(AnimalBreed.get_species_breeds_map(), ensure_ascii=False),
        "catalog_services": catalog_services,
        "catalog_vaccines": catalog_vaccines,
        "visit_types": visit_types,
        "appointment_types": appointment_types,
        "can_restore": can_restore_records(request.user),
        "can_manage_appointments": can_manage_appointments(request.user),
    }
    return render(request, "patients/patients_details.html", context)


@login_required
@client_manage_permission_required
@require_POST
def patient_create(request):
    """Handle patient creation and audit logging."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    form = AnimalForm(request.POST, request.FILES)
    if form.is_valid():
        patient_obj = form.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity=patient_obj,
            entity_id=str(patient_obj.pk),
            description=f"إضافة مريض جديد: {patient_obj.name} ({patient_obj.get_species_display()}) للمالك {patient_obj.client.full_name}",
            ip_address=get_client_ip(request),
        )

        msg = f"تمت إضافة المريض «{patient_obj.name}» بنجاح."
        messages.success(request, msg)
        
        return_url = request.POST.get("return_to") or reverse("patients:detail", kwargs={"patient_id": patient_obj.pk})
        if is_ajax:
            return JsonResponse({"success": True, "redirect_url": return_url, "message": msg})

        if request.POST.get("return_to"):
            return redirect(request.POST.get("return_to"))
        return redirect("patients:detail", patient_id=patient_obj.pk)

    error_list = [err for sublist in form.errors.values() for err in sublist]
    error_msg = "; ".join(error_list) if error_list else "يرجى مراجعة الحقول المطلوبة والتأكد من صحتها."
    is_duplicate = getattr(form, "has_duplicate_name_warning", False)
    if is_ajax:
        return JsonResponse({
            "success": False,
            "error": error_msg,
            "duplicate_warning": is_duplicate,
            "duplicate_field": "name" if is_duplicate else None,
            "field_errors": {k: [str(e) for e in v] for k, v in form.errors.items()}
        }, status=400)

    messages.error(request, error_msg)
    return_url = request.POST.get("return_to")
    if return_url:
        return redirect(return_url)
    return redirect("patients:list")


@login_required
@client_manage_permission_required
@require_POST
def patient_update(request, patient_id):
    """Handle patient update and audit logging."""
    patient_obj = get_object_or_404(Animal.all_objects, pk=patient_id)
    form = AnimalForm(request.POST, request.FILES, instance=patient_obj)
    if form.is_valid():
        patient_obj = form.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity=patient_obj,
            entity_id=str(patient_obj.pk),
            description=f"تعديل بيانات المريض: {patient_obj.name}",
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تم تحديث بيانات المريض «{patient_obj.name}» بنجاح.")
        return redirect("patients:detail", patient_id=patient_obj.pk)

    messages.error(request, "فشل تحديث البيانات. يرجى مراجعة الحقول.")
    return redirect("patients:detail", patient_id=patient_obj.pk)


@login_required
@require_POST
def patient_update_photo(request, patient_id):
    """
    Dedicated endpoint for tablet and mobile camera/gallery photo upload or deletion.
    """
    from apps.accounts.permissions import can_manage_clients, is_vet, is_admin
    user = request.user
    if not (can_manage_clients(user) or is_vet(user) or is_admin(user)):
        return JsonResponse({"success": False, "error": "ليس لديك الصلاحية لتعديل صورة المريض."}, status=403)

    patient_obj = get_object_or_404(Animal.all_objects, pk=patient_id)
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    # 1. Handle deletion of current photo
    if request.POST.get("delete_photo") == "true":
        if patient_obj.photo:
            try:
                patient_obj.photo.delete(save=False)
            except Exception:
                pass
            patient_obj.photo = None
            patient_obj.save(update_fields=["photo", "updated_at"])

            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                entity=patient_obj,
                entity_id=str(patient_obj.pk),
                description=f"حذف صورة المريض: {patient_obj.name}",
                ip_address=get_client_ip(request),
            )
        messages.success(request, f"تم حذف صورة المريض «{patient_obj.name}» بنجاح.")
        if is_ajax:
            return JsonResponse({"success": True, "message": "تم حذف الصورة بنجاح."})
        return redirect("patients:detail", patient_id=patient_obj.pk)

    # 2. Handle photo upload (Camera or Gallery)
    photo_file = request.FILES.get("photo")
    if not photo_file:
        if is_ajax:
            return JsonResponse({"success": False, "error": "لم يتم اختيار أو التقاط أي صورة."}, status=400)
        messages.error(request, "لم يتم اختيار أو التقاط أي صورة.")
        return redirect("patients:detail", patient_id=patient_obj.pk)

    # Max size validation: 15 MB per requirements
    if photo_file.size > 15 * 1024 * 1024:
        err = "حجم الصورة يتجاوز الحد الأقصى المسموح (15 ميغابايت)."
        if is_ajax:
            return JsonResponse({"success": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect("patients:detail", patient_id=patient_obj.pk)

    # Content type validation
    if hasattr(photo_file, "content_type") and not photo_file.content_type.startswith("image/"):
        err = "الملف المرفوع ليس ملف صورة صالح."
        if is_ajax:
            return JsonResponse({"success": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect("patients:detail", patient_id=patient_obj.pk)

    # Delete old photo file if exists
    if patient_obj.photo:
        try:
            patient_obj.photo.delete(save=False)
        except Exception:
            pass

    patient_obj.photo = photo_file
    patient_obj.save(update_fields=["photo", "updated_at"])

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.UPDATE,
        entity=patient_obj,
        entity_id=str(patient_obj.pk),
        description=f"تحديث صورة المريض: {patient_obj.name} عبر الكاميرا/المعرض",
        ip_address=get_client_ip(request),
    )

    msg = f"تم تحديث صورة المريض «{patient_obj.name}» بنجاح."
    messages.success(request, msg)
    if is_ajax:
        return JsonResponse({
            "success": True,
            "photo_url": patient_obj.photo.url if patient_obj.photo else "",
            "message": msg
        })
    return redirect("patients:detail", patient_id=patient_obj.pk)


@login_required
@delete_permission_required
@require_POST
def patient_delete(request, patient_id):
    """Handle patient soft-deletion."""
    patient_obj = get_object_or_404(Animal.objects.alive(), pk=patient_id)
    patient_name = patient_obj.name
    patient_obj.soft_delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity=patient_obj,
        entity_id=str(patient_obj.pk),
        description=f"حذف المريض مؤقتاً (نقل للسلة): {patient_name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم نقل المريض «{patient_name}» إلى سلة المحذوفات.")
    return redirect("patients:list")


@login_required
@restore_permission_required
@require_POST
def patient_restore(request, patient_id):
    """Handle patient restoration from soft-delete."""
    patient_obj = get_object_or_404(Animal.objects.deleted_only(), pk=patient_id)
    patient_obj.restore()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.RESTORE,
        entity=patient_obj,
        entity_id=str(patient_obj.pk),
        description=f"استعادة المريض من سلة المحذوفات: {patient_obj.name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تمت استعادة المريض «{patient_obj.name}» بنجاح.")
    return redirect("patients:detail", patient_id=patient_obj.pk)


@login_required
@delete_permission_required
@require_POST
def patient_hard_delete(request, patient_id):
    """Handle patient permanent deletion from trash."""
    patient_obj = get_object_or_404(Animal.objects.deleted_only(), pk=patient_id)
    patient_name = patient_obj.name
    p_pk = patient_obj.pk

    if patient_obj.photo:
        try:
            patient_obj.photo.delete(save=False)
        except Exception:
            pass

    patient_obj.delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity_type="Animal",
        entity_id=str(p_pk),
        description=f"حذف نهائي للمريض «{patient_name}» من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم حذف المريض «{patient_name}» نهائياً وبشكل قطعي.")
    return redirect("patients:list")


@login_required
@delete_permission_required
@require_POST
def patient_bulk_hard_delete(request):
    """Handle bulk permanent deletion of patients from trash."""
    ids = request.POST.getlist("selected_ids") or request.POST.getlist("selected_ids[]")
    if not ids:
        messages.warning(request, "لم يتم تحديد أي مرضى للحذف النهائي.")
        return redirect("patients:list")

    deleted_qs = Animal.objects.deleted_only().filter(pk__in=ids)
    count = deleted_qs.count()
    if count > 0:
        for patient in deleted_qs:
            if patient.photo:
                try:
                    patient.photo.delete(save=False)
                except Exception:
                    pass
        deleted_qs.delete()
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            entity_type="Animal",
            entity_id=f"Bulk-{count}",
            description=f"حذف نهائي جماعي لـ ({count}) مريض من سلة المحذوفات",
            ip_address=get_client_ip(request),
        )
    return redirect("patients:list")


@login_required
def patient_quick_search(request):
    """
    Fast JSON search endpoint for typeahead/combobox autocomplete.
    Searches across:
    - animal_id (#ID)
    - name (patient name)
    - client__full_name (owner name)
    - client__phone (owner phone)
    - identification (microchip / collar tag)
    """
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"results": []})

    clean_q = q.lstrip("#").strip()

    qs = (
        Animal.objects.alive()
        .select_related("client")
        .filter(
            Q(animal_id__icontains=clean_q)
            | Q(name__icontains=q)
            | Q(client__full_name__icontains=q)
            | Q(client__phone__icontains=clean_q)
            | Q(identification__icontains=q)
        )
        .order_by("name")[:15]
    )

    results = []
    for animal in qs:
        results.append({
            "id": animal.pk,
            "animal_id": animal.animal_id or f"{animal.pk:07d}",
            "name": animal.name,
            "species": animal.species,
            "species_display": animal.get_species_display(),
            "breed": animal.breed or "",
            "client_name": animal.client.full_name if animal.client else "-",
            "client_phone": animal.client.phone if animal.client else "",
        })

    return JsonResponse({"results": results})

