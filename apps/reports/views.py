from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q

from apps.accounts.permissions import reports_permission_required
from apps.accounts.models import User
from apps.patients.models import Animal
from apps.clients.models import Client
from apps.clinical.models import VaccinationRecord, MedicalRecord
from apps.appointments.models import Appointment
from apps.reminders.models import Reminder
from apps.audit.models import AuditLog
from apps.core.utils import get_client_ip

from .services import (
    generate_patient_medical_report_xlsx,
    generate_patients_registry_report_xlsx,
    generate_client_report_xlsx,
    generate_due_vaccinations_report_xlsx,
    generate_vaccinations_report_xlsx,
    generate_appointments_report_xlsx,
    generate_clients_directory_report_xlsx,
    generate_clinical_records_report_xlsx,
    generate_reminders_report_xlsx,
)


@reports_permission_required
def reports(request):
    """
    Central Reports & Excel Export Dashboard.
    Provides interactive forms to generate multi-sheet medical records,
    patients registry, due/all vaccinations, appointments schedules, and directories.
    """
    today = timezone.localdate()

    # Pre-fetch clients and doctors for dropdown filters
    clients = Client.objects.alive().annotate(
        pets_count=Count("animals", filter=Q(animals__is_deleted=False))
    ).order_by("full_name")

    patients = Animal.objects.alive().select_related("client").order_by("name")

    doctors = User.objects.filter(
        role=User.Role.VET,
        is_active=True
    ).order_by("first_name", "username")

    # Dropdown choices
    species_list = Animal.Species.choices
    appointment_types = Appointment.AppointmentType.choices
    clinical_record_types = MedicalRecord.RecordType.choices
    reminder_types = Reminder.ReminderType.choices

    # Fetch unique vaccine names for filter suggestions
    vaccine_names = (
        VaccinationRecord.objects.alive()
        .values_list("vaccine_name", flat=True)
        .distinct()
        .order_by("vaccine_name")
    )

    # High-level KPIs for reporting dashboard
    total_clients = clients.count()
    total_patients = Animal.objects.alive().count()
    total_clinical_records = MedicalRecord.objects.alive().count()
    due_vaccines_count = VaccinationRecord.objects.alive().filter(
        next_due_date__isnull=False,
        next_due_date__lte=today
    ).count()

    context = {
        "clients": clients,
        "patients": patients,
        "doctors": doctors,
        "today": today,
        "total_clients": total_clients,
        "total_patients": total_patients,
        "total_clinical_records": total_clinical_records,
        "due_vaccines_count": due_vaccines_count,
        "species_list": species_list,
        "appointment_types": appointment_types,
        "clinical_record_types": clinical_record_types,
        "reminder_types": reminder_types,
        "vaccine_names": list(vaccine_names),
    }
    return render(request, "reports/reports.html", context)


@reports_permission_required
def api_client_patients(request, client_id):
    """
    JSON API returning active patients for a given client to populate dropdowns.
    """
    client = get_object_or_404(Client.objects.alive(), pk=client_id)
    patients = client.animals.alive().values("id", "name", "species", "breed")
    return JsonResponse({"patients": list(patients)})


@reports_permission_required
def export_patient_report(request, patient_id):
    """
    Exports a multi-sheet medical report (Basic Info, Clinical Visits, Vaccinations) for a patient.
    """
    animal = get_object_or_404(
        Animal.objects.alive().select_related("client"),
        pk=patient_id
    )

    include_basic = request.GET.get("basic", "true").lower() == "true"
    include_clinical = request.GET.get("clinical", "true").lower() == "true"
    include_vaccines = request.GET.get("vaccines", "true").lower() == "true"
    include_appointments = request.GET.get("appointments", "false").lower() == "true"
    include_reminders = request.GET.get("reminders", "false").lower() == "true"
    include_services = request.GET.get("services", "true").lower() == "true"

    buffer = generate_patient_medical_report_xlsx(
        animal=animal,
        include_basic=include_basic,
        include_clinical=include_clinical,
        include_vaccines=include_vaccines,
        include_appointments=include_appointments,
        include_reminders=include_reminders,
        include_services=include_services,
    )

    # Audit log
    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.EXPORT,
        entity_type="MedicalReport",
        entity_id=str(animal.pk),
        description=f"تصدير التقرير الطبي لـ {animal.name} (المالك: {animal.client.full_name}) بصيغة Excel",
        ip_address=get_client_ip(request)
    )

    filename = f"Medical_Report_Pet_{animal.pk}_{timezone.localdate().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@reports_permission_required
