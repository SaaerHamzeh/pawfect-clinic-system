from datetime import timedelta
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q, F
from django.contrib.auth import get_user_model

from apps.appointments.models import Appointment
from apps.patients.models import Animal
from apps.clients.models import Client
from apps.reminders.models import Reminder
from apps.clinical.models import MedicalRecord, VisitService
from apps.settings.models import VisitServiceCatalogItem
from apps.accounts.permissions import (
    can_view_all_patients,
    get_visible_clinical_records,
    get_visible_appointments,
)

User = get_user_model()


def get_top_active_patients(user, period="this_month", metric="total", limit=10):
    """
    High-performance, flexible query to determine top active patients.
    Filters by timeframe and metric before fetching Animal models, avoiding
    expensive full-table joins or scans across the entire patient database.
    """
    today = timezone.localdate()
    date_from = None
    if period == "this_month":
        date_from = today.replace(day=1)
    elif period == "last_30_days":
        date_from = today - timedelta(days=30)
    elif period == "this_year":
        date_from = today.replace(month=1, day=1)
    elif period == "all_time":
        date_from = None
    else:
        period = "this_month"
        date_from = today.replace(day=1)

    try:
        limit = int(limit)
        if limit not in [5, 10, 15]:
            limit = 10
    except (ValueError, TypeError):
        limit = 10

    if metric not in ["total", "visits", "appointments"]:
        metric = "total"

    # 1. Aggregate appointments by animal_id for the period
    app_qs = get_visible_appointments(user, Appointment.objects.alive())
    if date_from:
        app_qs = app_qs.filter(date__gte=date_from)
    app_counts = dict(
        app_qs.values("animal_id")
        .annotate(cnt=Count("id"))
        .values_list("animal_id", "cnt")
    )

    # 2. Aggregate clinical records by animal_id for the period
    vis_qs = get_visible_clinical_records(user, MedicalRecord.objects.alive())
    if date_from:
        vis_qs = vis_qs.filter(date_time__date__gte=date_from)
    vis_counts = dict(
        vis_qs.values("animal_id")
        .annotate(cnt=Count("id"))
        .values_list("animal_id", "cnt")
    )

    all_animal_ids = set(app_counts.keys()) | set(vis_counts.keys())
    all_animal_ids.discard(None)

    if not all_animal_ids:
        return [], period, metric, limit

    activity_map = {}
    for aid in all_animal_ids:
        a_cnt = app_counts.get(aid, 0)
        v_cnt = vis_counts.get(aid, 0)
        t_cnt = a_cnt + v_cnt
        activity_map[aid] = {
            "appointments_count": a_cnt,
            "visits_count": v_cnt,
            "total_activity": t_cnt,
        }

    # Sort based on metric
    if metric == "appointments":
        sorted_ids = sorted(
            all_animal_ids,
            key=lambda aid: (
                activity_map[aid]["appointments_count"],
                activity_map[aid]["visits_count"],
                activity_map[aid]["total_activity"],
            ),
            reverse=True,
        )
    elif metric == "visits":
        sorted_ids = sorted(
            all_animal_ids,
            key=lambda aid: (
                activity_map[aid]["visits_count"],
                activity_map[aid]["appointments_count"],
                activity_map[aid]["total_activity"],
            ),
            reverse=True,
        )
    else:  # total
        sorted_ids = sorted(
            all_animal_ids,
            key=lambda aid: (
                activity_map[aid]["total_activity"],
                activity_map[aid]["visits_count"],
                activity_map[aid]["appointments_count"],
            ),
            reverse=True,
        )

    top_ids = sorted_ids[:limit]

    # Fetch Animal objects with select_related client
    animals_by_id = {
        animal.pk: animal
        for animal in Animal.objects.alive()
        .filter(pk__in=top_ids)
        .select_related("client")
    }

    results = []
    for aid in top_ids:
        animal = animals_by_id.get(aid)
        if animal:
            animal.appointments_count = activity_map[aid]["appointments_count"]
            animal.visits_count = activity_map[aid]["visits_count"]
            animal.total_activity = activity_map[aid]["total_activity"]
            results.append(animal)

    return results, period, metric, limit


@login_required
def top_patients_partial(request):
    """HTMX partial endpoint for dynamic filtering of top active patients."""
    period = request.GET.get("top_period", "this_month")
    metric = request.GET.get("top_metric", "total")
    limit = request.GET.get("top_limit", 10)

    top_patients, top_period, top_metric, top_limit = get_top_active_patients(
        request.user, period=period, metric=metric, limit=limit
    )

    context = {
        "top_patients": top_patients,
        "top_period": top_period,
        "top_metric": top_metric,
        "top_limit": top_limit,
    }
    return render(request, "dashboard/includes/top_patients_card.html", context)


