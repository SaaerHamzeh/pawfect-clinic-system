import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import MedicalRecord, FileAttachment, VaccinationRecord
from .forms import MedicalRecordForm, FileAttachmentForm, VaccinationRecordForm
from apps.patients.models import Animal
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.reminders.models import Reminder
from apps.settings.models import ClinicalVisitType, VaccineCatalogItem, VisitServiceCatalogItem
from apps.audit.models import AuditLog
from apps.core.utils import get_client_ip
from apps.accounts.permissions import (
    can_restore_records,
    can_delete_records,
    restore_permission_required,
    delete_permission_required,
    clinical_edit_permission_required,
    get_visible_clinical_records,
    can_view_other_doctors_records,
    can_view_all_patients,
)


@login_required
def clinical_records_list(request):
    """List clinical visits and medical records with stats, search, and filters."""
    doctor_id = request.GET.get("doctor_id", "all")
    record_type = request.GET.get("record_type", "all")
    vaccine_name = request.GET.get("vaccine_name", "all").strip()
    visit_type = request.GET.get("visit_type", "all")
    filter_deleted = request.GET.get("filter_deleted") or request.GET.get("status") or request.GET.get("deleted") or "active"
    date_filter = request.GET.get("date", "").strip()
    q = request.GET.get("q", "").strip()

    # Base QuerySet respecting visibility permissions
    if filter_deleted == "deleted":
        queryset = MedicalRecord.objects.deleted_only()
    else:
        queryset = MedicalRecord.objects.alive()

    queryset = get_visible_clinical_records(request.user, queryset).select_related(
        "animal", "animal__client", "doctor", "appointment"
    ).prefetch_related("attachments", "services", "vaccination_records__reminder", "reminders")

    # Doctor filter
    if not can_view_other_doctors_records(request.user) and request.user.role == User.Role.VET:
        queryset = queryset.filter(doctor=request.user)
        doctor_id = str(request.user.pk)
    elif doctor_id and doctor_id != "all":
        queryset = queryset.filter(doctor_id=doctor_id)

    # Record type filter
    if record_type and record_type != "all":
        queryset = queryset.filter(record_type=record_type.upper())

    # Vaccination type filter (if record is vaccination or vaccine is chosen)
    if vaccine_name and vaccine_name != "all":
        queryset = queryset.filter(
            Q(vaccine_name__iexact=vaccine_name)
            | Q(vaccination_records__vaccine_name__iexact=vaccine_name)
        ).distinct()

    # Visit type filter (Walk-in vs Appointment)
    if visit_type == "walk_in":
        queryset = queryset.filter(appointment__isnull=True)
    elif visit_type == "appointment":
        queryset = queryset.filter(appointment__isnull=False)

    # Date filter
    if date_filter:
        try:
            parsed_date = datetime.date.fromisoformat(date_filter)
            queryset = queryset.filter(date_time__date=parsed_date)
        except (ValueError, TypeError):
            pass

    # Search query
    if q:
        queryset = queryset.filter(
            Q(animal__name__icontains=q)
            | Q(animal__client__full_name__icontains=q)
            | Q(symptoms__icontains=q)
            | Q(diagnosis__icontains=q)
            | Q(treatment__icontains=q)
            | Q(prescription__icontains=q)
            | Q(notes__icontains=q)
        )

    queryset = queryset.order_by("-date_time")

    # Stats for active records respecting visibility
    today = timezone.localdate()
    all_active = get_visible_clinical_records(request.user, MedicalRecord.objects.alive())
    total_count = all_active.count()
    today_count = all_active.filter(date_time__date=today).count()
    walk_in_count = all_active.filter(appointment__isnull=True).count()
    appointment_count = all_active.filter(appointment__isnull=False).count()

    # Pagination
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)

    # Filter doctors list to Vets only (or just self if cannot view others)
    if not can_view_other_doctors_records(request.user) and request.user.role == User.Role.VET:
        doctors = User.objects.filter(pk=request.user.pk)
    else:
        doctors = User.objects.filter(role=User.Role.VET, is_active=True).order_by("first_name", "username")

    form = MedicalRecordForm(user=request.user)

    # Lookup catalogs for modals
    catalog_services = VisitServiceCatalogItem.objects.filter(is_active=True).order_by("order", "name")
    catalog_vaccines = VaccineCatalogItem.objects.filter(is_active=True).order_by("order", "name")
    visit_types = ClinicalVisitType.objects.filter(is_active=True).order_by("order", "name")

    context = {
        "records": page_obj,
        "page_obj": page_obj,
        "total_count": total_count,
        "today_count": today_count,
        "walk_in_count": walk_in_count,
        "appointment_count": appointment_count,
        "doctors": doctors,
        "form": form,
        "catalog_services": catalog_services,
        "catalog_vaccines": catalog_vaccines,
        "visit_types": visit_types,
        "doctor_id": doctor_id,
        "record_type": record_type,
        "vaccine_name": vaccine_name,
        "visit_type": visit_type,
        "filter_deleted": filter_deleted,
        "status": filter_deleted,
        "date_filter": date_filter,
        "today": today,
        "q": q,
        "is_vet_user": is_vet_user,
        "can_restore": can_restore_records(request.user),
    }
    return render(request, "medical/medical_record.html", context)


