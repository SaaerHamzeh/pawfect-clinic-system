from datetime import date, timedelta
from django.test import TestCase, Client as HttpClient
from django.urls import reverse
from django.utils import timezone
import openpyxl
import io

from apps.accounts.models import User
from apps.clients.models import Client
from apps.patients.models import Animal
from apps.clinical.models import MedicalRecord, VaccinationRecord, VisitService, FileAttachment
from apps.appointments.models import Appointment
from apps.reminders.models import Reminder
from apps.audit.models import AuditLog


class ReportsModuleTests(TestCase):
    def setUp(self):
        self.client = HttpClient()

        # Admin user (has all permissions)
        self.admin_user = User.objects.create_superuser(
            username="admin_rep",
            password="password123",
            role=User.Role.ADMIN,
            first_name="Admin",
            last_name="Test"
        )

        # Staff user with reports permission
        self.staff_with_rep = User.objects.create_user(
            username="staff_rep",
            password="password123",
            role=User.Role.STAFF,
            first_name="Staff",
            last_name="Reporter"
        )
        from django.contrib.auth.models import Permission
        rep_perm = Permission.objects.get(codename="can_view_reports")
        self.staff_with_rep.user_permissions.add(rep_perm)

        # Staff user without reports permission
        self.staff_no_rep = User.objects.create_user(
            username="staff_norep",
            password="password123",
            role=User.Role.STAFF,
            first_name="Staff",
            last_name="NoRep"
        )

        # Sample Client & Patient
        self.test_client = Client.objects.create(
            full_name="طارق الخالد",
            phone="0911223344",
            address="دمشق"
        )

        self.test_patient = Animal.objects.create(
            client=self.test_client,
            name="سيمبا",
            species=Animal.Species.CAT,
            breed="شيرازي",
            gender=Animal.Gender.MALE,
            weight=4.5
        )

        # Clinical record with service and attachment
        self.test_record = MedicalRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin_user,
            date_time=timezone.now(),
            symptoms="فقدان شهية",
            diagnosis="التهاب بسيط في المعدة",
            treatment="مضاد حيوي",
            prescription="أموكسيسيلين",
            weight_at_visit=4.5
        )
        VisitService.objects.create(
            medical_record=self.test_record,
            name="حقنة مضاد حيوي"
        )

        # Vaccination
        self.test_vaccine = VaccinationRecord.objects.create(
            animal=self.test_patient,
            doctor=self.admin_user,
            vaccine_name="تطعيم الثلاثي للقطط",
            batch_number="VAC-101",
            date_administered=timezone.localdate() - timedelta(days=30),
            next_due_date=timezone.localdate() + timedelta(days=5)
        )

        # Appointment
        self.test_appt = Appointment.objects.create(
            animal=self.test_patient,
            doctor=self.admin_user,
            created_by=self.staff_with_rep,
            date=timezone.localdate(),
            time="10:00:00",
            duration=30,
            appointment_type=Appointment.AppointmentType.CHECKUP,
            status=Appointment.Status.SCHEDULED,
            notes="فحص روتيني دوري"
        )

        # Reminder
        self.test_reminder = Reminder.objects.create(
            animal=self.test_patient,
            reminder_type=Reminder.ReminderType.VACCINATION,
            due_date=timezone.localdate() + timedelta(days=5),
            status=Reminder.Status.PENDING,
            notes="تذكير بجرعة اللقاح القادمة"
        )

    def test_reports_permission_denied_for_unauthorized_user(self):
        """User without can_view_reports should receive 403 Forbidden."""
        self.client.force_login(self.staff_no_rep)
        response = self.client.get(reverse("reports:reports"))
        self.assertEqual(response.status_code, 403)

    def test_reports_dashboard_accessible_by_authorized_user(self):
        """User with can_view_reports should successfully view reports dashboard."""
        self.client.force_login(self.staff_with_rep)
        response = self.client.get(reverse("reports:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reports/reports.html")
        self.assertContains(response, "سجل وتقارير المرضى")

    def test_api_client_patients(self):
        """JSON endpoint should return client's alive pets."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:api_client_patients", args=[self.test_client.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["patients"]), 1)
        self.assertEqual(data["patients"][0]["name"], "سيمبا")

    def test_export_patient_medical_report_xlsx(self):
        """Exporting patient medical report should return valid multi-sheet Excel file."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_patient", args=[self.test_patient.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertIn("attachment; filename=", response["Content-Disposition"])

        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet_names = wb.sheetnames
        self.assertIn("البيانات الأساسية", sheet_names)
        self.assertIn("السجل السريري وتاريخ الزيارات", sheet_names)
        self.assertIn("سجل التطعيمات والجرعات", sheet_names)

        log = AuditLog.objects.filter(
            user=self.staff_with_rep,
            action=AuditLog.Action.EXPORT,
            entity_type="MedicalReport",
            entity_id=str(self.test_patient.pk)
        ).first()
        self.assertIsNotNone(log)

    def test_export_due_vaccinations_xlsx(self):
        """Due vaccinations export should return Excel with vaccination rows."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_vaccinations") + "?due=month"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("التطعيمات المستحقة", wb.sheetnames)

    def test_export_appointments_xlsx(self):
        """Appointments export should return Excel with appointment details."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_appointments")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("سجل المواعيد", wb.sheetnames)

    def test_export_directory_xlsx(self):
        """Directory export should return complete client and pet list in Excel."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_directory")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("دليل العملاء والمرضى", wb.sheetnames)

    def test_export_custom_unified_report_clinical_xlsx(self):
        """Unified custom export should generate clinical records Excel workbook with services."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_custom") + "?domain=clinical&record_type=all&include_services=true"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("السجلات والزيارات السريرية", wb.sheetnames)
        ws = wb["السجلات والزيارات السريرية"]
        headers = [cell.value for cell in ws[4]]
        self.assertIn("الخدمات المنفذة", headers)
        self.assertIn("المرفقات", headers)

    def test_export_custom_unified_report_reminders_xlsx(self):
        """Unified custom export should generate reminders Excel workbook."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_custom") + "?domain=reminders&status=all&species=CAT"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("سجل التذكيرات والمتابعات", wb.sheetnames)

    def test_export_custom_unified_report_all_patients_registry(self):
        """Selecting all clients / leaving patient empty should export full patients registry."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_custom") + "?domain=patient"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertIn("Custom_Patients_Registry_", response["Content-Disposition"])
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("دليل وسجل المرضى", wb.sheetnames)
        ws = wb["دليل وسجل المرضى"]
        headers = [cell.value for cell in ws[4]]
        self.assertIn("اسم الحيوان", headers)
        self.assertIn("اسم المالك الكامل", headers)

    def test_export_custom_unified_report_patient_5_sheets(self):
        """When a patient is selected with appointments and reminders, export 5-sheet workbook."""
        self.client.force_login(self.staff_with_rep)
        url = (
            reverse("reports:export_custom") +
            f"?domain=patient&patient_id={self.test_patient.pk}"
            "&include_basic=true&include_clinical=true&include_vaccines=true"
            "&include_appointments=true&include_reminders=true"
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertEqual(len(wb.sheetnames), 5)
        self.assertIn("البيانات الأساسية", wb.sheetnames)
        self.assertIn("السجل السريري وتاريخ الزيارات", wb.sheetnames)
        self.assertIn("سجل التطعيمات والجرعات", wb.sheetnames)
        self.assertIn("سجل المواعيد والزيارات", wb.sheetnames)
        self.assertIn("سجل التذكيرات والمتابعات", wb.sheetnames)

    def test_export_custom_unified_report_vaccinations_scope_all(self):
        """Exporting vaccinations with scope=all should export complete historical archive."""
        self.client.force_login(self.staff_with_rep)
        url = reverse("reports:export_custom") + "?domain=vaccinations&scope=all"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        self.assertIn("سجل كافة التطعيمات", wb.sheetnames)

    def test_export_with_malformed_dates_and_ids_does_not_crash(self):
        """Passing invalid dates or non-numeric IDs must not raise 500 DataError."""
        self.client.force_login(self.staff_with_rep)
        # Malformed appointments export
        url_appts = reverse("reports:export_appointments") + "?start_date=invalid-date&end_date=9999-99-99&doctor_id=bad_id"
        res_appts = self.client.get(url_appts)
        self.assertEqual(res_appts.status_code, 200)

        # Malformed clinical export
        url_clin = reverse("reports:export_custom") + "?domain=clinical&start_date=not-a-date&doctor_id=xyz&client_id=abc"
        res_clin = self.client.get(url_clin)
        self.assertEqual(res_clin.status_code, 200)

        # Malformed registry export
        url_reg = reverse("reports:export_custom") + "?domain=patient&start_date=2026/09/22&client_id=not_an_int"
        res_reg = self.client.get(url_reg)
        self.assertEqual(res_reg.status_code, 200)

