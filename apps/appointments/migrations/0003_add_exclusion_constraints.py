from django.db import migrations
from django.contrib.postgres.operations import BtreeGistExtension


def add_exclusion_constraints(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            ALTER TABLE appointments_appointment
            ADD CONSTRAINT exclude_overlapping_bath_appointments
            EXCLUDE USING gist (
                tsrange("date" + "time", ("date" + "time") + (duration * interval '1 minute'), '[)') WITH &&
            ) WHERE (appointment_type = 'BATH' AND is_deleted = false AND status != 'CANCELLED');

            ALTER TABLE appointments_appointment
            ADD CONSTRAINT exclude_overlapping_doctor_appointments
            EXCLUDE USING gist (
                doctor_id WITH =,
                tsrange("date" + "time", ("date" + "time") + (duration * interval '1 minute'), '[)') WITH &&
            ) WHERE (is_deleted = false AND status != 'CANCELLED');
        """)


def drop_exclusion_constraints(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            ALTER TABLE appointments_appointment
            DROP CONSTRAINT IF EXISTS exclude_overlapping_bath_appointments;

            ALTER TABLE appointments_appointment
            DROP CONSTRAINT IF EXISTS exclude_overlapping_doctor_appointments;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0002_alter_appointment_appointment_type'),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.RunPython(add_exclusion_constraints, drop_exclusion_constraints),
    ]