def _extract_vaccines_from_request(request):
    """Helper to extract multi-vaccination rows from POST request."""
    vac_names = request.POST.getlist("vac_name[]") or request.POST.getlist("vac_name") or request.POST.getlist("vaccine_name[]") or request.POST.getlist("vaccine_name")
    vac_batches = request.POST.getlist("vac_batch[]") or request.POST.getlist("vac_batch") or request.POST.getlist("batch_number[]") or request.POST.getlist("batch_number")
    vac_next_names = request.POST.getlist("vac_next_name[]") or request.POST.getlist("vac_next_name") or request.POST.getlist("next_vaccine_name[]") or request.POST.getlist("next_vaccine_name")
    vac_next_dates = request.POST.getlist("vac_next_date[]") or request.POST.getlist("vac_next_date") or request.POST.getlist("next_vaccination_date[]") or request.POST.getlist("next_vaccination_date")
    vac_notes = request.POST.getlist("vac_notes[]") or request.POST.getlist("vac_notes")

    import datetime
    vaccines = []
    for i, name in enumerate(vac_names):
        name = name.strip()
        if not name:
            continue
        batch = vac_batches[i].strip() if i < len(vac_batches) else ""
        next_name = vac_next_names[i].strip() if i < len(vac_next_names) else ""
        raw_date = vac_next_dates[i].strip() if i < len(vac_next_dates) else ""
        parsed_date = None
        if raw_date:
            try:
                parsed_date = datetime.date.fromisoformat(raw_date)
            except (ValueError, TypeError):
                parsed_date = None
        notes = vac_notes[i].strip() if i < len(vac_notes) else ""
        vaccines.append({
            "name": name,
            "batch": batch,
            "next_name": next_name,
            "next_date": parsed_date,
            "notes": notes,
        })
    return vaccines


