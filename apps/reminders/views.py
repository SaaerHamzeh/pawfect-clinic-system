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

from .models import Reminder
from .forms import ReminderForm, ReminderUpdateForm, ConvertReminderToAppointmentForm
from apps.patients.models import Animal
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.core.utils import get_client_ip
from apps.accounts.permissions import (
    can_restore_records,
    can_delete_records,
    restore_permission_required,
    delete_permission_required,
    appointment_manage_permission_required,
    can_view_all_patients,
    get_visible_patients,
    can_manage_appointments,
)


@login_required
def reminders(request):
    """List reminders with search, stats, status filtering, date range filtering, and due-date highlighting."""
    status = request.GET.get("status", "all")
    reminder_type = request.GET.get("type", "all")
    filter_deleted = request.GET.get("filter_deleted", "active")
    due_filter = request.GET.get("due", "all")
    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "due_date").strip()

    # Soft Delete handling
    if filter_deleted == "deleted":
        queryset = Reminder.objects.deleted_only().select_related(
            "animal", "animal__client", "medical_record", "medical_record__doctor", "converted_appointment"
        ).prefetch_related("generated_from_vaccination", "generated_from_vaccination__doctor")
    else:
        queryset = Reminder.objects.alive().select_related(
            "animal", "animal__client", "medical_record", "medical_record__doctor", "converted_appointment"
        ).prefetch_related("generated_from_vaccination", "generated_from_vaccination__doctor")

    if not can_view_all_patients(request.user) and request.user.role == User.Role.VET:
        queryset = queryset.filter(animal__in=get_visible_patients(request.user))

    # Status filter
    if status and status != "all":
        queryset = queryset.filter(status=status)

    # Type filter
    if reminder_type and reminder_type != "all":
        queryset = queryset.filter(reminder_type=reminder_type)

    # Date Range filter
    today = timezone.localdate()
    if from_date:
        try:
            d_from = datetime.datetime.strptime(from_date, "%Y-%m-%d").date()
            queryset = queryset.filter(due_date__gte=d_from)
        except ValueError:
            pass
    if to_date:
        try:
            d_to = datetime.datetime.strptime(to_date, "%Y-%m-%d").date()
            queryset = queryset.filter(due_date__lte=d_to)
        except ValueError:
            pass

    # Due-Date filter presets
    if due_filter == "overdue":
        queryset = queryset.filter(due_date__lt=today, status=Reminder.Status.PENDING)
    elif due_filter == "today":
        queryset = queryset.filter(due_date=today, status=Reminder.Status.PENDING)
    elif due_filter == "week":
        end_of_week = today + datetime.timedelta(days=7)
        queryset = queryset.filter(due_date__gte=today, due_date__lte=end_of_week, status=Reminder.Status.PENDING)
    elif due_filter == "month":
        end_of_month = today + datetime.timedelta(days=30)
        queryset = queryset.filter(due_date__gte=today, due_date__lte=end_of_month, status=Reminder.Status.PENDING)

    # Search
    if q:
        queryset = queryset.filter(
            Q(animal__name__icontains=q) |
            Q(animal__client__full_name__icontains=q) |
            Q(animal__client__phone__icontains=q) |
            Q(notes__icontains=q)
        )

    # Sorting / Alphabetical ordering
    if sort == "animal_asc":
        queryset = queryset.order_by("animal__name", "due_date")
    elif sort == "animal_desc":
        queryset = queryset.order_by("-animal__name", "due_date")
    elif sort == "client_asc":
        queryset = queryset.order_by("animal__client__full_name", "due_date")
    elif sort == "client_desc":
        queryset = queryset.order_by("-animal__client__full_name", "due_date")
    elif sort == "notes_asc":
        queryset = queryset.order_by("notes", "due_date")
    else:
        sort = "due_date"
        queryset = queryset.order_by("due_date", "created_at")

    # Counters
    alive_qs = Reminder.objects.alive()
    if not can_view_all_patients(request.user) and request.user.role == User.Role.VET:
        alive_qs = alive_qs.filter(animal__in=get_visible_patients(request.user))

    total_count = alive_qs.count()
    overdue_count = alive_qs.filter(due_date__lt=today, status=Reminder.Status.PENDING).count()
    due_today_count = alive_qs.filter(due_date=today, status=Reminder.Status.PENDING).count()
    completed_count = alive_qs.filter(status=Reminder.Status.COMPLETED).count()

    # Doctors for appointment conversion modal
    doctors = User.objects.filter(role=User.Role.VET, is_active=True).order_by("first_name", "username")

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    form = ReminderForm()

    context = {
        "reminders": page_obj,
        "page_obj": page_obj,
        "total_count": total_count,
        "overdue_count": overdue_count,
        "due_today_count": due_today_count,
        "completed_count": completed_count,
        "today": today,
        "doctors": doctors,
        "form": form,
        "status": status,
        "reminder_type": reminder_type,
        "filter_deleted": filter_deleted,
        "due_filter": due_filter,
        "from_date": from_date,
        "to_date": to_date,
        "q": q,
        "sort": sort,
        "can_restore": can_restore_records(request.user),
        "can_manage_appointments": can_manage_appointments(request.user),
    }
    return render(request, "reminders/reminders.html", context)


