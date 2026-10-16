import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from apps.core.utils import get_client_ip

from .models import Appointment
from .forms import AppointmentForm
from apps.accounts.models import User
from apps.patients.models import Animal
from apps.audit.models import AuditLog
from apps.settings.models import AppointmentTypeConfig, VaccineCatalogItem
from apps.accounts.permissions import (
    can_restore_records,
    can_delete_records,
    restore_permission_required,
    delete_permission_required,
    appointment_manage_permission_required,
    can_view_all_patients,
)


@login_required
def appointments(request):
    """Main appointments view supporting List and Calendar views with search, date range filters, and stats."""
    status = request.GET.get("status", "all")
    appointment_type = request.GET.get("appointment_type", "all")
    vaccine_name = request.GET.get("vaccine_name", "all").strip()
    filter_deleted = request.GET.get("filter_deleted") or request.GET.get("deleted") or "active"
    doctor_id = request.GET.get("doctor_id", "all")
    date_filter = request.GET.get("date", "").strip() or request.GET.get("date_filter", "").strip()
    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()
    q = request.GET.get("q", "").strip()

    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)

    # Base Queryset
    if filter_deleted == "deleted":
        queryset = Appointment.objects.deleted_only()
    else:
        queryset = Appointment.objects.alive()

    queryset = queryset.select_related("animal", "animal__client", "doctor", "created_by")

    can_view_all = can_view_all_patients(request.user)

    # If the user is a Vet without view_all_patients, strictly restrict view to their own appointments
    if is_vet_user and not can_view_all:
        queryset = queryset.filter(doctor=request.user)
        doctor_id = str(request.user.pk)
    elif doctor_id and doctor_id != "all":
        queryset = queryset.filter(doctor_id=doctor_id)

    # Status filter
    if status and status != "all":
        queryset = queryset.filter(status=status.upper())

    # Appointment Type filter
    if appointment_type and appointment_type != "all":
        queryset = queryset.filter(appointment_type=appointment_type.upper())

    # Vaccination filter (if appointment is vaccination or vaccine is specified)
    if vaccine_name and vaccine_name != "all":
        queryset = queryset.filter(
            Q(vaccine_name__iexact=vaccine_name)
            | Q(medical_record__vaccine_name__iexact=vaccine_name)
            | Q(notes__icontains=vaccine_name)
        ).distinct()

    # Date / Date Range filter
    today = timezone.localdate()
    if from_date:
        try:
            parsed_from = datetime.date.fromisoformat(from_date)
            queryset = queryset.filter(date__gte=parsed_from)
        except (ValueError, TypeError):
            pass
    if to_date:
        try:
            parsed_to = datetime.date.fromisoformat(to_date)
            queryset = queryset.filter(date__lte=parsed_to)
        except (ValueError, TypeError):
            pass
    elif date_filter:
        if date_filter == "today":
            queryset = queryset.filter(date=today)
        elif date_filter == "tomorrow":
            queryset = queryset.filter(date=today + datetime.timedelta(days=1))
        elif date_filter == "this_week":
            start_week = today - datetime.timedelta(days=today.weekday())
            end_week = start_week + datetime.timedelta(days=6)
            queryset = queryset.filter(date__gte=start_week, date__lte=end_week)
        elif date_filter == "next_week":
            start_next = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=7)
            end_next = start_next + datetime.timedelta(days=6)
            queryset = queryset.filter(date__gte=start_next, date__lte=end_next)
        elif date_filter != "all":
            try:
                parsed_custom = datetime.date.fromisoformat(date_filter)
                queryset = queryset.filter(date=parsed_custom)
            except (ValueError, TypeError):
                pass

    # Search filter
    if q:
        queryset = queryset.filter(
            Q(animal__name__icontains=q)
            | Q(animal__animal_id__icontains=q)
            | Q(animal__client__full_name__icontains=q)
            | Q(animal__client__phone__icontains=q)
            | Q(brought_by__icontains=q)
            | Q(notes__icontains=q)
            | Q(doctor__first_name__icontains=q)
            | Q(doctor__last_name__icontains=q)
            | Q(doctor__username__icontains=q)
        )

    queryset = queryset.order_by("date", "time")

    # Stats for active appointments
    today = timezone.localdate()
    all_active = Appointment.objects.alive()
    if is_vet_user and not can_view_all:
        all_active = all_active.filter(doctor=request.user)

    today_count = all_active.filter(date=today, status=Appointment.Status.SCHEDULED).count()
    scheduled_count = all_active.filter(status=Appointment.Status.SCHEDULED).count()
    completed_count = all_active.filter(status=Appointment.Status.COMPLETED).count()
    cancelled_count = all_active.filter(status=Appointment.Status.CANCELLED).count()
    no_show_count = all_active.filter(status=Appointment.Status.NO_SHOW).count()

    due_now_list = [appt for appt in all_active.filter(date=today, status=Appointment.Status.SCHEDULED) if appt.is_due_now]
    overdue_list = [appt for appt in all_active.filter(status=Appointment.Status.SCHEDULED) if appt.is_overdue]

    # Pagination for List View
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Doctors list for filter dropdown (Vets only)
    if is_vet_user and not can_view_all:
        doctors = User.objects.filter(pk=request.user.pk)
    else:
        doctors = User.objects.filter(role=User.Role.VET, is_active=True).order_by("first_name", "username")

    # Appointment types from admin catalog
    appointment_types = AppointmentTypeConfig.objects.filter(is_active=True).order_by("order", "name")
    catalog_vaccines = VaccineCatalogItem.objects.filter(is_active=True).order_by("order", "name")
    form = AppointmentForm(user=request.user)

    context = {
        "appointments": page_obj,
        "page_obj": page_obj,
        "today_count": today_count,
        "scheduled_count": scheduled_count,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "no_show_count": no_show_count,
        "due_now_list": due_now_list,
        "overdue_list": overdue_list,
        "urgent_alerts_count": len(due_now_list) + len(overdue_list),
        "doctors": doctors,
        "form": form,
        "appointment_types": appointment_types,
        "catalog_vaccines": catalog_vaccines,
        "status": status,
        "appointment_type": appointment_type,
        "vaccine_name": vaccine_name,
        "filter_deleted": filter_deleted,
        "doctor_id": doctor_id,
        "date_filter": date_filter,
        "from_date": from_date,
        "to_date": to_date,
        "q": q,
        "is_vet_user": is_vet_user,
        "can_restore": can_restore_records(request.user),
    }
    return render(request, "appointments/appointments.html", context)