def _sync_medical_record_vaccination_and_reminders(record_obj, vaccines_data=None):
    """
    Cascading smart sync between MedicalRecord, VaccinationRecord(s), and Reminder(s):
    Supports multiple vaccines per visit and distinct next_vaccine_name.
    """
    if vaccines_data is None:
        is_vaccination = (
            record_obj.record_type == MedicalRecord.RecordType.VACCINATION
            or bool(record_obj.vaccine_name)
        )
        if is_vaccination and record_obj.vaccine_name:
            vaccines_data = [{
                "name": record_obj.vaccine_name,
                "batch": record_obj.batch_number or "",
                "next_name": record_obj.next_vaccine_name or "",
                "next_date": record_obj.next_vaccination_date,
                "notes": record_obj.notes or "",
            }]
        else:
            vaccines_data = []

    clean_vaccines = []
    for item in vaccines_data:
        name = (item.get("name") or "").strip()
        if name:
            clean_vaccines.append({
                "name": name,
                "batch": (item.get("batch") or "").strip(),
                "next_name": (item.get("next_name") or "").strip(),
                "next_date": item.get("next_date"),
                "notes": (item.get("notes") or "").strip(),
            })

    existing_vacs = list(record_obj.vaccination_records.alive().order_by("id"))

    if clean_vaccines:
        first_vac = clean_vaccines[0]
        record_obj.vaccine_name = first_vac["name"]
        record_obj.batch_number = first_vac["batch"]
        record_obj.next_vaccine_name = first_vac["next_name"]
        record_obj.next_vaccination_date = first_vac["next_date"]
        record_obj.save(update_fields=["vaccine_name", "batch_number", "next_vaccine_name", "next_vaccination_date", "updated_at"])

        matched_ids = []
        for i, vdata in enumerate(clean_vaccines):
            vac_name = vdata["name"]
            due_date = vdata["next_date"]
            batch_no = vdata["batch"]
            v_notes = vdata["notes"] or (record_obj.notes or "")

            if i < len(existing_vacs):
                vac = existing_vacs[i]
                vac.animal = record_obj.animal
                vac.doctor = record_obj.doctor
                vac.vaccine_name = vac_name
                vac.next_vaccine_name = vdata["next_name"]
                vac.date_administered = record_obj.date_time.date()
                vac.next_due_date = due_date
                vac.batch_number = batch_no
                vac.notes = v_notes
                vac.is_deleted = False
                vac.save()
            else:
                vac = VaccinationRecord.objects.create(
                    animal=record_obj.animal,
                    doctor=record_obj.doctor,
                    medical_record=record_obj,
                    vaccine_name=vac_name,
                    next_vaccine_name=vdata["next_name"],
                    date_administered=record_obj.date_time.date(),
                    next_due_date=due_date,
                    batch_number=batch_no,
                    notes=v_notes,
                )
            matched_ids.append(vac.pk)

            # Reminder synchronization for this specific vaccine
            if due_date:
                batch_str = f" (تشغيلة: {batch_no})" if batch_no else ""
                if vdata["next_name"] and vdata["next_name"] != vac_name:
                    rem_notes = f"الجرعة القادمة المستحقة: لقاح {vdata['next_name']} (بعد إعطاء {vac_name}){batch_str}"
                else:
                    rem_notes = f"الجرعة القادمة المستحقة للقاح {vac_name}{batch_str}"

                existing_rem = vac.reminder
                if existing_rem:
                    existing_rem.animal = record_obj.animal
                    existing_rem.due_date = due_date
                    existing_rem.notes = rem_notes
                    existing_rem.is_deleted = False
                    if existing_rem.status not in (Reminder.Status.CONVERTED, Reminder.Status.COMPLETED):
                        existing_rem.status = Reminder.Status.PENDING
                    existing_rem.save(update_fields=["animal", "due_date", "notes", "status", "is_deleted", "updated_at"])
                else:
                    rem = Reminder.objects.create(
                        animal=record_obj.animal,
                        medical_record=record_obj,
                        reminder_type=Reminder.ReminderType.VACCINATION,
                        due_date=due_date,
                        status=Reminder.Status.PENDING,
                        notes=rem_notes,
                    )
                    vac.reminder = rem
                    vac.save(update_fields=["reminder"])
            else:
                if vac.reminder_id:
                    rem_id = vac.reminder_id
                    vac.reminder = None
                    vac.save(update_fields=["reminder"])
                    Reminder.objects.filter(pk=rem_id, status=Reminder.Status.PENDING).delete()

        # Clean up any leftover vaccination records that were removed
        for vac in existing_vacs:
            if vac.pk not in matched_ids:
                if vac.reminder_id:
                    rem_id = vac.reminder_id
                    vac.reminder = None
                    vac.save(update_fields=["reminder"])
                    Reminder.objects.filter(pk=rem_id, status=Reminder.Status.PENDING).delete()
                vac.soft_delete()

    else:
        # Not a vaccination visit / all vaccines removed: clean up
        for vac in record_obj.vaccination_records.all():
            if vac.reminder_id:
                rem_id = vac.reminder_id
                vac.reminder = None
                vac.save(update_fields=["reminder"])
                Reminder.objects.filter(pk=rem_id, status=Reminder.Status.PENDING).delete()
            vac.soft_delete()
        record_obj.reminders.filter(
            reminder_type=Reminder.ReminderType.VACCINATION,
            status=Reminder.Status.PENDING
        ).delete()


