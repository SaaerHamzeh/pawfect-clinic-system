import io
from datetime import datetime, date, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.utils import timezone
from django.db.models import Q

from apps.patients.models import Animal
from apps.clients.models import Client
from apps.clinical.models import MedicalRecord, VaccinationRecord, VisitService, FileAttachment
from apps.appointments.models import Appointment
from apps.reminders.models import Reminder
from apps.accounts.models import User


# ==============================================================================
# Styling Utilities
# ==============================================================================

# Colors - Matching Pawfect Clinic Brand Palette (Teal & Lavender Purple)
HEADER_FILL = PatternFill(start_color="1099A7", end_color="1099A7", fill_type="solid")  # Brand Teal
SUBHEADER_FILL = PatternFill(start_color="0E8794", end_color="0E8794", fill_type="solid")  # Darker Teal
SECTION_FILL = PatternFill(start_color="EEF9FA", end_color="EEF9FA", fill_type="solid")  # Brand Light Teal
ZEBRA_FILL = PatternFill(start_color="F7FCFC", end_color="F7FCFC", fill_type="solid")  # Crisp Subtle Tint
ACCENT_PURPLE = PatternFill(start_color="F3E8FF", end_color="F3E8FF", fill_type="solid") # Paw Accent
ACCENT_GREEN = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
ACCENT_RED = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
ACCENT_AMBER = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
ACCENT_BLUE = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")

# Fonts
TITLE_FONT = Font(name="Calibri", size=16, bold=True, color="0F2A3A")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BOLD_FONT = Font(name="Calibri", size=10, bold=True, color="0F172A")
NORMAL_FONT = Font(name="Calibri", size=10, bold=False, color="334155")
MUTED_FONT = Font(name="Calibri", size=9, italic=True, color="64748B")

# Alignments
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")

# Borders
THIN_SIDE = Side(border_style="thin", color="E2E8F0")
CELL_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
HEADER_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=Side(border_style="medium", color="096F7B"))


def apply_sheet_rtl_and_auto_widths(ws):
    """Sets Right-To-Left view orientation and computes reasonable column widths."""
    ws.views.sheetView[0].rightToLeft = True
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        # Bounded between 12 and 55
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 55)


def add_title_header(ws, title_text, subtitle_text=None, col_span=6):
    """Adds clinic branding header at the top of a worksheet."""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_span)
    title_cell = ws.cell(row=1, column=1, value=f"🐾 عيادة باوفيكت البيطرية — {title_text}")
    title_cell.font = TITLE_FONT
    title_cell.alignment = ALIGN_RIGHT
    ws.row_dimensions[1].height = 30

    if subtitle_text:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=col_span)
        sub_cell = ws.cell(row=2, column=1, value=f"{subtitle_text} — تم استخراج التقرير: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}")
        sub_cell.font = MUTED_FONT
        sub_cell.alignment = ALIGN_RIGHT
        ws.row_dimensions[2].height = 20
        return 4
    return 3


def parse_date_safely(val):
    """Safely converts input string or date/datetime to a date object or None."""
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_int_safely(val):
    """Safely converts input string to integer or None."""
    if not val or val == "all":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ==============================================================================
# 1. Patient Medical Dossier (Multi-Sheet: Basic Info, Clinical, Vaccines, Appts, Reminders)
# ==============================================================================

