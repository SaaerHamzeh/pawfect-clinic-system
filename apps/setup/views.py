import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import get_user_model, login
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import transaction

from apps.settings.models import (
    AnimalSpecies,
    ClinicalVisitType,
    VaccineCatalogItem,
    VisitServiceCatalogItem,
)
from apps.audit.models import AuditLog
from apps.core.utils import get_client_ip

User = get_user_model()


def get_default_taxonomies_payload():
    """Ensure standard default clinic data exists and return it for wizard customization."""
    # 1. Species
    default_species = [
        {
            "name": "قطة",
            "code": "CAT",
            "icon": "🐱",
            "is_system": True,
            "order": 1,
            "is_active": True,
        },
        {
            "name": "كلب",
            "code": "DOG",
            "icon": "🐶",
            "is_system": True,
            "order": 2,
            "is_active": True,
        },
        {
            "name": "طائر",
            "code": "BIRD",
            "icon": "🦜",
            "is_system": True,
            "order": 3,
            "is_active": True,
        },
        {
            "name": "أرنب",
            "code": "RABBIT",
            "icon": "🐰",
            "is_system": False,
            "order": 4,
            "is_active": True,
        },
        {
            "name": "أخرى",
            "code": "OTHER",
            "icon": "🐾",
            "is_system": True,
            "order": 5,
            "is_active": True,
        },
    ]
    for sp in default_species:
        AnimalSpecies.objects.get_or_create(name=sp["name"], defaults=sp)

    # 2. Visit Types
    default_visit_types = [
        {
            "name": "زيارة سريرية عامة",
            "code": "VISIT",
            "icon": "🩺",
            "color": "#1099a7",
            "order": 1,
            "is_active": True,
        },
        {
            "name": "فحص دوري شامل",
            "code": "CHECKUP",
            "icon": "🔍",
            "color": "#0284c7",
            "order": 2,
            "is_active": True,
        },
        {
            "name": "تطعيم ووقاية",
            "code": "VACCINATION",
            "icon": "💉",
            "color": "#10b981",
            "order": 3,
            "requires_vaccine_logic": True,
            "is_active": True,
        },
        {
            "name": "إجراء جراحي",
            "code": "SURGERY",
            "icon": "✂️",
            "color": "#ef4444",
            "order": 4,
            "is_active": True,
        },
        {
            "name": "طوارئ",
            "code": "EMERGENCY",
            "icon": "🚨",
            "color": "#dc2626",
            "order": 5,
            "is_active": True,
        },
    ]
    for vt in default_visit_types:
        ClinicalVisitType.objects.get_or_create(code=vt["code"], defaults=vt)

    # 3. Clinical Services
    default_services = [
        {"name": "فحص سريري شامل", "is_active": True, "order": 1},
        {"name": "علاج جروح وتضميد", "is_active": True, "order": 2},
        {"name": "قص أظافر", "is_active": True, "order": 3},
        {"name": "تنظيف وتعقيم أذنين", "is_active": True, "order": 4},
        {"name": "حمام طبي وتجفيف", "is_active": True, "order": 5},
        {"name": "حقن وعلاج بالعيادة", "is_active": True, "order": 6},
    ]
    for srv in default_services:
        VisitServiceCatalogItem.objects.get_or_create(name=srv["name"], defaults=srv)

    # 4. Standard Vaccines
    default_vaccines = [
        {
            "name": "اللقاح الثلاثي للقطط (Tricat)",
            "default_validity_days": 365,
            "is_active": True,
            "order": 1,
        },
        {
            "name": "اللقاح الرباعي للقطط (Quadricat)",
            "default_validity_days": 365,
            "is_active": True,
            "order": 2,
        },
        {
            "name": "لقاح السعار (Rabies)",
            "default_validity_days": 365,
            "is_active": True,
            "order": 3,
        },
        {
            "name": "اللقاح الخماسي للكلاب (DHPPi)",
            "default_validity_days": 365,
            "is_active": True,
            "order": 4,
        },
    ]
    for vac in default_vaccines:
        VaccineCatalogItem.objects.get_or_create(name=vac["name"], defaults=vac)

    return {
        "species": list(AnimalSpecies.objects.all().order_by("order")),
        "services": list(VisitServiceCatalogItem.objects.all().order_by("order")),
        "vaccines": list(VaccineCatalogItem.objects.all().order_by("order")),
    }


def wizard(request):
    """
    Renders the setup wizard view. If an active Admin already exists,
    redirects to dashboard or login.
    """
    has_admin = User.objects.filter(role=User.Role.ADMIN, is_active=True).exists()
    if has_admin:
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return redirect("accounts:login")

    taxonomies = get_default_taxonomies_payload()

    context = {
        "species_list": taxonomies["species"],
        "services_list": taxonomies["services"],
        "vaccines_list": taxonomies["vaccines"],
        "species_names_json": json.dumps([s.name for s in taxonomies["species"]]),
        "services_names_json": json.dumps([s.name for s in taxonomies["services"]]),
        "vaccines_names_json": json.dumps([s.name for s in taxonomies["vaccines"]]),
    }
    return render(request, "setup/wizard.html", context)