@login_required
@clinical_edit_permission_required
@require_POST
def clinical_record_create(request):
    """Create a clinical medical record with multi-services, vaccination integration, doctor-only reminder, file attachment, appointment completion, and weight sync."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)

    form = MedicalRecordForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        record_obj = form.save(commit=False)
        if is_vet_user or not record_obj.doctor_id:
            record_obj.doctor = request.user
        record_obj.save()

        # Update animal's latest weight if recorded
        if record_obj.weight_at_visit:
            record_obj.animal.weight = record_obj.weight_at_visit
            record_obj.animal.save(update_fields=["weight", "updated_at"])

        # Mark linked appointment as COMPLETED if present
        if record_obj.appointment:
            record_obj.appointment.status = Appointment.Status.COMPLETED
            record_obj.appointment.save(update_fields=["status", "updated_at"])

        # Multi-services management
        service_names = request.POST.getlist("service_name") or request.POST.getlist("services[]")
        service_notes = request.POST.getlist("service_notes") or request.POST.getlist("service_notes[]")
        for i, sname in enumerate(service_names):
            sname = sname.strip()
            if sname:
                snotes = service_notes[i].strip() if i < len(service_notes) else ""
                from .models import VisitService
                VisitService.objects.create(
                    medical_record=record_obj,
                    name=sname,
                    notes=snotes,
                )

        # Cascading vaccination & reminder synchronization
        req_vaccines = _extract_vaccines_from_request(request)
        _sync_medical_record_vaccination_and_reminders(record_obj, vaccines_data=req_vaccines if req_vaccines else None)

        # Doctor-only reminder creation from visit form
        create_rem = form.cleaned_data.get("create_reminder")
        if create_rem:
            if request.user.role == User.Role.VET or request.user.is_superuser or request.user.role == User.Role.ADMIN:
                rem_type = form.cleaned_data.get("reminder_type") or Reminder.ReminderType.FOLLOW_UP
                rem_due = form.cleaned_data.get("reminder_due_date")
                rem_notes = form.cleaned_data.get("reminder_notes") or ""
                if rem_due:
                    Reminder.objects.create(
                        animal=record_obj.animal,
                        medical_record=record_obj,
                        reminder_type=rem_type,
                        due_date=rem_due,
                        status=Reminder.Status.PENDING,
                        notes=rem_notes or f"تذكير متابعة للزيارة السريرية في {record_obj.date_time.strftime('%Y-%m-%d')}",
                    )

        # Handle attachment if uploaded in form
        attachment_file = request.FILES.get("attachment_file")
        if attachment_file:
            attachment_obj = FileAttachment.objects.create(
                animal=record_obj.animal,
                medical_record=record_obj,
                file=attachment_file,
                uploaded_by=request.user,
            )
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.CREATE,
                entity=attachment_obj,
                entity_id=str(attachment_obj.pk),
                description=f"رفع مرفق طبي ({attachment_obj.file_name} - {attachment_obj.file_size_display}) للزيارة السريرية للمريض {record_obj.animal.name}",
                ip_address=get_client_ip(request),
            )

        # Audit Log
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity=record_obj,
            entity_id=str(record_obj.pk),
            description=(
                f"تسجيل زيارة سريرية للمريض {record_obj.animal.name} "
                f"مع د. {record_obj.doctor.get_full_name() or record_obj.doctor.username} "
                f"(التشخيص: {record_obj.diagnosis or record_obj.get_record_type_display()})"
            ),
            ip_address=get_client_ip(request),
        )

        msg = f"تم توثيق الزيارة السريرية بنجاح للمريض «{record_obj.animal.name}»."
        messages.success(request, msg)
        return_url = request.POST.get("return_to") or reverse("clinical:list")
        if is_ajax:
            return JsonResponse({"success": True, "redirect_url": return_url, "message": msg})
    else:
        error_list = [err for sublist in form.errors.values() for err in sublist]
        error_msg = "تعذر تسجيل الزيارة: " + "; ".join(error_list) if error_list else "يرجى التحقق من صحة البيانات المدخلة."
        if is_ajax:
            return JsonResponse({
                "success": False,
                "error": error_msg,
                "field_errors": {k: [str(e) for e in v] for k, v in form.errors.items()}
            }, status=400)
        messages.error(request, error_msg)

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("clinical:list")


@login_required
def clinical_record_detail(request, record_id):
    """View single clinical visit detail with services and attachments."""
    record_obj = get_object_or_404(
        MedicalRecord.all_objects.select_related("animal", "animal__client", "doctor", "appointment").prefetch_related("attachments", "services"),
        pk=record_id,
    )
    if not can_view_other_doctors_records(request.user) and record_obj.doctor_id != request.user.pk:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("عذراً، هذا السجل الطبي يخص طبيباً آخر وليس لديك صلاحية الاطلاع عليه.")

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "id": record_obj.pk,
            "animal_name": record_obj.animal.name,
            "doctor_name": record_obj.doctor.get_full_name() or record_obj.doctor.username,
            "date_time": record_obj.date_time.isoformat(),
            "diagnosis": record_obj.diagnosis,
            "treatment": record_obj.treatment,
            "symptoms": record_obj.symptoms,
            "notes": record_obj.notes,
        })
    return redirect("patients:detail", patient_id=record_obj.animal_id)


@login_required
@clinical_edit_permission_required
@require_POST
def clinical_record_update(request, record_id):
    """Update medical record details and its services."""
    record_obj = get_object_or_404(MedicalRecord.all_objects, pk=record_id)
    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)

    if is_vet_user and record_obj.doctor_id != request.user.pk:
        messages.error(request, "ليس لديك صلاحية تعديل سجل طبي مسجل لطبيب آخر.")
        return redirect("clinical:list")

    form = MedicalRecordForm(request.POST, request.FILES, instance=record_obj, user=request.user)
    if form.is_valid():
        record_obj = form.save()

        # Update animal's weight
        if record_obj.weight_at_visit:
            record_obj.animal.weight = record_obj.weight_at_visit
            record_obj.animal.save(update_fields=["weight", "updated_at"])

        # Mark linked appointment as COMPLETED if present
        if record_obj.appointment:
            record_obj.appointment.status = Appointment.Status.COMPLETED
            record_obj.appointment.save(update_fields=["status", "updated_at"])

        # Update services
        service_names = request.POST.getlist("service_name") or request.POST.getlist("services[]")
        service_notes = request.POST.getlist("service_notes") or request.POST.getlist("service_notes[]")
        if service_names:
            from .models import VisitService
            record_obj.services.all().delete()
            for i, sname in enumerate(service_names):
                sname = sname.strip()
                if sname:
                    snotes = service_notes[i].strip() if i < len(service_notes) else ""
                    VisitService.objects.create(
                        medical_record=record_obj,
                        name=sname,
                        notes=snotes,
                    )

        # Cascading vaccination & reminder synchronization
        req_vaccines = _extract_vaccines_from_request(request)
        has_vac_payload = any(k in request.POST for k in ["vac_name[]", "vac_name", "vaccine_name[]"])
        _sync_medical_record_vaccination_and_reminders(record_obj, vaccines_data=req_vaccines if (req_vaccines or has_vac_payload) else None)

        # Doctor reminder creation on update if requested
        create_rem = form.cleaned_data.get("create_reminder")
        if create_rem:
            if request.user.role == User.Role.VET or request.user.is_superuser or request.user.role == User.Role.ADMIN:
                rem_type = form.cleaned_data.get("reminder_type") or Reminder.ReminderType.FOLLOW_UP
                rem_due = form.cleaned_data.get("reminder_due_date")
                rem_notes = form.cleaned_data.get("reminder_notes") or ""
                if rem_due:
                    Reminder.objects.create(
                        animal=record_obj.animal,
                        medical_record=record_obj,
                        reminder_type=rem_type,
                        due_date=rem_due,
                        status=Reminder.Status.PENDING,
                        notes=rem_notes or f"تذكير متابعة للزيارة السريرية في {record_obj.date_time.strftime('%Y-%m-%d')}",
                    )

        # Handle attachment if uploaded in update form
        attachment_file = request.FILES.get("attachment_file")
        if attachment_file:
            attachment_obj = FileAttachment.objects.create(
                animal=record_obj.animal,
                medical_record=record_obj,
                file=attachment_file,
                uploaded_by=request.user,
            )
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.CREATE,
                entity=attachment_obj,
                entity_id=str(attachment_obj.pk),
                description=f"رفع مرفق طبي ({attachment_obj.file_name} - {attachment_obj.file_size_display}) للزيارة السريرية للمريض {record_obj.animal.name}",
                ip_address=get_client_ip(request),
            )

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity=record_obj,
            entity_id=str(record_obj.pk),
            description=f"تعديل السجل الطبي #{record_obj.pk} للمريض {record_obj.animal.name}",
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تم تحديث السجل الطبي للمريض «{record_obj.animal.name}» بنجاح.")
    else:
        error_list = [err for sublist in form.errors.values() for err in sublist]
        error_msg = "فشل تحديث السجل الطبي: " + "; ".join(error_list) if error_list else "يرجى التحقق من صحة البيانات المدخلة."
        messages.error(request, error_msg)

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("clinical:list")


@login_required
@delete_permission_required
@require_POST
def clinical_record_delete(request, record_id):
    """Soft delete a medical record."""
    record_obj = get_object_or_404(MedicalRecord.objects.alive(), pk=record_id)
    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)

    if is_vet_user and record_obj.doctor_id != request.user.pk:
        messages.error(request, "ليس لديك صلاحية حذف سجل طبي مسجل لطبيب آخر.")
        return redirect("clinical:list")

    record_obj.soft_delete()

    # Soft-delete linked pending reminders and vaccination records
    record_obj.reminders.filter(status=Reminder.Status.PENDING, is_deleted=False).update(is_deleted=True)
    record_obj.vaccination_records.filter(is_deleted=False).update(is_deleted=True)

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity=record_obj,
        entity_id=str(record_obj.pk),
        description=f"حذف السجل الطبي #{record_obj.pk} مؤقتاً للمريض {record_obj.animal.name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم نقل السجل الطبي إلى سلة المحذوفات.")
    return redirect("clinical:list")


@login_required
@restore_permission_required
@require_POST
def clinical_record_restore(request, record_id):
    """Restore a soft-deleted medical record."""
    record_obj = get_object_or_404(MedicalRecord.objects.deleted_only(), pk=record_id)
    record_obj.restore()

    # Restore linked vaccination records and pending reminders
    record_obj.vaccination_records.filter(is_deleted=True).update(is_deleted=False)
    record_obj.reminders.filter(is_deleted=True, status=Reminder.Status.PENDING).update(is_deleted=False)

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.RESTORE,
        entity=record_obj,
        entity_id=str(record_obj.pk),
        description=f"استعادة السجل الطبي #{record_obj.pk} من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تمت استعادة السجل الطبي بنجاح.")
    return redirect("clinical:list")


@login_required
@delete_permission_required
@require_POST
def clinical_record_hard_delete(request, record_id):
    """Permanently delete a medical record and its physical attachments from trash."""
    record_obj = get_object_or_404(MedicalRecord.objects.deleted_only(), pk=record_id)
    rec_pk = record_obj.pk
    animal_name = record_obj.animal.name if record_obj.animal else "غير محدد"

    # Delete physical attachment files if any
    for attachment in record_obj.attachments.all():
        if attachment.file:
            try:
                attachment.file.delete(save=False)
            except Exception:
                pass

    record_obj.delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity_type="MedicalRecord",
        entity_id=str(rec_pk),
        description=f"حذف نهائي للسجل الطبي #{rec_pk} للمريض {animal_name} من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم حذف السجل الطبي #{rec_pk} ومرفقاته نهائياً وبشكل قطعي.")
    return redirect("clinical:list")


@login_required
@delete_permission_required
@require_POST
def clinical_record_bulk_hard_delete(request):
    """Bulk permanently delete selected medical records from trash."""
    ids = request.POST.getlist("selected_ids") or request.POST.getlist("selected_ids[]")
    if not ids:
        messages.warning(request, "لم يتم تحديد أي سجلات طبية للحذف النهائي.")
        return redirect("clinical:list")

    deleted_qs = MedicalRecord.objects.deleted_only().filter(pk__in=ids)
    count = deleted_qs.count()
    if count > 0:
        for record in deleted_qs:
            for attachment in record.attachments.all():
                if attachment.file:
                    try:
                        attachment.file.delete(save=False)
                    except Exception:
                        pass
        deleted_qs.delete()
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            entity_type="MedicalRecord",
            entity_id=f"Bulk-{count}",
            description=f"حذف نهائي جماعي لـ ({count}) سجل طبي من سلة المحذوفات",
            ip_address=get_client_ip(request),
        )
        messages.success(request, f"تم الحذف النهائي لـ {count} سجل طبي بنجاح من سلة المحذوفات.")
    else:
        messages.warning(request, "لم يتم العثور على السجلات الطبية المحددة في سلة المحذوفات.")

    return redirect("clinical:list")



@login_required
@clinical_edit_permission_required
@require_POST
def attachment_upload(request):
    """Upload a file attachment for an animal or medical visit (max 15MB)."""
    form = FileAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment_obj = form.save(commit=False)
        attachment_obj.uploaded_by = request.user
        attachment_obj.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity=attachment_obj,
            entity_id=str(attachment_obj.pk),
            description=(
                f"رفع مرفق طبي ({attachment_obj.file_name} - {attachment_obj.file_size_display}) "
                f"للمريض {attachment_obj.animal.name}"
            ),
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تم رفع المرفق الطبي «{attachment_obj.file_name}» بنجاح.")
    else:
        error_msg = "تعذر رفع الملف: " + "; ".join(
            [f"{err[0]}" for err in form.errors.values()]
        )
        messages.error(request, error_msg)

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("clinical:list")


@login_required
@delete_permission_required
@require_POST
def attachment_delete(request, attachment_id):
    """Soft delete an attachment (non-admin can only delete files they uploaded)."""
    attachment_obj = get_object_or_404(FileAttachment.objects.alive(), pk=attachment_id)
    is_admin = request.user.is_superuser or getattr(request.user, "is_admin_user", False) or request.user.role == User.Role.ADMIN

    if not is_admin and attachment_obj.uploaded_by_id != request.user.pk:
        messages.error(request, "ليس لديك صلاحية حذف مرفق طبي تم رفعه بواسطة مستخدم آخر.")
        return_to = request.POST.get("return_to")
        if return_to:
            return redirect(return_to)
        return redirect("clinical:list")

    attachment_obj.soft_delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity=attachment_obj,
        entity_id=str(attachment_obj.pk),
        description=f"حذف المرفق الطبي ({attachment_obj.file_name}) للمريض {attachment_obj.animal.name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, "تم حذف المرفق الطبي.")
    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("clinical:list")


@login_required
@clinical_edit_permission_required
@require_POST
def vaccination_create(request):
    """Create a vaccination record with automated future reminder generation."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    form = VaccinationRecordForm(request.POST)
    if form.is_valid():
        vaccination_obj = form.save(commit=False)

        # If next_due_date is set, automatically generate Reminder
        if vaccination_obj.next_due_date:
            reminder_obj = Reminder.objects.create(
                animal=vaccination_obj.animal,
                reminder_type=Reminder.ReminderType.VACCINATION,
                due_date=vaccination_obj.next_due_date,
                status=Reminder.Status.PENDING,
                notes=f"الجرعة القادمة المستحقة للقاح {vaccination_obj.vaccine_name} (تشغيلة: {vaccination_obj.batch_number or '-'})",
            )
            vaccination_obj.reminder = reminder_obj

        vaccination_obj.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity=vaccination_obj,
            entity_id=str(vaccination_obj.pk),
            description=(
                f"تسجيل تطعيم ({vaccination_obj.vaccine_name}) للمريض {vaccination_obj.animal.name} "
                f"بإشراف د. {vaccination_obj.doctor.get_full_name() or vaccination_obj.doctor.username}"
                + (f" وتوليد تذكير للجرعة القادمة في {vaccination_obj.next_due_date}" if vaccination_obj.next_due_date else "")
            ),
            ip_address=get_client_ip(request),
        )

        msg = f"تم توثيق التطعيم «{vaccination_obj.vaccine_name}» بنجاح."
        messages.success(request, msg)
        return_url = request.POST.get("return_to") or reverse("clinical:list")
        if is_ajax:
            return JsonResponse({"success": True, "redirect_url": return_url, "message": msg})
    else:
        error_list = [err for sublist in form.errors.values() for err in sublist]
        error_msg = "تعذر تسجيل التطعيم: " + "; ".join(error_list) if error_list else "يرجى التحقق من صحة البيانات المدخلة."
        if is_ajax:
            return JsonResponse({
                "success": False,
                "error": error_msg,
                "field_errors": {k: [str(e) for e in v] for k, v in form.errors.items()}
            }, status=400)
        messages.error(request, error_msg)

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("clinical:list")