@login_required
@require_GET
def appointments_events_api(request):
    """JSON API endpoint returning appointments for FullCalendar."""
    start_str = request.GET.get("start")
    end_str = request.GET.get("end")
    doctor_id = request.GET.get("doctor_id")

    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)

    queryset = Appointment.objects.alive().select_related("animal", "animal__client", "doctor")

    can_view_all = can_view_all_patients(request.user)

    if is_vet_user and not can_view_all:
        queryset = queryset.filter(doctor=request.user)
    elif doctor_id and doctor_id != "all":
        queryset = queryset.filter(doctor_id=doctor_id)

    if start_str and end_str:
        try:
            start_date = datetime.datetime.fromisoformat(start_str.replace("Z", "")).date()
            end_date = datetime.datetime.fromisoformat(end_str.replace("Z", "")).date()
            queryset = queryset.filter(date__gte=start_date, date__lte=end_date)
        except (ValueError, TypeError):
            pass

    # Brand identity high-contrast color palette for Calendar Events
    STATUS_COLORS = {
        Appointment.Status.SCHEDULED: {
            "bg": "#faf5ff",
            "border": "#9b5ec9",
            "text": "#4c1d95",
            "badge_bg": "#e9d5ff",
            "badge_text": "#6b21a8",
        },
        Appointment.Status.COMPLETED: {
            "bg": "#f0fdfa",
            "border": "#1099a7",
            "text": "#134e4a",
            "badge_bg": "#ccfbf1",
            "badge_text": "#115e59",
        },
        Appointment.Status.CANCELLED: {
            "bg": "#fef2f2",
            "border": "#ef4444",
            "text": "#991b1b",
            "badge_bg": "#fee2e2",
            "badge_text": "#991b1b",
        },
        Appointment.Status.NO_SHOW: {
            "bg": "#fffbeb",
            "border": "#f59e0b",
            "text": "#92400e",
            "badge_bg": "#fef3c7",
            "badge_text": "#92400e",
        },
    }

    events = []
    for appt in queryset:
        start_dt = appt.start_datetime
        end_dt = appt.end_datetime

        # Dynamic color highlights for active/overdue appointments
        if appt.is_due_now:
            color_scheme = {
                "bg": "#ecfdf5",
                "border": "#059669",
                "text": "#064e3b",
                "badge_bg": "#a7f3d0",
                "badge_text": "#065f46",
            }
        elif appt.is_overdue:
            color_scheme = {
                "bg": "#fff7ed",
                "border": "#ea580c",
                "text": "#7c2d12",
                "badge_bg": "#ffedd5",
                "badge_text": "#9a3412",
            }
        else:
            color_scheme = STATUS_COLORS.get(
                appt.status,
                {
                    "bg": "#faf5ff",
                    "border": "#9b5ec9",
                    "text": "#4c1d95",
                    "badge_bg": "#e9d5ff",
                    "badge_text": "#6b21a8",
                }
            )

        doctor_name = appt.doctor.get_full_name() or appt.doctor.username

        events.append({
            "id": str(appt.pk),
            "title": f"{appt.animal.name} ({appt.get_appointment_type_display()}) - د. {doctor_name}",
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "backgroundColor": color_scheme["bg"],
            "borderColor": color_scheme["border"],
            "textColor": color_scheme["text"],
            "extendedProps": {
                "id": appt.pk,
                "animal_id": appt.animal.pk,
                "animal_id_code": appt.animal.animal_id or f"{appt.animal.pk:07d}",
                "animal_name": appt.animal.name,
                "species": appt.animal.get_species_display(),
                "client_id": appt.animal.client.pk,
                "client_name": appt.animal.client.full_name,
                "client_phone": appt.animal.client.phone,
                "brought_by": appt.brought_by or "المالك الدائم",
                "doctor_id": appt.doctor.pk,
                "doctor_name": doctor_name,
                "status": appt.status,
                "status_display": appt.get_status_display(),
                "time_status": appt.time_status,
                "is_due_now": appt.is_due_now,
                "is_overdue": appt.is_overdue,
                "appointment_type": appt.get_appointment_type_display(),
                "raw_appointment_type": appt.appointment_type,
                "duration": appt.duration,
                "date": appt.date.strftime("%Y-%m-%d"),
                "time": appt.time.strftime("%H:%M"),
                "vaccine_name": appt.vaccine_name or "",
                "notes": appt.notes or "",
                "theme_border": color_scheme["border"],
                "theme_text": color_scheme["text"],
                "theme_badge_bg": color_scheme["badge_bg"],
                "theme_badge_text": color_scheme["badge_text"],
            }
        })

    return JsonResponse(events, safe=False)