def export_client_report(request, client_id):
    """
    Exports all animal records for a specific client.
    """
    client = get_object_or_404(Client.objects.alive(), pk=client_id)

    buffer = generate_client_report_xlsx(client)

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.EXPORT,
        entity_type="ClientReport",
        entity_id=str(client.pk),
        description=f"تصدير تقرير شامل للعميل {client.full_name} وحيواناته بصيغة Excel",
        ip_address=get_client_ip(request)
    )

    filename = f"Client_Report_{client.pk}_{timezone.localdate().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@reports_permission_required
def export_due_vaccinations(request):
    """
    Exports due vaccinations list with owner phone contacts.
    """
    due_filter = request.GET.get("due", "all")
    scope = request.GET.get("scope", "due")
    species = request.GET.get("species") or None
    doctor_id = request.GET.get("doctor_id") or None

    buffer = generate_vaccinations_report_xlsx(
        scope=scope,
        due_filter=due_filter,
        species=species,
        doctor_id=doctor_id
    )

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.EXPORT,
        entity_type="VaccinationsDueReport",
        description=f"تصدير كشف التطعيمات (نطاق: {scope}، تصفية: {due_filter}) بصيغة Excel",
        ip_address=get_client_ip(request)
    )

    filename = f"Vaccinations_{scope}_{timezone.localdate().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@reports_permission_required
def export_appointments(request):
    """
    Exports appointments schedule log with date, doctor, status, and species filters.
    """
    start_date = request.GET.get("start_date") or None
    end_date = request.GET.get("end_date") or None
    doctor_id = request.GET.get("doctor_id") or None
    status = request.GET.get("status") or None
    species = request.GET.get("species") or None
    appointment_type = request.GET.get("appointment_type") or None

    buffer = generate_appointments_report_xlsx(
        start_date=start_date,
        end_date=end_date,
        doctor_id=doctor_id,
        status=status,
        species=species,
        appointment_type=appointment_type,
    )

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.EXPORT,
        entity_type="AppointmentsReport",
        description="تصدير سجل المواعيد بصيغة Excel",
        ip_address=get_client_ip(request)
    )

    filename = f"Appointments_Report_{timezone.localdate().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@reports_permission_required
def export_directory(request):
    """
    Exports complete clients and patients directory.
    """
    buffer = generate_clients_directory_report_xlsx()

    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.Action.EXPORT,
        entity_type="DirectoryReport",
        description="تصدير دليل العملاء والمرضى الشامل بصيغة Excel",
        ip_address=get_client_ip(request)
    )

    filename = f"Clinic_Directory_{timezone.localdate().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@reports_permission_required