@require_POST
def complete_setup(request):
    """
    Handles the final submission of all 3 setup steps:
    1. Creates the primary Admin superuser.
    2. Creates any additional users (Vets, Staff) if provided.
    3. Customizes services, species, and vaccines according to Admin's selection.
    Logs in the new Admin and responds with JSON redirect.
    """
    has_admin = User.objects.filter(role=User.Role.ADMIN, is_active=True).exists()
    if has_admin:
        return JsonResponse(
            {"success": False, "error": "تم إكمال الإعداد الأولي للنظام مسبقاً."},
            status=400,
        )

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse(
            {"success": False, "error": "تنسيق البيانات غير صالح."}, status=400
        )

    admin_data = data.get("admin", {})
    users_data = data.get("users", [])
    customization_data = data.get("customizations", {})

    # 1. Validate Admin Data
    username = admin_data.get("username", "").strip()
    first_name = admin_data.get("first_name", "").strip()
    last_name = admin_data.get("last_name", "").strip()
    password = admin_data.get("password", "")
    password_confirm = admin_data.get("password_confirm", "")

    if not username or len(username) < 3:
        return JsonResponse(
            {
                "success": False,
                "error": "يرجى كتابة اسم مستخدم صالح للمدير (3 أحرف على الأقل).",
            },
            status=400,
        )
    if not first_name:
        return JsonResponse(
            {"success": False, "error": "يرجى كتابة الاسم الأول للمدير."}, status=400
        )
    if not password or len(password) < 6:
        return JsonResponse(
            {"success": False, "error": "كلمة المرور يجب أن لا تقل عن 6 خانات."},
            status=400,
        )
    if password != password_confirm:
        return JsonResponse(
            {"success": False, "error": "كلمة المرور وتأكيدها غير متطابقين."},
            status=400,
        )
    if User.objects.filter(username=username).exists():
        return JsonResponse(
            {"success": False, "error": f"اسم المستخدم «{username}» مستخدم مسبقاً."},
            status=400,
        )

    with transaction.atomic():
        # Create Admin superuser
        admin_user = User.objects.create_superuser(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.ADMIN,
            is_active=True,
        )

        # 2. Create Additional Users if any
        created_users_count = 0
        for u in users_data:
            u_username = u.get("username", "").strip()
            u_name = u.get("first_name", "").strip()
            u_role = u.get("role", User.Role.STAFF)
            u_pass = u.get("password", "")

            if (
                u_username
                and u_pass
                and not User.objects.filter(username=u_username).exists()
            ):
                if u_role not in [User.Role.VET, User.Role.STAFF]:
                    u_role = User.Role.STAFF
                new_u = User.objects.create_user(
                    username=u_username,
                    password=u_pass,
                    first_name=u_name,
                    role=u_role,
                    is_active=True,
                )
                from apps.accounts.models import ROLE_CORE_PERMISSIONS
                from django.contrib.auth.models import Permission
                from django.contrib.contenttypes.models import ContentType

                core_perms = ROLE_CORE_PERMISSIONS.get(u_role, [])
                if core_perms:
                    ct = ContentType.objects.get_for_model(User)
                    p_objs = Permission.objects.filter(
                        content_type=ct, codename__in=core_perms
                    )
                    new_u.user_permissions.set(p_objs)
                created_users_count += 1

        # 3. Apply Taxonomies & Customizations
        # Active Species
        active_species_names = customization_data.get("active_species", [])
        if active_species_names:
            AnimalSpecies.objects.filter(name__in=active_species_names).update(
                is_active=True
            )
            AnimalSpecies.objects.exclude(name__in=active_species_names).update(
                is_active=False
            )

        # New Species added during setup
        new_species = customization_data.get("new_species", [])
        for sp_name in new_species:
            sp_name = str(sp_name).strip()
            if sp_name and not AnimalSpecies.objects.filter(name=sp_name).exists():
                AnimalSpecies.objects.create(name=sp_name, is_active=True, icon="🐾")

        # Active Services
        active_service_names = customization_data.get("active_services", [])
        if active_service_names:
            VisitServiceCatalogItem.objects.filter(
                name__in=active_service_names
            ).update(is_active=True)
            VisitServiceCatalogItem.objects.exclude(
                name__in=active_service_names
            ).update(is_active=False)

        # New Services added during setup
        new_services = customization_data.get("new_services", [])
        for srv_name in new_services:
            srv_name = str(srv_name).strip()
            if (
                srv_name
                and not VisitServiceCatalogItem.objects.filter(name=srv_name).exists()
            ):
                VisitServiceCatalogItem.objects.create(name=srv_name, is_active=True)

        # Active Vaccines
        active_vaccine_names = customization_data.get("active_vaccines", [])
        if active_vaccine_names:
            VaccineCatalogItem.objects.filter(name__in=active_vaccine_names).update(
                is_active=True
            )
            VaccineCatalogItem.objects.exclude(name__in=active_vaccine_names).update(
                is_active=False
            )

        # New Vaccines added during setup
        new_vaccines = customization_data.get("new_vaccines", [])
        for vac_name in new_vaccines:
            vac_name = str(vac_name).strip()
            if (
                vac_name
                and not VaccineCatalogItem.objects.filter(name=vac_name).exists()
            ):
                VaccineCatalogItem.objects.create(
                    name=vac_name, is_active=True, default_validity_days=365
                )

        # Audit Log
        AuditLog.log(
            user=admin_user,
            action=AuditLog.Action.CREATE,
            entity=admin_user,
            entity_id=str(admin_user.pk),
            description=f"إكمال معالج الإعداد الأولي للنظام وإنشاء حساب المدير العام «{admin_user.username}» مع {created_users_count} مستخدم إضافي",
            ip_address=get_client_ip(request),
        )

        # Automatically log in the Admin user
        login(request, admin_user, backend="django.contrib.auth.backends.ModelBackend")

        from apps.accounts.services import (
            SESSION_RECOVERY_CODE_KEY,
            issue_new_recovery_code,
        )

        recovery_code = issue_new_recovery_code()
        request.session[SESSION_RECOVERY_CODE_KEY] = recovery_code

    return JsonResponse(
        {
            "success": True,
            "message": "تم إعداد النظام وتهيئة الحسابات بنجاح!",
            "redirect_url": reverse("accounts:recovery_code"),
            "recovery_code": recovery_code,
        }
    )