@login_required
@delete_permission_required
@require_POST
def vaccination_delete(request, vaccination_id):
    """Soft delete a vaccination record."""
    vaccination_obj = get_object_or_404(VaccinationRecord.objects.alive(), pk=vaccination_id)
    vaccination_obj.soft_delete()

    # Soft-delete linked pending reminder
    if vaccination_obj.reminder and vaccination_obj.reminder.status == Reminder.Status.PENDING and not vaccination_obj.reminder.is_deleted:
        vaccination_obj.reminder.soft_delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity=vaccination_obj,
        entity_id=str(vaccination_obj.pk),
        description=f"حذف سجل التطعيم ({vaccination_obj.vaccine_name}) للمريض {vaccination_obj.animal.name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, "تم نقل سجل التطعيم إلى سلة المحذوفات.")
    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("clinical:list")


@login_required
def today_doctor_appointments_api(request):
    """
    JSON API returning active appointments for a specific Vet/Doctor on TODAY's date only.
    Used for streamlined, uncluttered appointment linking during clinical visit creation.
    """
    doctor_id = request.GET.get("doctor_id")
    today = timezone.localdate()

    queryset = Appointment.objects.alive().filter(
        date=today
    ).exclude(
        status=Appointment.Status.CANCELLED
    ).select_related("animal", "animal__client", "doctor")

    if doctor_id:
        queryset = queryset.filter(doctor_id=doctor_id)

    appointments_list = []
    for appt in queryset.order_by("time"):
        animal = appt.animal
        client = animal.client if animal else None
        time_24 = appt.time.strftime("%H:%M") if appt.time else ""
        
        display_parts = [f"موعد الساعة {time_24}"]
        if animal:
            display_parts.append(f"{animal.name} (#{animal.animal_id})")
        if client and client.full_name:
            display_parts.append(f"المالك: {client.full_name}")

        appointments_list.append({
            "id": appt.id,
            "time": time_24,
            "display": " - ".join(display_parts),
            "animal_id": animal.id if animal else None,
            "animal_name": animal.name if animal else "",
            "animal_code": animal.animal_id if animal else "",
            "species_display": animal.get_species_display() if animal else "",
            "breed": animal.breed if animal else "",
            "client_name": client.full_name if client else "",
            "client_phone": client.phone if client else "",
        })

    return JsonResponse({"success": True, "appointments": appointments_list})

