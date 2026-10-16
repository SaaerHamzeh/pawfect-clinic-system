import random
import time
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.clients.models import Client
from apps.patients.models import Animal
from apps.appointments.models import Appointment
from apps.clinical.models import MedicalRecord, VaccinationRecord
from apps.settings.models import AnimalSpecies, AnimalBreed, ClinicalVisitType, VaccineCatalogItem


class Command(BaseCommand):
    help = "Generate high-volume realistic clinic data for scale and stress testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scale",
            type=str,
            choices=["test", "small", "medium", "large", "stress"],
            default="small",
            help="Predefined scale: test (100), small (1,000), medium (10,000), large (50,000), stress (100,000)",
        )
        parser.add_argument("--clients", type=int, help="Custom number of clients")
        parser.add_argument("--patients", type=int, help="Custom number of patients")
        parser.add_argument("--records", type=int, help="Custom number of clinical records")

    def handle(self, *args, **options):
        scale_map = {
            "test": {"clients": 100, "patients": 200, "records": 150},
            "small": {"clients": 1000, "patients": 2000, "records": 1500},
            "medium": {"clients": 10000, "patients": 20000, "records": 15000},
            "large": {"clients": 50000, "patients": 100000, "records": 75000},
            "stress": {"clients": 100000, "patients": 200000, "records": 150000},
        }

        scale_name = options["scale"]
        cfg = scale_map[scale_name]
        n_clients = options["clients"] or cfg["clients"]
        n_patients = options["patients"] or cfg["patients"]
        n_records = options["records"] or cfg["records"]

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 65))
        self.stdout.write(self.style.MIGRATE_HEADING("   PAWFECT CLINIC — STRESS DATA GENERATOR"))
        self.stdout.write(self.style.MIGRATE_HEADING(f"   Target Scale: {scale_name.upper()} ({n_clients:,} clients, {n_patients:,} patients)"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 65))

        start_time = time.time()

        # 1. Ensure Admin & Doctor accounts exist
        User = get_user_model()
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "first_name": "الدكتور",
                "last_name": "المدير",
                "role": User.Role.ADMIN,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if not admin_user.has_usable_password():
            admin_user.set_password("admin123")
            admin_user.save()

        vet_user, _ = User.objects.get_or_create(
            username="doctor_sami",
            defaults={
                "first_name": "د. سامي",
                "last_name": "البيطري",
                "role": User.Role.VET,
                "is_active": True,
            },
        )
        if not vet_user.has_usable_password():
            vet_user.set_password("vet123")
            vet_user.save()

        # 2. Ensure Catalogs
        species_cat, _ = AnimalSpecies.objects.get_or_create(name="قطة", defaults={"code": "CAT"})
        species_dog, _ = AnimalSpecies.objects.get_or_create(name="كلب", defaults={"code": "DOG"})
        visit_general, _ = ClinicalVisitType.objects.get_or_create(name="كشف عام", defaults={"color": "#0D9488"})
        vaccine_rabies, _ = VaccineCatalogItem.objects.get_or_create(
            name="لقاح السعار (Rabies)",
            defaults={"target_species": species_dog, "default_validity_days": 365},
        )

        first_names = ["أحمد", "محمد", "سامر", "عمر", "طارق", "رنا", "سارة", "مايا", "ليلى", "نور", "خالد", "يوسف"]
        last_names = ["الدمشقي", "الحلبي", "الشامي", "العطار", "الحكيم", "النجار", "الخليل", "الصالح", "حموي"]
        pet_names = ["بسبوس", "لولو", "ماكس", "روكي", "تومي", "سيمبا", "بيلا", "زيزو", "ريكس", "ميشو", "شمس"]

        # 3. Bulk Create Clients
        self.stdout.write(f"[*] Generating {n_clients:,} client records...")
        clients_batch = []
        base_client_id = Client.all_objects.count()

        for i in range(1, n_clients + 1):
            idx = base_client_id + i
            fn = random.choice(first_names)
            ln = random.choice(last_names)
            phone = f"09{idx % 100000000:08d}"
            clients_batch.append(
                Client(
                    full_name=f"{fn} {ln} #{idx}",
                    phone=phone,
                    address=f"دمشق - شارع {random.randint(1, 50)}",
                    notes="عميل دائم عبر النظام التجريبي",
                )
            )
            if len(clients_batch) >= 5000:
                Client.objects.bulk_create(clients_batch)
                clients_batch = []

        if clients_batch:
            Client.objects.bulk_create(clients_batch)

        client_ids = list(Client.objects.values_list("id", flat=True))
        self.stdout.write(self.style.SUCCESS(f" [OK] {len(client_ids):,} Clients ready."))

        # 4. Bulk Create Patients (Animals)
        self.stdout.write(f"[*] Generating {n_patients:,} patient records...")
        animals_batch = []
        base_animal_id = Animal.all_objects.count()

        for i in range(1, n_patients + 1):
            idx = base_animal_id + i
            species_choice = random.choice([Animal.Species.CAT, Animal.Species.DOG])
            cid = random.choice(client_ids)
            pname = random.choice(pet_names)
            animal_code = f"{idx:07d}"

            animals_batch.append(
                Animal(
                    animal_id=animal_code,
                    name=f"{pname} {idx}",
                    species=species_choice,
                    breed="سلالة نقية" if idx % 2 == 0 else "هجين",
                    gender=random.choice([Animal.Gender.MALE, Animal.Gender.FEMALE]),
                    birth_date=date.today() - timedelta(days=random.randint(60, 2500)),
                    weight=round(random.uniform(1.5, 35.0), 2),
                    color="رمادي مع أبيض",
                    client_id=cid,
                )
            )
            if len(animals_batch) >= 5000:
                Animal.objects.bulk_create(animals_batch)
                animals_batch = []

        if animals_batch:
            Animal.objects.bulk_create(animals_batch)

        animal_ids = list(Animal.objects.values_list("id", flat=True))
        self.stdout.write(self.style.SUCCESS(f" [OK] {len(animal_ids):,} Patients ready."))

        # 5. Bulk Create Appointments & Medical Records
        if n_records > 0:
            self.stdout.write(f"[*] Generating {n_records:,} medical records and visits...")
            med_batch = []
            now = timezone.now()

            for i in range(1, n_records + 1):
                aid = random.choice(animal_ids)
                med_batch.append(
                    MedicalRecord(
                        animal_id=aid,
                        doctor=vet_user,
                        record_type=MedicalRecord.RecordType.VISIT,
                        date_time=now - timedelta(days=random.randint(1, 180)),
                        symptoms="فحص دوري وقائي ومتابعة حالة الوزن",
                        diagnosis="الحالة الصحية ممتازة ولا توجد أعراض مرضية",
                        treatment="فيتامينات ومكملات غذائية يومياً",
                        weight_at_visit=round(random.uniform(2.0, 25.0), 2),
                    )
                )
                if len(med_batch) >= 5000:
                    MedicalRecord.objects.bulk_create(med_batch)
                    med_batch = []

            if med_batch:
                MedicalRecord.objects.bulk_create(med_batch)

            self.stdout.write(self.style.SUCCESS(f" [OK] {n_records:,} Medical records created."))

        elapsed = time.time() - start_time
        total_created = n_clients + n_patients + n_records
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(self.style.SUCCESS(f" [✓] COMPLETE: Successfully inserted {total_created:,} total records!"))
        self.stdout.write(self.style.SUCCESS(f" [✓] Total Time: {elapsed:.2f} seconds ({total_created / max(elapsed, 0.01):,.0f} records/sec)"))
        self.stdout.write(self.style.SUCCESS("=" * 65))