def generate_patient_medical_report_xlsx(
    animal,
    include_basic=True,
    include_clinical=True,
    include_vaccines=True,
    include_appointments=False,
    include_reminders=False,
    include_services=True,
):
    """
    Generates a comprehensive multi-sheet Excel workbook for a single animal:
    - Sheet 1: Basic Information (Owner & Pet biodata)
    - Sheet 2: Clinical History (Visits, diagnosis, prescriptions, services, attachments count)
    - Sheet 3: Vaccination History (Vaccines, intervals, next due)
    - Sheet 4 (Optional): Appointments History
    - Sheet 5 (Optional): Reminders History
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ----------------------------------------------------
    # Sheet 1: البيانات الأساسية (Basic Info)
    # ----------------------------------------------------
    if include_basic:
        ws1 = wb.create_sheet(title="البيانات الأساسية")
        current_row = add_title_header(
            ws1,
            title_text=f"البيانات التعريفية للمريض: {animal.name}",
            subtitle_text=f"ملف المريض رقم #{animal.pk}",
            col_span=4
        )

        # Section: Owner Information
        ws1.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        sec1 = ws1.cell(row=current_row, column=1, value="1. بيانات المالك الدائم (Owner Info)")
        sec1.font = Font(name="Calibri", size=11, bold=True, color="1E3A8A")
        sec1.fill = SECTION_FILL
        sec1.alignment = ALIGN_RIGHT
        ws1.row_dimensions[current_row].height = 24
        current_row += 1

        owner_fields = [
            ("اسم المالك الكامل", animal.client.full_name, "رقم هاتف المالك", animal.client.phone),
            ("عنوان المالك", animal.client.address or "غير محدد", "تاريخ تسجيل العميل", animal.client.created_at.strftime("%Y-%m-%d")),
            ("ملاحظات المالك", animal.client.notes or "لا يوجد", "", ""),
        ]
        for f1_label, f1_val, f2_label, f2_val in owner_fields:
            c1 = ws1.cell(row=current_row, column=1, value=f1_label); c1.font = BOLD_FONT; c1.alignment = ALIGN_RIGHT; c1.border = CELL_BORDER
            c2 = ws1.cell(row=current_row, column=2, value=f1_val); c2.font = NORMAL_FONT; c2.alignment = ALIGN_RIGHT; c2.border = CELL_BORDER
            c3 = ws1.cell(row=current_row, column=3, value=f2_label); c3.font = BOLD_FONT; c3.alignment = ALIGN_RIGHT; c3.border = CELL_BORDER
            c4 = ws1.cell(row=current_row, column=4, value=f2_val); c4.font = NORMAL_FONT; c4.alignment = ALIGN_RIGHT; c4.border = CELL_BORDER
            ws1.row_dimensions[current_row].height = 22
            current_row += 1

        current_row += 1

        # Section: Animal Information
        ws1.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        sec2 = ws1.cell(row=current_row, column=1, value="2. بيانات الحيوان والمريض (Patient Info)")
        sec2.font = Font(name="Calibri", size=11, bold=True, color="1E3A8A")
        sec2.fill = SECTION_FILL
        sec2.alignment = ALIGN_RIGHT
        ws1.row_dimensions[current_row].height = 24
        current_row += 1

        animal_fields = [
            ("رقم المريض المميز (ID)", animal.animal_id or f"#{animal.pk}", "اسم الحيوان", animal.name),
            ("الفصيلة (Species)", animal.get_species_display(), "السلالة (Breed)", animal.breed or "غير محدد"),
            ("الجنس (Gender)", animal.get_gender_display(), "تاريخ الميلاد (Birth date)", str(animal.birth_date or "غير محدد")),
            ("الوزن الحالي (كغ)", f"{animal.weight} كغ" if animal.weight else "غير مسجل", "اللون والعلامات", animal.color or "غير محدد"),
            ("رقم الشريحة / التعريف", animal.identification or "بدون شريحة", "تاريخ التسجيل بالعيادة", animal.created_at.strftime("%Y-%m-%d")),
            ("حالة السجل", "محذوف" if animal.is_deleted else "نشط", "ملاحظات خاصة وحساسية", animal.notes or "لا يوجد"),
        ]
        for f1_label, f1_val, f2_label, f2_val in animal_fields:
            c1 = ws1.cell(row=current_row, column=1, value=f1_label); c1.font = BOLD_FONT; c1.alignment = ALIGN_RIGHT; c1.border = CELL_BORDER
            c2 = ws1.cell(row=current_row, column=2, value=f1_val); c2.font = NORMAL_FONT; c2.alignment = ALIGN_RIGHT; c2.border = CELL_BORDER
            c3 = ws1.cell(row=current_row, column=3, value=f2_label); c3.font = BOLD_FONT; c3.alignment = ALIGN_RIGHT; c3.border = CELL_BORDER
            c4 = ws1.cell(row=current_row, column=4, value=f2_val); c4.font = NORMAL_FONT; c4.alignment = ALIGN_RIGHT; c4.border = CELL_BORDER
            ws1.row_dimensions[current_row].height = 22
            current_row += 1

        apply_sheet_rtl_and_auto_widths(ws1)

    # ----------------------------------------------------
    # Sheet 2: السجل السريري (Clinical History)
    # ----------------------------------------------------
    if include_clinical:
        ws2 = wb.create_sheet(title="السجل السريري وتاريخ الزيارات")
        headers = [
            "م", "التاريخ والوقت", "الطبيب المعالج", "نوع الزيارة",
            "الأعراض والشكوى", "الفحص والتشخيص", "العلاج والإجراءات",
            "الوصفة الدوائية", "الوزن عند الفحص"
        ]
        if include_services:
            headers.append("الخدمات المنفذة")
        headers.append("عدد المرفقات")

        col_count = len(headers)
        current_row = add_title_header(
            ws2,
            title_text=f"سجل الزيارات والفحوصات السريرية: {animal.name}",
            subtitle_text=f"إجمالي الزيارات: {animal.medical_records.alive().count()}",
            col_span=col_count
        )

        for col_num, h_text in enumerate(headers, 1):
            cell = ws2.cell(row=current_row, column=col_num, value=h_text)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = HEADER_BORDER
        ws2.row_dimensions[current_row].height = 26
        current_row += 1

        records = (
            animal.medical_records.alive()
            .select_related("doctor", "appointment")
            .prefetch_related("services", "attachments")
            .order_by("-date_time")
        )
        if not records.exists():
            ws2.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=col_count)
            empty_cell = ws2.cell(row=current_row, column=1, value="لا توجد زيارات سريرية مسجلة لهذا الحيوان بعد.")
            empty_cell.font = MUTED_FONT
            empty_cell.alignment = ALIGN_CENTER
            empty_cell.border = CELL_BORDER
            ws2.row_dimensions[current_row].height = 24
        else:
            for idx, rec in enumerate(records, 1):
                doc_name = rec.doctor.get_full_name() or rec.doctor.username
                visit_type = f"موعد #{rec.appointment.pk}" if rec.appointment else "زيارة مباشرة (Walk-in)"
                weight_str = f"{rec.weight_at_visit} كغ" if rec.weight_at_visit else "-"
                row_data = [
                    idx,
                    rec.date_time.strftime("%Y-%m-%d %H:%M"),
                    f"د. {doc_name}",
                    visit_type,
                    rec.symptoms or "-",
                    rec.diagnosis or "-",
                    rec.treatment or "-",
                    rec.prescription or "-",
                    weight_str
                ]
                if include_services:
                    services_str = ", ".join([s.name for s in rec.services.all()]) or "لا يوجد"
                    row_data.append(services_str)
                
                att_count = rec.attachments.filter(is_deleted=False).count()
                row_data.append(att_count)

                for col_num, val in enumerate(row_data, 1):
                    cell = ws2.cell(row=current_row, column=col_num, value=val)
                    cell.font = NORMAL_FONT
                    cell.alignment = ALIGN_CENTER if col_num in [1, 2, 3, 4, 9, col_count] else ALIGN_RIGHT
                    cell.border = CELL_BORDER
                    if idx % 2 == 0:
                        cell.fill = ZEBRA_FILL
                ws2.row_dimensions[current_row].height = 22
                current_row += 1

        apply_sheet_rtl_and_auto_widths(ws2)

    # ----------------------------------------------------
    # Sheet 3: سجل التطعيمات (Vaccination History)
    # ----------------------------------------------------
    if include_vaccines:
        ws3 = wb.create_sheet(title="سجل التطعيمات والجرعات")
        current_row = add_title_header(
            ws3,
            title_text=f"سجل اللقاحات والجرعات الوقائية: {animal.name}",
            subtitle_text=f"إجمالي التطعيمات: {animal.vaccination_records.alive().count()}",
            col_span=8
        )

        v_headers = [
            "م", "اسم اللقاح / التطعيم", "رقم التشغيلة", "تاريخ الإعطاء",
            "تاريخ الجرعة القادمة", "الحالة", "الطبيب البيطري", "ملاحظات اللقاح"
        ]
        for col_num, h_text in enumerate(v_headers, 1):
            cell = ws3.cell(row=current_row, column=col_num, value=h_text)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = HEADER_BORDER
        ws3.row_dimensions[current_row].height = 26
        current_row += 1

        vaccines = animal.vaccination_records.alive().select_related("doctor").order_by("-date_administered")
        if not vaccines.exists():
            ws3.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
            empty_cell = ws3.cell(row=current_row, column=1, value="لا توجد تطعيمات مسجلة لهذا الحيوان بعد.")
            empty_cell.font = MUTED_FONT
            empty_cell.alignment = ALIGN_CENTER
            empty_cell.border = CELL_BORDER
            ws3.row_dimensions[current_row].height = 24
        else:
            today = timezone.localdate()
            for idx, vac in enumerate(vaccines, 1):
                doc_name = vac.doctor.get_full_name() or vac.doctor.username if vac.doctor else "-"
                due_str = vac.next_due_date.strftime("%Y-%m-%d") if vac.next_due_date else "غير محدد"
                is_overdue = vac.next_due_date and vac.next_due_date < today
                status_str = "متأخر ⚠️" if is_overdue else ("مستحق قريباً" if vac.next_due_date else "مكتمل")

                v_row_data = [
                    idx,
                    vac.vaccine_name,
                    vac.batch_number or "-",
                    vac.date_administered.strftime("%Y-%m-%d"),
                    due_str,
                    status_str,
                    f"د. {doc_name}" if vac.doctor else "-",
                    vac.notes or "-"
                ]
                for col_num, val in enumerate(v_row_data, 1):
                    cell = ws3.cell(row=current_row, column=col_num, value=val)
                    cell.font = NORMAL_FONT
                    cell.alignment = ALIGN_CENTER if col_num in [1, 3, 4, 5, 6, 7] else ALIGN_RIGHT
                    cell.border = CELL_BORDER
                    if col_num == 6 and is_overdue:
                        cell.fill = ACCENT_RED
                        cell.font = BOLD_FONT
                    elif idx % 2 == 0:
                        cell.fill = ZEBRA_FILL
                ws3.row_dimensions[current_row].height = 22
                current_row += 1

        apply_sheet_rtl_and_auto_widths(ws3)

    # ----------------------------------------------------
    # Sheet 4: سجل المواعيد (Appointments History - Optional)
    # ----------------------------------------------------
    if include_appointments:
        ws4 = wb.create_sheet(title="سجل المواعيد والزيارات")
        appts = animal.appointments.alive().select_related("doctor", "created_by").order_by("-date", "-time")
        current_row = add_title_header(
            ws4,
            title_text=f"سجل المواعيد والزيارات المجدولة: {animal.name}",
            subtitle_text=f"إجمالي المواعيد: {appts.count()}",
            col_span=8
        )

        a_headers = ["م", "التاريخ", "الوقت", "نوع الموعد", "المدة", "الطبيب المعالج", "الحالة", "الملاحظات"]
        for col_num, h_text in enumerate(a_headers, 1):
            cell = ws4.cell(row=current_row, column=col_num, value=h_text)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = HEADER_BORDER
        ws4.row_dimensions[current_row].height = 26
        current_row += 1

        if not appts.exists():
            ws4.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
            empty_cell = ws4.cell(row=current_row, column=1, value="لا توجد مواعيد مسجلة لهذا المريض بعد.")
            empty_cell.font = MUTED_FONT
            empty_cell.alignment = ALIGN_CENTER
            empty_cell.border = CELL_BORDER
            ws4.row_dimensions[current_row].height = 24
        else:
            for idx, appt in enumerate(appts, 1):
                doc_name = appt.doctor.get_full_name() or appt.doctor.username
                row_data = [
                    idx,
                    appt.date.strftime("%Y-%m-%d"),
                    appt.time.strftime("%H:%M"),
                    appt.get_appointment_type_display(),
                    f"{appt.duration} دقيقة",
                    f"د. {doc_name}",
                    appt.get_status_display(),
                    appt.notes or "-"
                ]
                for col_num, val in enumerate(row_data, 1):
                    cell = ws4.cell(row=current_row, column=col_num, value=val)
                    cell.font = NORMAL_FONT
                    cell.alignment = ALIGN_CENTER if col_num in [1, 2, 3, 4, 5, 6, 7] else ALIGN_RIGHT
                    cell.border = CELL_BORDER
                    if col_num == 7:
                        if appt.status == Appointment.Status.COMPLETED:
                            cell.fill = ACCENT_GREEN
                        elif appt.status == Appointment.Status.CANCELLED:
                            cell.fill = ACCENT_RED
                    elif idx % 2 == 0:
                        cell.fill = ZEBRA_FILL
                ws4.row_dimensions[current_row].height = 22
                current_row += 1

        apply_sheet_rtl_and_auto_widths(ws4)

    # ----------------------------------------------------
    # Sheet 5: سجل التذكيرات (Reminders History - Optional)
    # ----------------------------------------------------
    if include_reminders:
        ws5 = wb.create_sheet(title="سجل التذكيرات والمتابعات")
        reminders = animal.reminders.alive().select_related("converted_appointment").order_by("-due_date")
        current_row = add_title_header(
            ws5,
            title_text=f"سجل التذكيرات والمتابعات الدورية: {animal.name}",
            subtitle_text=f"إجمالي التذكيرات: {reminders.count()}",
            col_span=7
        )

        r_headers = ["م", "تاريخ الاستحقاق", "نوع التذكير", "الحالة", "الموعد المحول إليه", "السبب والملاحظات", "تاريخ الإنشاء"]
        for col_num, h_text in enumerate(r_headers, 1):
            cell = ws5.cell(row=current_row, column=col_num, value=h_text)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = HEADER_BORDER
        ws5.row_dimensions[current_row].height = 26
        current_row += 1

        if not reminders.exists():
            ws5.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
            empty_cell = ws5.cell(row=current_row, column=1, value="لا توجد تذكيرات مسجلة لهذا المريض بعد.")
            empty_cell.font = MUTED_FONT
            empty_cell.alignment = ALIGN_CENTER
            empty_cell.border = CELL_BORDER
            ws5.row_dimensions[current_row].height = 24
        else:
            for idx, rem in enumerate(reminders, 1):
                conv_str = (
                    f"موعد {rem.converted_appointment.date.strftime('%Y-%m-%d')} #{rem.converted_appointment.pk}"
                    if rem.converted_appointment else "-"
                )
                row_data = [
                    idx,
                    rem.due_date.strftime("%Y-%m-%d"),
                    rem.get_reminder_type_display(),
                    rem.get_status_display(),
                    conv_str,
                    rem.notes or "-",
                    rem.created_at.strftime("%Y-%m-%d")
                ]
                for col_num, val in enumerate(row_data, 1):
                    cell = ws5.cell(row=current_row, column=col_num, value=val)
                    cell.font = NORMAL_FONT
                    cell.alignment = ALIGN_CENTER if col_num in [1, 2, 3, 4, 5, 7] else ALIGN_RIGHT
                    cell.border = CELL_BORDER
                    if idx % 2 == 0:
                        cell.fill = ZEBRA_FILL
                ws5.row_dimensions[current_row].height = 22
                current_row += 1

        apply_sheet_rtl_and_auto_widths(ws5)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==============================================================================
# 2. Patients Full Registry Report (All Patients or Filtered Registry)
# ==============================================================================

def generate_patients_registry_report_xlsx(
    client_id=None,
    species=None,
    breed=None,
    gender=None,
    q=None,
    start_date=None,
    end_date=None,
):
    """
    Exports a comprehensive table/registry of clinic patients (animals)
    with owner information and demographic filters.
    """
    queryset = Animal.objects.alive().select_related("client").order_by("name")

    cid = parse_int_safely(client_id)
    if cid:
        queryset = queryset.filter(client_id=cid)
    if species and species != "all":
        queryset = queryset.filter(species=species)
    if breed:
        queryset = queryset.filter(breed__icontains=breed)
    if gender and gender != "all":
        queryset = queryset.filter(gender=gender)

    s_date = parse_date_safely(start_date)
    e_date = parse_date_safely(end_date)
    if s_date:
        queryset = queryset.filter(created_at__date__gte=s_date)
    if e_date:
        queryset = queryset.filter(created_at__date__lte=e_date)
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) |
            Q(animal_id__icontains=q) |
            Q(identification__icontains=q) |
            Q(breed__icontains=q) |
            Q(client__full_name__icontains=q) |
            Q(client__phone__icontains=q)
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "دليل وسجل المرضى"

    current_row = add_title_header(
        ws,
        title_text="دليل وسجل المرضى (الحيوانات) بالعيادة",
        subtitle_text=f"إجمالي المرضى المطابقين: {queryset.count()}",
        col_span=12
    )

    headers = [
        "م", "رقم المريض (ID)", "اسم الحيوان", "الفصيلة", "السلالة",
        "الجنس", "تاريخ الميلاد", "الوزن (كغ)", "اللون والعلامات",
        "رقم الشريحة / التعريف", "اسم المالك الكامل", "رقم هاتف المالك", "تاريخ التسجيل"
    ]
    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    if not queryset.exists():
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=12)
        empty_cell = ws.cell(row=current_row, column=1, value="لا يوجد مرضى مطابقين لمعايير التصفية والبحث المحددة.")
        empty_cell.font = MUTED_FONT
        empty_cell.alignment = ALIGN_CENTER
        empty_cell.border = CELL_BORDER
        ws.row_dimensions[current_row].height = 24
    else:
        for idx, pet in enumerate(queryset, 1):
            birth_str = pet.birth_date.strftime("%Y-%m-%d") if pet.birth_date else "-"
            weight_str = f"{pet.weight} كغ" if pet.weight else "-"
            row_data = [
                idx,
                pet.animal_id or f"#{pet.pk}",
                pet.name,
                pet.get_species_display(),
                pet.breed or "-",
                pet.get_gender_display(),
                birth_str,
                weight_str,
                pet.color or "-",
                pet.identification or "-",
                pet.client.full_name,
                pet.client.phone,
                pet.created_at.strftime("%Y-%m-%d"),
            ]
            for col_num, val in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_num, value=val)
                cell.font = NORMAL_FONT
                cell.alignment = ALIGN_CENTER if col_num in [1, 2, 4, 6, 7, 8, 10, 12, 13] else ALIGN_RIGHT
                cell.border = CELL_BORDER
                if idx % 2 == 0:
                    cell.fill = ZEBRA_FILL
            ws.row_dimensions[current_row].height = 22
            current_row += 1

    apply_sheet_rtl_and_auto_widths(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==============================================================================
# 3. Client Multi-Animal Comprehensive Report
# ==============================================================================

def generate_client_report_xlsx(client, include_basic=True, include_clinical=True, include_vaccines=True):
    """
    Generates an Excel workbook for all animals owned by a client.
    Contains basic overview sheet, plus clinical and vaccination records for each pet.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet(title="بيانات العميل والحيوانات")
    current_row = add_title_header(
        ws,
        title_text=f"تقرير ملف العميل الشامل: {client.full_name}",
        subtitle_text=f"هاتف: {client.phone} | عدد الحيوانات المسجلة: {client.animals.alive().count()}",
        col_span=8
    )

    # Owner details box
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
    sec = ws.cell(row=current_row, column=1, value="بيانات العميل (Client Details)")
    sec.font = Font(name="Calibri", size=11, bold=True, color="1E3A8A")
    sec.fill = SECTION_FILL
    sec.alignment = ALIGN_RIGHT
    current_row += 1

    details = [
        ("الاسم الكامل", client.full_name, "رقم الهاتف", client.phone),
        ("العنوان", client.address or "غير محدد", "تاريخ الانضمام", client.created_at.strftime("%Y-%m-%d")),
        ("ملاحظات العميل", client.notes or "لا يوجد", "", ""),
    ]
    for f1_label, f1_val, f2_label, f2_val in details:
        c1 = ws.cell(row=current_row, column=1, value=f1_label); c1.font = BOLD_FONT; c1.alignment = ALIGN_RIGHT; c1.border = CELL_BORDER
        c2 = ws.cell(row=current_row, column=2, value=f1_val); c2.font = NORMAL_FONT; c2.alignment = ALIGN_RIGHT; c2.border = CELL_BORDER
        c3 = ws.cell(row=current_row, column=3, value=f2_label); c3.font = BOLD_FONT; c3.alignment = ALIGN_RIGHT; c3.border = CELL_BORDER
        c4 = ws.cell(row=current_row, column=4, value=f2_val); c4.font = NORMAL_FONT; c4.alignment = ALIGN_RIGHT; c4.border = CELL_BORDER
        current_row += 1

    current_row += 1

    # Animals Table
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
    sec2 = ws.cell(row=current_row, column=1, value="قائمة الحيوانات التابعة للعميل (Registered Pets)")
    sec2.font = Font(name="Calibri", size=11, bold=True, color="1E3A8A")
    sec2.fill = SECTION_FILL
    sec2.alignment = ALIGN_RIGHT
    current_row += 1

    p_headers = ["م", "رقم المريض (ID)", "اسم الحيوان", "الفصيلة", "السلالة", "الجنس", "الوزن الحالي", "رقم الشريحة / التعريف"]
    for col_num, h_text in enumerate(p_headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    current_row += 1

    animals = client.animals.alive().order_by("name")
    for idx, pet in enumerate(animals, 1):
        row_vals = [
            idx,
            pet.animal_id or f"#{pet.pk}",
            pet.name,
            pet.get_species_display(),
            pet.breed or "-",
            pet.get_gender_display(),
            f"{pet.weight} كغ" if pet.weight else "-",
            pet.identification or "-"
        ]
        for col_num, val in enumerate(row_vals, 1):
            c = ws.cell(row=current_row, column=col_num, value=val)
            c.font = NORMAL_FONT
            c.alignment = ALIGN_CENTER if col_num in [1, 3, 5, 6] else ALIGN_RIGHT
            c.border = CELL_BORDER
            if idx % 2 == 0:
                c.fill = ZEBRA_FILL
        current_row += 1

    apply_sheet_rtl_and_auto_widths(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==============================================================================
# 4. Vaccinations Comprehensive Report (Due/Overdue or Full Historical Archive)
# ==============================================================================

def generate_vaccinations_report_xlsx(
    scope="due",
    due_filter="all",
    species=None,
    doctor_id=None,
    vaccine_name=None,
    start_date=None,
    end_date=None,
):
    """
    Exports vaccinations with flexible scopes:
    - scope='due': Overdue or upcoming vaccinations for client follow-up.
    - scope='all': Complete clinic vaccination archive/history.
    """
    today = timezone.localdate()
    queryset = VaccinationRecord.objects.alive().select_related(
        "animal", "animal__client", "doctor"
    )

    if species and species != "all":
        queryset = queryset.filter(animal__species=species)
    doc_id = parse_int_safely(doctor_id)
    if doc_id:
        queryset = queryset.filter(doctor_id=doc_id)
    if vaccine_name:
        queryset = queryset.filter(vaccine_name__icontains=vaccine_name)

    s_date = parse_date_safely(start_date)
    e_date = parse_date_safely(end_date)

    if scope == "due":
        queryset = queryset.filter(next_due_date__isnull=False)
        if due_filter == "overdue":
            queryset = queryset.filter(next_due_date__lt=today)
        elif due_filter == "today":
            queryset = queryset.filter(next_due_date=today)
        elif due_filter == "week":
            queryset = queryset.filter(next_due_date__gte=today, next_due_date__lte=today + timedelta(days=7))
        elif due_filter == "month":
            queryset = queryset.filter(next_due_date__gte=today, next_due_date__lte=today + timedelta(days=30))
        
        if s_date:
            queryset = queryset.filter(next_due_date__gte=s_date)
        if e_date:
            queryset = queryset.filter(next_due_date__lte=e_date)
        queryset = queryset.order_by("next_due_date")
        sheet_title = "التطعيمات المستحقة"
        report_title = "كشف التطعيمات والجرعات المستحقة للمتابعة"
    else:
        if s_date:
            queryset = queryset.filter(date_administered__gte=s_date)
        if e_date:
            queryset = queryset.filter(date_administered__lte=e_date)
        queryset = queryset.order_by("-date_administered")
        sheet_title = "سجل كافة التطعيمات"
        report_title = "أرشيف وسجل التطعيمات واللقاحات الشامل"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title

    current_row = add_title_header(
        ws,
        title_text=report_title,
        subtitle_text=f"إجمالي التطعيمات المطابقة: {queryset.count()}",
        col_span=10
    )

    headers = [
        "م", "اسم الحيوان", "الفصيلة", "المالك", "رقم الهاتف",
        "اسم اللقاح / التطعيم", "رقم التشغيلة", "تاريخ الإعطاء",
        "تاريخ الجرعة القادمة", "الطبيب البيطري"
    ]
    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    if not queryset.exists():
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=10)
        empty_cell = ws.cell(row=current_row, column=1, value="لا توجد تطعيمات مسجلة تطابق معايير التصفية المحددة.")
        empty_cell.font = MUTED_FONT
        empty_cell.alignment = ALIGN_CENTER
        empty_cell.border = CELL_BORDER
    else:
        for idx, vac in enumerate(queryset, 1):
            is_overdue = vac.next_due_date and vac.next_due_date < today
            doc_name = vac.doctor.get_full_name() or vac.doctor.username if vac.doctor else "-"
            next_due_str = vac.next_due_date.strftime("%Y-%m-%d") if vac.next_due_date else "-"
            row_data = [
                idx,
                vac.animal.name,
                vac.animal.get_species_display(),
                vac.animal.client.full_name,
                vac.animal.client.phone,
                vac.vaccine_name,
                vac.batch_number or "-",
                vac.date_administered.strftime("%Y-%m-%d"),
                next_due_str,
                f"د. {doc_name}",
            ]
            for col_num, val in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_num, value=val)
                cell.font = NORMAL_FONT
                cell.alignment = ALIGN_CENTER if col_num in [1, 3, 5, 7, 8, 9, 10] else ALIGN_RIGHT
                cell.border = CELL_BORDER
                if col_num == 9 and is_overdue:
                    cell.fill = ACCENT_RED
                    cell.font = BOLD_FONT
                elif idx % 2 == 0:
                    cell.fill = ZEBRA_FILL
            ws.row_dimensions[current_row].height = 22
            current_row += 1

    apply_sheet_rtl_and_auto_widths(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_due_vaccinations_report_xlsx(due_filter="all"):
    """Backward-compatible alias for due vaccinations export."""
    return generate_vaccinations_report_xlsx(scope="due", due_filter=due_filter)


# ==============================================================================
# 5. Appointments Log Report
# ==============================================================================

def generate_appointments_report_xlsx(
    start_date=None,
    end_date=None,
    doctor_id=None,
    status=None,
    species=None,
    appointment_type=None,
    include_notes=True,
):
    """
    Exports appointments schedule within a date range and granular filters.
    Includes appointment type, created_by, notes, and attendance summary.
    """
    queryset = Appointment.objects.alive().select_related("animal", "animal__client", "doctor", "created_by")

    s_date = parse_date_safely(start_date)
    e_date = parse_date_safely(end_date)
    if s_date:
        queryset = queryset.filter(date__gte=s_date)
    if e_date:
        queryset = queryset.filter(date__lte=e_date)
    doc_id = parse_int_safely(doctor_id)
    if doc_id:
        queryset = queryset.filter(doctor_id=doc_id)
    if status and status != "all":
        queryset = queryset.filter(status=status.upper())
    if species and species != "all":
        queryset = queryset.filter(animal__species=species)
    if appointment_type and appointment_type != "all":
        queryset = queryset.filter(appointment_type=appointment_type)

    queryset = queryset.order_by("-date", "-time")

    # Calculate status summary stats
    total_count = queryset.count()
    completed_count = queryset.filter(status=Appointment.Status.COMPLETED).count()
    cancelled_count = queryset.filter(status=Appointment.Status.CANCELLED).count()
    no_show_count = queryset.filter(status=Appointment.Status.NO_SHOW).count()
    scheduled_count = queryset.filter(status=Appointment.Status.SCHEDULED).count()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "سجل المواعيد"

    date_range_label = f"من {s_date.isoformat() if s_date else 'البداية'} إلى {e_date.isoformat() if e_date else 'اليوم'}"
    subtitle = (
        f"الفترة: {date_range_label} | الإجمالي: {total_count} "
        f"(مكتمل: {completed_count} | مجدول: {scheduled_count} | لم يحضر: {no_show_count} | ملغى: {cancelled_count})"
    )

    headers = [
        "م", "التاريخ", "الوقت", "المدة", "نوع الموعد", "المريض والنوع",
        "المالك والهاتف", "الشخص المُحضر", "الطبيب المعالج", "الموظف المنشئ", "الحالة"
    ]
    if include_notes:
        headers.append("ملاحظات الموعد")

    col_count = len(headers)
    current_row = add_title_header(
        ws,
        title_text="سجل مواعيد وزيارات العيادة",
        subtitle_text=subtitle,
        col_span=col_count
    )

    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    if not queryset.exists():
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=col_count)
        empty_cell = ws.cell(row=current_row, column=1, value="لا توجد مواعيد مسجلة تطابق التصفية المحددة.")
        empty_cell.font = MUTED_FONT
        empty_cell.alignment = ALIGN_CENTER
        empty_cell.border = CELL_BORDER
    else:
        for idx, appt in enumerate(queryset, 1):
            doc_name = appt.doctor.get_full_name() or appt.doctor.username
            creator_name = (appt.created_by.get_full_name() or appt.created_by.username) if appt.created_by else "-"
            type_display = appt.get_appointment_type_display()
            if appt.vaccine_name:
                type_display += f" ({appt.vaccine_name})"

            row_data = [
                idx,
                appt.date.strftime("%Y-%m-%d"),
                appt.time.strftime("%H:%M"),
                f"{appt.duration} دقيقة",
                type_display,
                f"{appt.animal.name} ({appt.animal.get_species_display()})",
                f"{appt.animal.client.full_name} ({appt.animal.client.phone})",
                appt.brought_by or "المالك نفسه",
                f"د. {doc_name}",
                creator_name,
                appt.get_status_display()
            ]
            if include_notes:
                row_data.append(appt.notes or "-")

            for col_num, val in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_num, value=val)
                cell.font = NORMAL_FONT
                cell.alignment = ALIGN_CENTER if col_num in [1, 2, 3, 4, 5, 9, 10, 11] else ALIGN_RIGHT
                cell.border = CELL_BORDER
                if col_num == 11:
                    if appt.status == Appointment.Status.COMPLETED:
                        cell.fill = ACCENT_GREEN
                    elif appt.status == Appointment.Status.CANCELLED:
                        cell.fill = ACCENT_RED
                    elif appt.status == Appointment.Status.NO_SHOW:
                        cell.fill = ACCENT_AMBER
                elif idx % 2 == 0:
                    cell.fill = ZEBRA_FILL
            ws.row_dimensions[current_row].height = 22
            current_row += 1

    apply_sheet_rtl_and_auto_widths(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==============================================================================
# 6. Clients & Patients Full Directory Report
# ==============================================================================

def generate_clients_directory_report_xlsx():
    """
    Exports a comprehensive clinic directory with clients and their pets.
    """
    clients = Client.objects.alive().prefetch_related("animals").order_by("full_name")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "دليل العملاء والمرضى"

    total_pets = Animal.objects.alive().count()
    current_row = add_title_header(
        ws,
        title_text="دليل العملاء والمرضى المسجلين بالعيادة",
        subtitle_text=f"إجمالي العملاء: {clients.count()} | إجمالي الحيوانات: {total_pets}",
        col_span=7
    )

    headers = [
        "م", "اسم العميل الكامل", "رقم الهاتف", "العنوان",
        "عدد الحيوانات", "أسماء الحيوانات التابعة", "تاريخ التسجيل"
    ]
    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    for idx, cl in enumerate(clients, 1):
        active_pets = cl.animals.filter(is_deleted=False)
        pet_names = ", ".join([f"{p.name} ({p.get_species_display()})" for p in active_pets]) or "لا يوجد"
        row_data = [
            idx,
            cl.full_name,
            cl.phone,
            cl.address or "-",
            active_pets.count(),
            pet_names,
            cl.created_at.strftime("%Y-%m-%d")
        ]
        for col_num, val in enumerate(row_data, 1):
            cell = ws.cell(row=current_row, column=col_num, value=val)
            cell.font = NORMAL_FONT
            cell.alignment = ALIGN_CENTER if col_num in [1, 3, 5, 7] else ALIGN_RIGHT
            cell.border = CELL_BORDER
            if idx % 2 == 0:
                cell.fill = ZEBRA_FILL
        ws.row_dimensions[current_row].height = 22
        current_row += 1

    apply_sheet_rtl_and_auto_widths(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==============================================================================
# 7. Clinical Visits & Diagnostics Custom Report
# ==============================================================================

def generate_clinical_records_report_xlsx(
    start_date=None,
    end_date=None,
    doctor_id=None,
    record_type=None,
    animal_id=None,
    client_id=None,
    species=None,
    q=None,
    include_prescriptions=True,
    include_treatment=True,
    include_services=True,
):
    """
    Generates an Excel report for clinical visits and examinations with granular filters,
    including performed services and attachment counts.
    """
    queryset = (
        MedicalRecord.objects.alive()
        .select_related("animal", "animal__client", "doctor")
        .prefetch_related("services", "attachments")
        .order_by("-date_time")
    )

    s_date = parse_date_safely(start_date)
    e_date = parse_date_safely(end_date)
    if s_date:
        queryset = queryset.filter(date_time__date__gte=s_date)
    if e_date:
        queryset = queryset.filter(date_time__date__lte=e_date)
    doc_id = parse_int_safely(doctor_id)
    if doc_id:
        queryset = queryset.filter(doctor_id=doc_id)
    if record_type and record_type != "all":
        queryset = queryset.filter(record_type=record_type)
    aid = parse_int_safely(animal_id)
    if aid:
        queryset = queryset.filter(animal_id=aid)
    cid = parse_int_safely(client_id)
    if cid:
        queryset = queryset.filter(animal__client_id=cid)
    if species and species != "all":
        queryset = queryset.filter(animal__species=species)
    if q:
        queryset = queryset.filter(
            Q(animal__name__icontains=q) |
            Q(animal__client__full_name__icontains=q) |
            Q(diagnosis__icontains=q) |
            Q(symptoms__icontains=q) |
            Q(treatment__icontains=q)
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "السجلات والزيارات السريرية"

    headers = ["م", "التاريخ والوقت", "نوع الزيارة", "المريض والنوع", "المالك والهاتف", "الطبيب المعالج", "الوزن (كغ)", "التشخيص الطبي"]
    if include_treatment:
        headers.append("العلاج والإجراءات")
    if include_prescriptions:
        headers.append("الوصفة الطبية المنزلية")
    if include_services:
        headers.append("الخدمات المنفذة")
    headers.append("المرفقات")

    col_count = len(headers)

    current_row = add_title_header(
        ws,
        title_text="تقرير الزيارات والفحوصات السريرية المخصص",
        subtitle_text=f"إجمالي السجلات المضمنة: {queryset.count()}",
        col_span=col_count
    )

    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    if not queryset.exists():
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=col_count)
        empty_cell = ws.cell(row=current_row, column=1, value="لا توجد زيارات سريرية مسجلة تطابق التصفية المحددة.")
        empty_cell.font = MUTED_FONT
        empty_cell.alignment = ALIGN_CENTER
        empty_cell.border = CELL_BORDER
    else:
        for idx, rec in enumerate(queryset, 1):
            doc_name = rec.doctor.get_full_name() or rec.doctor.username
            row_data = [
                idx,
                rec.date_time.strftime("%Y-%m-%d %H:%M"),
                rec.get_record_type_display(),
                f"{rec.animal.name} ({rec.animal.get_species_display()})",
                f"{rec.animal.client.full_name} ({rec.animal.client.phone})",
                f"د. {doc_name}",
                f"{rec.weight_at_visit} كغ" if rec.weight_at_visit else "-",
                rec.diagnosis or "غير مسجل",
            ]
            if include_treatment:
                row_data.append(rec.treatment or "-")
            if include_prescriptions:
                row_data.append(rec.prescription or "-")
            if include_services:
                services_str = ", ".join([s.name for s in rec.services.all()]) or "لا يوجد"
                row_data.append(services_str)
            
            att_count = rec.attachments.filter(is_deleted=False).count()
            row_data.append(att_count)

            for col_num, val in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_num, value=val)
                cell.font = NORMAL_FONT
                cell.alignment = ALIGN_CENTER if col_num in [1, 2, 3, 6, 7, col_count] else ALIGN_RIGHT
                cell.border = CELL_BORDER
                if idx % 2 == 0:
                    cell.fill = ZEBRA_FILL
            ws.row_dimensions[current_row].height = 22
            current_row += 1

    apply_sheet_rtl_and_auto_widths(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==============================================================================
# 8. Reminders Custom Report
# ==============================================================================

def generate_reminders_report_xlsx(
    due_filter="all",
    reminder_type="all",
    status="all",
    start_date=None,
    end_date=None,
    species=None,
):
    """
    Generates an Excel report for reminders and client follow-ups,
    with species filter and linked converted appointment details.
    """
    today = timezone.localdate()
    queryset = Reminder.objects.alive().select_related("animal", "animal__client", "converted_appointment").order_by("due_date", "created_at")

    if status and status != "all":
        queryset = queryset.filter(status=status)
    if reminder_type and reminder_type != "all":
        queryset = queryset.filter(reminder_type=reminder_type)
    if species and species != "all":
        queryset = queryset.filter(animal__species=species)
    s_date = parse_date_safely(start_date)
    e_date = parse_date_safely(end_date)
    if s_date:
        queryset = queryset.filter(due_date__gte=s_date)
    if e_date:
        queryset = queryset.filter(due_date__lte=e_date)

    if due_filter == "overdue":
        queryset = queryset.filter(due_date__lt=today, status=Reminder.Status.PENDING)
    elif due_filter == "today":
        queryset = queryset.filter(due_date=today, status=Reminder.Status.PENDING)
    elif due_filter == "week":
        end_of_week = today + timezone.timedelta(days=7)
        queryset = queryset.filter(due_date__gte=today, due_date__lte=end_of_week, status=Reminder.Status.PENDING)
    elif due_filter == "month":
        end_of_month = today + timezone.timedelta(days=30)
        queryset = queryset.filter(due_date__gte=today, due_date__lte=end_of_month, status=Reminder.Status.PENDING)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "سجل التذكيرات والمتابعات"

    current_row = add_title_header(
        ws,
        title_text="تقرير سجل التذكيرات والمتابعات",
        subtitle_text=f"إجمالي التذكيرات: {queryset.count()}",
        col_span=8
    )

    headers = ["م", "تاريخ الاستحقاق", "نوع التذكير", "المريض والنوع", "المالك ورقم الهاتف", "الحالة", "الموعد المحول إليه", "السبب والملاحظات"]
    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_num, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border = HEADER_BORDER
    ws.row_dimensions[current_row].height = 26
    current_row += 1

    if not queryset.exists():
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
        empty_cell = ws.cell(row=current_row, column=1, value="لا توجد تذكيرات مسجلة تطابق التصفية المحددة.")
        empty_cell.font = MUTED_FONT
        empty_cell.alignment = ALIGN_CENTER
        empty_cell.border = CELL_BORDER
    else:
        for idx, rem in enumerate(queryset, 1):
            conv_str = (
                f"موعد #{rem.converted_appointment.pk} ({rem.converted_appointment.date.strftime('%Y-%m-%d')})"
                if rem.converted_appointment else "-"
            )
            row_data = [
                idx,
                rem.due_date.strftime("%Y-%m-%d"),
                rem.get_reminder_type_display(),
                f"{rem.animal.name} ({rem.animal.get_species_display()})",
                f"{rem.animal.client.full_name} ({rem.animal.client.phone})",
                rem.get_status_display(),
                conv_str,
                rem.notes or "لا توجد ملاحظات",
            ]
            for col_num, val in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_num, value=val)
                cell.font = NORMAL_FONT
                cell.alignment = ALIGN_CENTER if col_num in [1, 2, 3, 6, 7] else ALIGN_RIGHT
                cell.border = CELL_BORDER
                if col_num == 6:
                    if rem.status == Reminder.Status.COMPLETED or rem.status == Reminder.Status.CONVERTED:
                        cell.fill = ACCENT_GREEN
                    elif rem.status == Reminder.Status.CANCELLED:
                        cell.fill = ACCENT_RED
                    elif rem.due_date < today and rem.status == Reminder.Status.PENDING:
                        cell.fill = ACCENT_AMBER
                elif idx % 2 == 0:
                    cell.fill = ZEBRA_FILL
            ws.row_dimensions[current_row].height = 22
            current_row += 1

    apply_sheet_rtl_and_auto_widths(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