@login_required
@appointment_manage_permission_required
@require_POST
def appointment_create(request):
    """Create an appointment with conflict validation and audit logging."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    form = AppointmentForm(request.POST, user=request.user)

    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)

    if form.is_valid():
        appointment_obj = form.save(commit=False)
        appointment_obj.created_by = request.user
        if is_vet_user or not appointment_obj.doctor_id:
            appointment_obj.doctor = request.user
        try:
            appointment_obj.save()

            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.CREATE,
                entity=appointment_obj,
                entity_id=str(appointment_obj.pk),
                description=(
                    f"حجز موعد جديد للمريض {appointment_obj.animal.name} مع "
                    f"د. {appointment_obj.doctor.get_full_name() or appointment_obj.doctor.username} "
                    f"في {appointment_obj.date} الساعة {appointment_obj.time.strftime('%H:%M')}"
                ),
                ip_address=get_client_ip(request),
            )

            msg = f"تم حجز الموعد بنجاح للمريض «{appointment_obj.animal.name}»."
            if is_ajax:
                return JsonResponse({"success": True, "message": msg})
            messages.success(request, msg)
        except ValidationError as e:
            err_msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if is_ajax:
                return JsonResponse({"success": False, "error": err_msg}, status=400)
            messages.error(request, f"تعذر الحجز: {err_msg}")
    else:
        has_past_warning = getattr(form, "has_past_date_warning", False)
        error_msg = "; ".join([f"{err[0]}" for err in form.errors.values()])
        if is_ajax:
            return JsonResponse({
                "success": False,
                "error": error_msg,
                "has_past_date_warning": has_past_warning,
                "errors": form.errors.get_json_data()
            }, status=400)
        messages.error(request, f"يرجى تصحيح الأخطاء التالية: {error_msg}")

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("appointments:list")


@login_required
@appointment_manage_permission_required
@require_POST
def appointment_update(request, appointment_id):
    """Update appointment details with conflict checking."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    appointment_obj = get_object_or_404(Appointment.all_objects, pk=appointment_id)

    is_vet_user = request.user.is_authenticated and request.user.role == User.Role.VET and not request.user.is_superuser and not getattr(request.user, "is_admin_user", False)
    if is_vet_user and appointment_obj.doctor_id != request.user.pk:
        msg = "ليس لديك صلاحية تعديل موعد مسجل لطبيب آخر."
        if is_ajax:
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("appointments:list")

    form = AppointmentForm(request.POST, instance=appointment_obj, user=request.user)

    if form.is_valid():
        try:
            appointment_obj = form.save()

            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                entity=appointment_obj,
                entity_id=str(appointment_obj.pk),
                description=f"تعديل بيانات الموعد رقم #{appointment_obj.pk} للمريض {appointment_obj.animal.name}",
                ip_address=get_client_ip(request),
            )

            msg = f"تم تحديث الموعد رقم #{appointment_obj.pk} بنجاح."
            if is_ajax:
                return JsonResponse({"success": True, "message": msg})
            messages.success(request, msg)
        except ValidationError as e:
            err_msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if is_ajax:
                return JsonResponse({"success": False, "error": err_msg}, status=400)
            messages.error(request, f"تعذر التعديل: {err_msg}")
    else:
        has_past_warning = getattr(form, "has_past_date_warning", False)
        error_msg = "; ".join([f"{err[0]}" for err in form.errors.values()])
        if is_ajax:
            return JsonResponse({
                "success": False,
                "error": error_msg,
                "has_past_date_warning": has_past_warning,
                "errors": form.errors.get_json_data()
            }, status=400)
        messages.error(request, f"يرجى تصحيح الأخطاء التالية: {error_msg}")

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("appointments:list")