@login_required
def dashboard(request):
    """
    Main Clinic Executive Dashboard.
    Provides real-time Daily Pulse highlights, tabbed comprehensive statistics,
    visit services breakdown, today's schedule, and urgent operational queues.
    """
    today = timezone.localdate()

    # 1. Daily Pulse (Today's Quick Highlights)
    today_appointments_qs = Appointment.objects.alive().filter(date=today).select_related(
        "animal", "animal__client", "doctor"
    ).order_by("time")

    if request.user.is_authenticated and getattr(request.user, "role", None) == User.Role.VET and not can_view_all_patients(request.user):
        today_appointments_qs = today_appointments_qs.filter(doctor=request.user)

    today_appointments_count = today_appointments_qs.count()
    today_visits_count = MedicalRecord.objects.alive().filter(date_time__date=today).count()
    urgent_reminders_count = Reminder.objects.alive().filter(
        status=Reminder.Status.PENDING,
        due_date__lte=today
    ).count()
    new_patients_today_count = Animal.objects.alive().filter(created_at__date=today).count()

    # 2. Patients & Clients Domain
    total_patients_count = Animal.objects.alive().count()
    cats_count = Animal.objects.alive().filter(species=Animal.Species.CAT).count()
    dogs_count = Animal.objects.alive().filter(species=Animal.Species.DOG).count()
    birds_count = Animal.objects.alive().filter(species=Animal.Species.BIRD).count()
    other_species_count = Animal.objects.alive().exclude(
        species__in=[Animal.Species.CAT, Animal.Species.DOG, Animal.Species.BIRD]
    ).count()
    total_clients_count = Client.objects.alive().count()
    clients_with_pets_count = Client.objects.alive().filter(animals__deleted_at__isnull=True).distinct().count()

    # Top frequent patients using flexible, high-performance querying
    top_patients, top_period, top_metric, top_limit = get_top_active_patients(
        request.user, period="this_month", metric="total", limit=10
    )

    # 3. Clinical & Services Domain
    clinical_records_qs = get_visible_clinical_records(request.user, MedicalRecord.objects.alive())
    clinical_visits_count = clinical_records_qs.count()

    # Precise medical procedures classification
    vaccination_records_count = clinical_records_qs.filter(
        Q(record_type=MedicalRecord.RecordType.VACCINATION) |
        (~Q(vaccine_name="") & Q(vaccine_name__isnull=False)) |
        Q(vaccination_records__is_deleted=False)
    ).distinct().count()

    surgery_count = clinical_records_qs.filter(
        record_type=MedicalRecord.RecordType.SURGERY
    ).count()

    emergency_count = clinical_records_qs.filter(
        record_type=MedicalRecord.RecordType.EMERGENCY
    ).count()

    checkup_count = clinical_records_qs.filter(
        Q(record_type__in=[MedicalRecord.RecordType.CHECKUP, MedicalRecord.RecordType.VISIT]),
        Q(vaccine_name="") | Q(vaccine_name__isnull=True),
        Q(vaccination_records__is_deleted=True) | Q(vaccination_records__isnull=True)
    ).exclude(
        record_type__in=[
            MedicalRecord.RecordType.SURGERY,
            MedicalRecord.RecordType.EMERGENCY,
            MedicalRecord.RecordType.VACCINATION,
        ]
    ).distinct().count()

    other_procedures_count = max(
        0,
        clinical_visits_count - (checkup_count + surgery_count + emergency_count + vaccination_records_count)
    )

    # Clinical Services Stats
    total_services_count = VisitService.objects.filter(medical_record__deleted_at__isnull=True).count()
    top_services = list(
        VisitService.objects.filter(medical_record__deleted_at__isnull=True)
        .values("name")
        .annotate(count=Count("id"))
        .order_by("-count")[:6]
    )
    catalog_services_count = VisitServiceCatalogItem.objects.filter(is_active=True).count()

    # 4. Appointments & Reminders Domain
    scheduled_count = Appointment.objects.alive().filter(status=Appointment.Status.SCHEDULED).count()
    completed_appointments_count = Appointment.objects.alive().filter(status=Appointment.Status.COMPLETED).count()
    cancelled_appointments_count = Appointment.objects.alive().filter(status=Appointment.Status.CANCELLED).count()
    total_appointments_count = Appointment.objects.alive().count()

    pending_reminders_count = Reminder.objects.alive().filter(status=Reminder.Status.PENDING).count()
    converted_reminders_count = Reminder.objects.alive().filter(status=Reminder.Status.CONVERTED).count()
    total_reminders_count = Reminder.objects.alive().count()

    # 5. Clinic Staff & System Domain (Admin Only)
    is_admin = request.user.is_superuser or (hasattr(request.user, "role") and request.user.role == User.Role.ADMIN)
    total_users_count = User.objects.count() if is_admin else 0
    vets_count = User.objects.filter(role=User.Role.VET).count() if is_admin else 0
    staff_count = User.objects.filter(role=User.Role.STAFF).count() if is_admin else 0
    active_users_count = User.objects.filter(is_active=True).count() if is_admin else 0

    # 6. Chart Analytics Datasets (Visual BI)
    arabic_days = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    dates_7d = [today - timedelta(days=i) for i in range(6, -1, -1)]
    chart_labels_7d = [f"{arabic_days[d.weekday()]} ({d.strftime('%m/%d')})" for d in dates_7d]

    visits_7d = []
    appointments_7d = []
    for d in dates_7d:
        v_count = MedicalRecord.objects.alive().filter(date_time__date=d).count()
        a_count = Appointment.objects.alive().filter(date=d).count()
        visits_7d.append(v_count)
        appointments_7d.append(a_count)

    species_labels = ["القطط", "الكلاب", "الطيور", "فصائل أخرى"]
    species_data = [cats_count, dogs_count, birds_count, other_species_count]

    procedures_labels = ["فحوصات وزيارات", "عمليات جراحية", "طوارئ وإسعاف", "تطعيمات ولقاحات"]
    procedures_data = [checkup_count, surgery_count, emergency_count, vaccination_records_count]
    if other_procedures_count > 0:
        procedures_labels.append("إجراءات أخرى")
        procedures_data.append(other_procedures_count)

    services_chart_labels = [srv["name"] for srv in top_services] or ["لا توجد خدمات مسجلة"]
    services_chart_data = [srv["count"] for srv in top_services] or [0]

    completion_rate = round((completed_appointments_count / total_appointments_count * 100), 1) if total_appointments_count > 0 else 0
    cancellation_rate = round((cancelled_appointments_count / total_appointments_count * 100), 1) if total_appointments_count > 0 else 0
    scheduled_rate = round((scheduled_count / total_appointments_count * 100), 1) if total_appointments_count > 0 else 0

    context = {
        "today": today,
        # Daily Pulse
        "today_appointments_count": today_appointments_count,
        "today_visits_count": today_visits_count,
        "urgent_reminders_count": urgent_reminders_count,
        "new_patients_today_count": new_patients_today_count,
        # Patients & Clients
        "total_patients_count": total_patients_count,
        "cats_count": cats_count,
        "dogs_count": dogs_count,
        "birds_count": birds_count,
        "other_species_count": other_species_count,
        "total_clients_count": total_clients_count,
        "clients_with_pets_count": clients_with_pets_count,
        "top_patients": top_patients,
        "top_period": top_period,
        "top_metric": top_metric,
        "top_limit": top_limit,
        # Clinical & Services
        "clinical_visits_count": clinical_visits_count,
        "checkup_count": checkup_count,
        "surgery_count": surgery_count,
        "emergency_count": emergency_count,
        "vaccination_records_count": vaccination_records_count,
        "other_procedures_count": other_procedures_count,
        "total_services_count": total_services_count,
        "top_services": top_services,
        "catalog_services_count": catalog_services_count,
        # Appointments & Reminders
        "total_appointments_count": total_appointments_count,
        "scheduled_count": scheduled_count,
        "completed_appointments_count": completed_appointments_count,
        "cancelled_appointments_count": cancelled_appointments_count,
        "total_reminders_count": total_reminders_count,
        "pending_reminders_count": pending_reminders_count,
        "converted_reminders_count": converted_reminders_count,
        "completion_rate": completion_rate,
        "cancellation_rate": cancellation_rate,
        "scheduled_rate": scheduled_rate,
        # Staff & System
        "is_admin": is_admin,
        "total_users_count": total_users_count,
        "vets_count": vets_count,
        "staff_count": staff_count,
        "active_users_count": active_users_count,
        # JSON Chart Datasets for Frontend Rendering
        "chart_labels_7d_json": json.dumps(chart_labels_7d, ensure_ascii=False),
        "visits_7d_json": json.dumps(visits_7d),
        "appointments_7d_json": json.dumps(appointments_7d),
        "species_labels_json": json.dumps(species_labels, ensure_ascii=False),
        "species_data_json": json.dumps(species_data),
        "procedures_labels_json": json.dumps(procedures_labels, ensure_ascii=False),
        "procedures_data_json": json.dumps(procedures_data),
        "services_chart_labels_json": json.dumps(services_chart_labels, ensure_ascii=False),
        "services_chart_data_json": json.dumps(services_chart_data),
    }
    return render(request, "dashboard/dashboard.html", context)


def custom_403_view(request, exception=None):
    """Custom 403 Forbidden handler rendering polite Arabic UI."""
    return render(request, "403.html", {"exception": str(exception) if exception else None}, status=403)


def custom_404_view(request, exception=None):
    """Custom 404 Not Found handler rendering polite Arabic UI."""
    return render(request, "404.html", status=404)


def custom_500_view(request):
    """Custom 500 Server Error handler."""
    return render(request, "404.html", status=500)

