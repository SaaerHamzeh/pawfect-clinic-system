from django.db import migrations


def seed_initial_taxonomies(apps, schema_editor):
    AnimalSpecies = apps.get_model("settings", "AnimalSpecies")
    AnimalBreed = apps.get_model("settings", "AnimalBreed")
    ClinicalVisitType = apps.get_model("settings", "ClinicalVisitType")
    AppointmentTypeConfig = apps.get_model("settings", "AppointmentTypeConfig")
    VaccineCatalogItem = apps.get_model("settings", "VaccineCatalogItem")
    VisitServiceCatalogItem = apps.get_model("settings", "VisitServiceCatalogItem")

    # 1. Species
    species_data = [
        {"name": "قطة", "code": "CAT", "icon": "🐱", "is_system": True, "order": 1},
        {"name": "كلب", "code": "DOG", "icon": "🐶", "is_system": True, "order": 2},
        {"name": "طائر", "code": "BIRD", "icon": "🦜", "is_system": True, "order": 3},
        {"name": "أرنب", "code": "RABBIT", "icon": "🐰", "is_system": False, "order": 4},
        {"name": "أخرى", "code": "OTHER", "icon": "🐾", "is_system": True, "order": 5},
    ]
    created_species = {}
    for item in species_data:
        obj, _ = AnimalSpecies.objects.get_or_create(code=item["code"], defaults=item)
        created_species[item["code"]] = obj

    # 2. Breeds
    breeds_data = [
        # Cat breeds
        ("CAT", "شيرازي (فارسي)"),
        ("CAT", "هيمالايا"),
        ("CAT", "سيامي"),
        ("CAT", "بريطاني قصير الشعر"),
        ("CAT", "سكوتش فولد"),
        ("CAT", "بلدي / هجين"),
        # Dog breeds
        ("DOG", "جيرمن شيبرد"),
        ("DOG", "غولدن ريتريفر"),
        ("DOG", "هاسكي"),
        ("DOG", "بيتبول"),
        ("DOG", "لابرادور"),
        ("DOG", "جرو بلدي"),
    ]
    for sp_code, breed_name in breeds_data:
        if sp_code in created_species:
            AnimalBreed.objects.get_or_create(
                species=created_species[sp_code],
                name=breed_name,
                defaults={"is_active": True}
            )

    # 3. Clinical Visit Types
    visit_types = [
        {"name": "زيارة سريرية عامة", "code": "VISIT", "icon": "🩺", "color": "#1099a7", "requires_vaccine_logic": False, "is_system": True, "order": 1},
        {"name": "فحص دوري شامل", "code": "CHECKUP", "icon": "🔍", "color": "#0284c7", "requires_vaccine_logic": False, "is_system": True, "order": 2},
        {"name": "تطعيم ووقاية", "code": "VACCINATION", "icon": "💉", "color": "#10b981", "requires_vaccine_logic": True, "is_system": True, "order": 3},
        {"name": "إجراء جراحي", "code": "SURGERY", "icon": "✂️", "color": "#ef4444", "requires_vaccine_logic": False, "is_system": True, "order": 4},
        {"name": "طوارئ", "code": "EMERGENCY", "icon": "🚨", "color": "#dc2626", "requires_vaccine_logic": False, "is_system": True, "order": 5},
    ]
    for item in visit_types:
        ClinicalVisitType.objects.get_or_create(code=item["code"], defaults=item)

    # 4. Appointment Types
    appt_types = [
        {"name": "فحص دوري / استشارة", "code": "CHECKUP", "default_duration": 30, "color": "#0ea5e9", "is_system": True, "order": 1},
        {"name": "علاج / متابعة", "code": "TREATMENT", "default_duration": 30, "color": "#1099a7", "is_system": True, "order": 2},
        {"name": "تطعيم ووقاية", "code": "VACCINATION", "default_duration": 15, "color": "#10b981", "is_system": True, "order": 3},
        {"name": "حمام وتجفيف", "code": "BATH", "default_duration": 45, "color": "#6366f1", "is_system": False, "order": 4},
        {"name": "عناية وتنظيف (Grooming)", "code": "GROOMING", "default_duration": 60, "color": "#8b5cf6", "is_system": False, "order": 5},
        {"name": "إجراء جراحي", "code": "SURGERY", "default_duration": 90, "color": "#ef4444", "is_system": True, "order": 6},
        {"name": "حالة طارئة", "code": "EMERGENCY", "default_duration": 45, "color": "#dc2626", "is_system": True, "order": 7},
    ]
    for item in appt_types:
        AppointmentTypeConfig.objects.get_or_create(code=item["code"], defaults=item)

    # 5. Vaccine Catalog
    vaccines = [
        {"name": "التطعيم الرباعي للقطط (FVRCP)", "target_species": created_species.get("CAT"), "default_validity_days": 365, "notes": "يحمي من طاعون القطط وفيروسات الجهاز التنفسي"},
        {"name": "لقاح السعار (Rabies)", "target_species": None, "default_validity_days": 365, "notes": "لقاح وقائي إلزامي سنوي لجميع الحيوانات"},
        {"name": "التطعيم الخماسي / السداسي للكلاب (DHPPi)", "target_species": created_species.get("DOG"), "default_validity_days": 365, "notes": "يحمي من البارفو والديستمبر والتهاب الكبد"},
        {"name": "تطعيم السعال الديكي للكلاب (Kennel Cough)", "target_species": created_species.get("DOG"), "default_validity_days": 180, "notes": "كل 6 أشهر للكلاب المخالطة"},
        {"name": "تطعيم فطريات الجلد (Microsporum)", "target_species": created_species.get("CAT"), "default_validity_days": 365, "notes": "وقائي / علاجي حسب البروتوكول"},
    ]
    for item in vaccines:
        VaccineCatalogItem.objects.get_or_create(name=item["name"], defaults=item)

    # 6. Services
    services = [
        {"name": "قص وتقليم الأظافر", "default_notes": "تنظيف وقص أظافر الأطراف الأربعة", "order": 1},
        {"name": "تنظيف وتطهير الأذنين", "default_notes": "إزالة الشمع والفحص بالمجهر", "order": 2},
        {"name": "إفراغ الغدد الشرجية", "default_notes": "تنظيف وقائي للغدد الشرجية", "order": 3},
        {"name": "حقن وريدي / تحت الجلد", "default_notes": "إعطاء المحاليل أو الأدوية العلاجية", "order": 4},
        {"name": "تضميد وتطهير جروح", "default_notes": "تنظيف الجرح ووضع ضمادة معقمة", "order": 5},
    ]
    for item in services:
        VisitServiceCatalogItem.objects.get_or_create(name=item["name"], defaults=item)


class Migration(migrations.Migration):

    dependencies = [
        ("settings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_initial_taxonomies, migrations.RunPython.noop),
    ]