@login_required
@appointment_manage_permission_required
@require_POST
def reminder_create(request):
    """Create a new reminder with audit logging."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    form = ReminderForm(request.POST)
    if form.is_valid():
        reminder_obj = form.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity=reminder_obj,
            entity_id=str(reminder_obj.pk),
            description=(
                f"إنشاء تذكير جديد للمريض {reminder_obj.animal.name} "
                f"({reminder_obj.get_reminder_type_display()}) لتاريخ {reminder_obj.due_date}"
            ),
            ip_address=get_client_ip(request),
        )

        msg = f"تمت إضافة التذكير بنجاح للمريض «{reminder_obj.animal.name}»."
        messages.success(request, msg)
        return_url = request.POST.get("return_to") or reverse("reminders:list")
        if is_ajax:
            return JsonResponse({"success": True, "redirect_url": return_url, "message": msg})
    else:
        error_list = [err for sublist in form.errors.values() for err in sublist]
        error_msg = "; ".join(error_list) if error_list else "يرجى التحقق من صحة البيانات المدخلة."
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
    return redirect("reminders:list")


@login_required
@appointment_manage_permission_required
@require_POST
def reminder_update(request, reminder_id):
    """Update reminder details."""
    reminder_obj = get_object_or_404(Reminder.all_objects, pk=reminder_id)
    form = ReminderUpdateForm(request.POST, instance=reminder_obj)
    if form.is_valid():
        reminder_obj = form.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity=reminder_obj,
            entity_id=str(reminder_obj.pk),
            description=f"تعديل التذكير #{reminder_obj.pk} للمريض {reminder_obj.animal.name}",
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تم تحديث التذكير للمريض «{reminder_obj.animal.name}» بنجاح.")
    else:
        messages.error(request, "فشل تعديل التذكير. يرجى مراجعة الحقول المطلوبة.")

    return_to = request.POST.get("return_to")
    if return_to:
        return redirect(return_to)
    return redirect("reminders:list")


@login_required
@appointment_manage_permission_required
@require_POST
def reminder_convert_to_appointment(request, reminder_id):
    """Convert a pending reminder into a booked appointment."""
    reminder_obj = get_object_or_404(Reminder.objects.alive(), pk=reminder_id)

    if reminder_obj.status != Reminder.Status.PENDING:
        messages.warning(request, "يمكن فقط تحويل التذكيرات التي في حالة (معلق / قيد الانتظار).")
        return redirect("reminders:list")

    form = ConvertReminderToAppointmentForm(request.POST)
    if form.is_valid():
        chosen_doc = form.cleaned_data.get("doctor")
        assigned_doc = reminder_obj.assigned_doctor
        if assigned_doc and assigned_doc.is_active:
            doctor = assigned_doc
        elif chosen_doc and chosen_doc.is_active:
            doctor = chosen_doc
        else:
            doctor = chosen_doc or assigned_doc

        appt_date = form.cleaned_data["date"]
        appt_time = form.cleaned_data["time"]
        duration = int(form.cleaned_data["duration"])
        brought_by = form.cleaned_data["brought_by"]
        notes = form.cleaned_data["notes"] or reminder_obj.notes

        # Determine matching appointment type
        appt_type = Appointment.AppointmentType.CHECKUP
        vaccine_name = ""
        if reminder_obj.reminder_type == Reminder.ReminderType.VACCINATION:
            appt_type = Appointment.AppointmentType.VACCINATION
            v_rec = reminder_obj.generated_from_vaccination.first()
            if v_rec and v_rec.vaccine_name:
                vaccine_name = v_rec.vaccine_name
            elif reminder_obj.notes:
                vaccine_name = reminder_obj.notes
        elif reminder_obj.reminder_type == Reminder.ReminderType.FOLLOW_UP:
            appt_type = Appointment.AppointmentType.TREATMENT

        new_appointment = Appointment(
            animal=reminder_obj.animal,
            doctor=doctor,
            date=appt_date,
            time=appt_time,
            duration=duration,
            appointment_type=appt_type,
            vaccine_name=vaccine_name,
            status=Appointment.Status.SCHEDULED,
            brought_by=brought_by,
            notes=f"[محول من تذكير #{reminder_obj.pk}]: {notes}",
            created_by=request.user,
        )

        try:
            new_appointment.full_clean()
            new_appointment.save()

            # Mark reminder as converted
            reminder_obj.mark_as_converted(appointment=new_appointment)

            # Audit Log for Appointment
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.CREATE,
                entity=new_appointment,
                entity_id=str(new_appointment.pk),
                description=(
                    f"حجز موعد محول من تذكير #{reminder_obj.pk} للمريض {new_appointment.animal.name} "
                    f"مع د. {doctor.get_full_name() or doctor.username} في {appt_date} {appt_time}"
                ),
                ip_address=get_client_ip(request),
            )

            # Audit Log for Reminder status change
            AuditLog.log(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                entity=reminder_obj,
                entity_id=str(reminder_obj.pk),
                description=f"تحويل التذكير #{reminder_obj.pk} إلى موعد رسمي رقم #{new_appointment.pk}",
                ip_address=get_client_ip(request),
            )

            messages.success(
                request,
                f"تم تحويل التذكير بنجاح إلى موعد للمريض «{reminder_obj.animal.name}» في {appt_date} الساعة {appt_time.strftime('%H:%M')} مع د. {doctor.get_full_name() or doctor.username}."
            )
            return redirect("appointments:list")

        except ValidationError as e:
            messages.error(request, f"تعذر إنشاء الموعد لوجود تضارب: {e.message if hasattr(e, 'message') else e}")
    else:
        error_msg = "يرجى التحقق من بيانات الموعد: " + "; ".join(
            [f"{err[0]}" for err in form.errors.values()]
        )
        messages.error(request, error_msg)

    return redirect("reminders:list")


@login_required
@appointment_manage_permission_required
@require_POST
def reminder_update_status(request, reminder_id):
    """Quick status update for a reminder."""
    reminder_obj = get_object_or_404(Reminder.objects.alive(), pk=reminder_id)
    new_status = request.POST.get("status")

    if new_status in Reminder.Status.values:
        old_status_display = reminder_obj.get_status_display()
        reminder_obj.status = new_status
        reminder_obj.save(update_fields=["status", "updated_at"])

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity=reminder_obj,
            entity_id=str(reminder_obj.pk),
            description=f"تغيير حالة التذكير #{reminder_obj.pk} من ({old_status_display}) إلى ({reminder_obj.get_status_display()})",
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تم تحديث حالة التذكير إلى «{reminder_obj.get_status_display()}».")
    else:
        messages.error(request, "حالة غير صالحة.")

    return redirect("reminders:list")


@login_required
@delete_permission_required
@require_POST
def reminder_delete(request, reminder_id):
    """Soft delete a reminder."""
    reminder_obj = get_object_or_404(Reminder.objects.alive(), pk=reminder_id)
    reminder_obj.soft_delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity=reminder_obj,
        entity_id=str(reminder_obj.pk),
        description=f"حذف التذكير #{reminder_obj.pk} مؤقتاً للمريض {reminder_obj.animal.name}",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم نقل التذكير إلى سلة المحذوفات.")
    return redirect("reminders:list")


@login_required
@restore_permission_required
@require_POST
def reminder_restore(request, reminder_id):
    """Restore a soft-deleted reminder."""
    reminder_obj = get_object_or_404(Reminder.objects.deleted_only(), pk=reminder_id)
    reminder_obj.restore()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.RESTORE,
        entity=reminder_obj,
        entity_id=str(reminder_obj.pk),
        description=f"استعادة التذكير #{reminder_obj.pk} من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تمت استعادة التذكير بنجاح.")
    return redirect("reminders:list")


@login_required
@delete_permission_required
@require_POST
def reminder_hard_delete(request, reminder_id):
    """Permanently delete a reminder from trash."""
    reminder_obj = get_object_or_404(Reminder.objects.deleted_only(), pk=reminder_id)
    rem_pk = reminder_obj.pk
    animal_name = reminder_obj.animal.name if reminder_obj.animal else "غير محدد"
    reminder_obj.delete()

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.DELETE,
        entity_type="Reminder",
        entity_id=str(rem_pk),
        description=f"حذف نهائي للتذكير #{rem_pk} للمريض {animal_name} من سلة المحذوفات",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم حذف التذكير #{rem_pk} نهائياً وبشكل قطعي.")
    return redirect("reminders:list")


@login_required
@delete_permission_required
@require_POST
def reminder_bulk_hard_delete(request):
    """Bulk permanently delete selected reminders from trash."""
    ids = request.POST.getlist("selected_ids") or request.POST.getlist("selected_ids[]")
    if not ids:
        messages.warning(request, "لم يتم تحديد أي تذكيرات للحذف النهائي.")
        return redirect("reminders:list")

    deleted_qs = Reminder.objects.deleted_only().filter(pk__in=ids)
    count = deleted_qs.count()
    if count > 0:
        deleted_qs.delete()
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.DELETE,
            entity_type="Reminder",
            entity_id=f"Bulk-{count}",
            description=f"حذف نهائي جماعي لـ ({count}) تذكير من سلة المحذوفات",
            ip_address=get_client_ip(request),
        )
        messages.success(request, f"تم الحذف النهائي لـ {count} تذكير بنجاح من سلة المحذوفات.")
    else:
        messages.warning(request, "لم يتم العثور على التذكيرات المحددة في سلة المحذوفات.")

    return redirect("reminders:list")