@login_required
@appointment_manage_permission_required
@require_POST
def appointment_update_status(request, appointment_id):
    """Quick status update for an appointment (e.g. COMPLETED, CANCELLED, NO_SHOW, SCHEDULED)."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    appointment_obj = get_object_or_404(Appointment.objects.alive(), pk=appointment_id)
    new_status = request.POST.get("status")

    if new_status in Appointment.Status.values:
        old_status_display = appointment_obj.get_status_display()
        appointment_obj.status = new_status
        try:
            appointment_obj.save(update_fields=["status", "updated_at"])
        except (ValidationError, IntegrityError) as e:
            error_msg = "لا يمكن تغيير حالة الموعد لوجود تضارب زمني مع موعد آخر أو خارج أوقات دوام العيادة."
            if isinstance(e, ValidationError):
                if hasattr(e, "messages") and e.messages:
                    error_msg = "; ".join(e.messages)
                elif hasattr(e, "message_dict"):
                    error_msg = "; ".join([msg for sub in e.message_dict.values() for msg in sub])
            if is_ajax:
                return JsonResponse({"success": False, "error": error_msg}, status=400)
            messages.error(request, error_msg)
            return_to = request.POST.get("return_to")
            if return_to:
                return redirect(return_to)
            return redirect("appointments:list")

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity=appointment_obj,
            entity_id=str(appointment_obj.pk),
            description=f"تغيير حالة الموعد #{appointment_obj.pk} من ({old_status_display}) إلى ({appointment_obj.get_status_display()})",
            ip_address=get_client_ip(request),
        )

        msg = f"تم تحديث حالة الموعد إلى «{appointment_obj.get_status_display()}»."
        if is_ajax:
            return JsonResponse({
                "success": True,
                "message": msg,
                "status": appointment_obj.status,
                "status_display": appointment_obj.get_status_display(),
            })
        messages.success(request, msg)
    else:
        if is_ajax:
            return JsonResponse({"success": False, "error": "حالة موعد غير صالحة."}, status=400)
        messages.error(request, "حالة موعد غير صالحة.")

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("appointments:list")


@login_required
@delete_permission_required
@require_POST
def appointment_delete(request, appointment_id):
    """Soft delete an appointment."""
    appointment_obj = get_object_or_404(Appointment.objects.alive(), pk=appointment_id)
    appointment_obj.soft_delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity=appointment_obj,
        entity_id=str(appointment_obj.pk),
        description=f"حذف الموعد #{appointment_obj.pk} مؤقتاً للمريض {appointment_obj.animal.name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم نقل الموعد #{appointment_obj.pk} إلى سلة المحذوفات.")
    return redirect("appointments:list")


@login_required
@restore_permission_required
@require_POST
def appointment_restore(request, appointment_id):
    """Restore a soft-deleted appointment."""
    appointment_obj = get_object_or_404(Appointment.objects.deleted_only(), pk=appointment_id)
    
    # Check if restoring would cause an overlap conflict
    try:
        appointment_obj.clean()
    except ValidationError as e:
        messages.error(request, f"لا يمكن استعادة الموعد بسبب تضارب مع موعد آخر قائم: {e.message if hasattr(e, 'message') else e}")
        return redirect("appointments:list")

    appointment_obj.restore()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.RESTORE,
        entity=appointment_obj,
        entity_id=str(appointment_obj.pk),
        description=f"استعادة الموعد #{appointment_obj.pk} من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تمت استعادة الموعد #{appointment_obj.pk} بنجاح.")
    return redirect("appointments:list")


@login_required
@delete_permission_required
@require_POST
def appointment_hard_delete(request, appointment_id):
    """Permanently delete an appointment from trash."""
    appointment_obj = get_object_or_404(Appointment.objects.deleted_only(), pk=appointment_id)
    appt_pk = appointment_obj.pk
    animal_name = appointment_obj.animal.name if appointment_obj.animal else "غير محدد"
    appointment_obj.delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity_type="Appointment",
        entity_id=str(appt_pk),
        description=f"حذف نهائي للموعد #{appt_pk} للمريض {animal_name} من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم حذف الموعد #{appt_pk} نهائياً وبشكل لا رجعة فيه.")
    return redirect("appointments:list")


@login_required
@delete_permission_required
@require_POST
def appointment_bulk_hard_delete(request):
    """Bulk permanently delete selected appointments from trash."""
    ids = request.POST.getlist("selected_ids") or request.POST.getlist("selected_ids[]")
    if not ids:
        messages.warning(request, "لم يتم تحديد أي مواعيد للحذف النهائي.")
        return redirect("appointments:list")

    deleted_qs = Appointment.objects.deleted_only().filter(pk__in=ids)
    count = deleted_qs.count()
    if count > 0:
        deleted_qs.delete()
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            entity_type="Appointment",
            entity_id=f"Bulk-{count}",
            description=f"حذف نهائي جماعي لـ ({count}) موعد من سلة المحذوفات",
            ip_address=get_client_ip(request),
        )
        messages.success(request, f"تم الحذف النهائي لـ {count} موعد بنجاح من سلة المحذوفات.")
    else:
        messages.warning(request, "لم يتم العثور على المواعيد المحددة في سلة المحذوفات.")

    return redirect("appointments:list")