def export_custom_unified_report(request):
    """
    Comprehensive Unified Report Generator endpoint.
    Handles customized exports for any domain (Patient / Registry, Client, Clinical, Vaccinations, Appointments, Reminders, Directory).
    """
    domain = request.GET.get("domain", "patient")
    date_str = timezone.localdate().strftime('%Y%m%d')

    if domain == "patient":
        patient_id = request.GET.get("patient_id")
        client_id = request.GET.get("client_id")
        species = request.GET.get("species")
        breed = request.GET.get("breed")
        gender = request.GET.get("gender")
        q = request.GET.get("q")
        start_date = request.GET.get("start_date") or None
        end_date = request.GET.get("end_date") or None

        # If patient_id is not specified or set to "all", export the comprehensive Patients Registry table
        if not patient_id or patient_id == "all":
            buffer = generate_patients_registry_report_xlsx(
                client_id=client_id,
                species=species,
                breed=breed,
                gender=gender,
                q=q,
                start_date=start_date,
                end_date=end_date,
            )
            filename = f"Custom_Patients_Registry_{date_str}.xlsx"
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.EXPORT,
                entity_type="PatientsRegistryReport",
                description="تصدير سجل وقائمة المرضى (الحيوانات) بالعيادة بصيغة Excel",
                ip_address=get_client_ip(request)
            )
        else:
            animal = get_object_or_404(Animal.objects.alive().select_related("client"), pk=patient_id)
            include_basic = request.GET.get("include_basic", "true").lower() == "true"
            include_clinical = request.GET.get("include_clinical", "true").lower() == "true"
            include_vaccines = request.GET.get("include_vaccines", "true").lower() == "true"
            include_appointments = request.GET.get("include_appointments", "false").lower() == "true"
            include_reminders = request.GET.get("include_reminders", "false").lower() == "true"
            include_services = request.GET.get("include_services", "true").lower() == "true"

            buffer = generate_patient_medical_report_xlsx(
                animal=animal,
                include_basic=include_basic,
                include_clinical=include_clinical,
                include_vaccines=include_vaccines,
                include_appointments=include_appointments,
                include_reminders=include_reminders,
                include_services=include_services,
            )
            filename = f"Custom_Medical_Report_{animal.name}_{date_str}.xlsx"
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.EXPORT,
                entity_type="MedicalReport",
                entity_id=str(animal.pk),
                description=f"تصدير التقرير الطبي لـ {animal.name} بصيغة Excel",
                ip_address=get_client_ip(request)
            )

    elif domain == "clinical":
        start_date = request.GET.get("start_date") or None
        end_date = request.GET.get("end_date") or None
        doctor_id = request.GET.get("doctor_id") or None
        record_type = request.GET.get("record_type") or None
        client_id = request.GET.get("client_id") or None
        patient_id = request.GET.get("patient_id") or None
        species = request.GET.get("species") or None
        q = request.GET.get("q") or None
        include_prescriptions = request.GET.get("include_prescriptions", "true").lower() == "true"
        include_treatment = request.GET.get("include_treatment", "true").lower() == "true"
        include_services = request.GET.get("include_services", "true").lower() == "true"

        buffer = generate_clinical_records_report_xlsx(
            start_date=start_date,
            end_date=end_date,
            doctor_id=doctor_id,
            record_type=record_type,
            animal_id=patient_id,
            client_id=client_id,
            species=species,
            q=q,
            include_prescriptions=include_prescriptions,
            include_treatment=include_treatment,
            include_services=include_services,
        )
        filename = f"Custom_Clinical_Visits_{date_str}.xlsx"
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.EXPORT,
            entity_type="UnifiedCustomReport",
            description="تصدير تقرير الزيارات والفحوصات السريرية المخصص بصيغة Excel",
            ip_address=get_client_ip(request)
        )

    elif domain == "vaccinations":
        scope = request.GET.get("scope", "due")
        due_filter = request.GET.get("due_filter", "all")
        species = request.GET.get("species") or None
        doctor_id = request.GET.get("doctor_id") or None
        vaccine_name = request.GET.get("vaccine_name") or None
        start_date = request.GET.get("start_date") or None
        end_date = request.GET.get("end_date") or None

        buffer = generate_vaccinations_report_xlsx(
            scope=scope,
            due_filter=due_filter,
            species=species,
            doctor_id=doctor_id,
            vaccine_name=vaccine_name,
            start_date=start_date,
            end_date=end_date,
        )
        filename = f"Custom_Vaccinations_{scope}_{date_str}.xlsx"
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.EXPORT,
            entity_type="UnifiedCustomReport",
            description=f"تصدير تقرير التطعيمات المخصص (نطاق: {scope}) بصيغة Excel",
            ip_address=get_client_ip(request)
        )

    elif domain == "appointments":
        start_date = request.GET.get("start_date") or None
        end_date = request.GET.get("end_date") or None
        doctor_id = request.GET.get("doctor_id") or None
        status = request.GET.get("status") or None
        species = request.GET.get("species") or None
        appointment_type = request.GET.get("appointment_type") or None
        include_notes = request.GET.get("include_notes", "true").lower() == "true"

        buffer = generate_appointments_report_xlsx(
            start_date=start_date,
            end_date=end_date,
            doctor_id=doctor_id,
            status=status,
            species=species,
            appointment_type=appointment_type,
            include_notes=include_notes,
        )
        filename = f"Custom_Appointments_{date_str}.xlsx"
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.EXPORT,
            entity_type="UnifiedCustomReport",
            description="تصدير تقرير المواعيد المخصص بصيغة Excel",
            ip_address=get_client_ip(request)
        )

    elif domain == "reminders":
        due_filter = request.GET.get("due_filter", "all")
        reminder_type = request.GET.get("reminder_type", "all")
        status = request.GET.get("status", "all")
        start_date = request.GET.get("start_date") or None
        end_date = request.GET.get("end_date") or None
        species = request.GET.get("species") or None

        buffer = generate_reminders_report_xlsx(
            due_filter=due_filter,
            reminder_type=reminder_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
            species=species,
        )
        filename = f"Custom_Reminders_{date_str}.xlsx"
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.EXPORT,
            entity_type="UnifiedCustomReport",
            description="تصدير تقرير التذكيرات المخصص بصيغة Excel",
            ip_address=get_client_ip(request)
        )

    elif domain == "clients" or domain == "directory":
        client_id = request.GET.get("client_id")
        if client_id and client_id != "all":
            client = get_object_or_404(Client.objects.alive(), pk=client_id)
            buffer = generate_client_report_xlsx(client)
            filename = f"Custom_Client_{client.full_name}_{date_str}.xlsx"
        else:
            buffer = generate_clients_directory_report_xlsx()
            filename = f"Custom_Clinic_Directory_{date_str}.xlsx"

        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.Action.EXPORT,
            entity_type="UnifiedCustomReport",
            description=f"تصدير دليل/تقرير العملاء بصيغة Excel",
            ip_address=get_client_ip(request)
        )

    else:
        buffer = generate_clients_directory_report_xlsx()
        filename = f"Custom_Clinic_Report_{date_str}.xlsx"

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
