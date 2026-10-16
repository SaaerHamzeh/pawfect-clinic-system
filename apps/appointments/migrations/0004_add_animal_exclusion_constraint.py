from django.db import migrations


def add_animal_exclusion_constraint(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            ALTER TABLE appointments_appointment
            ADD CONSTRAINT exclude_overlapping_animal_appointments
            EXCLUDE USING gist (
                animal_id WITH =,
                tsrange("date" + "time", ("date" + "time") + (duration * interval '1 minute'), '[)') WITH &&
            ) WHERE (is_deleted = false AND status != 'CANCELLED');
        """)


def drop_animal_exclusion_constraint(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            ALTER TABLE appointments_appointment
            DROP CONSTRAINT IF EXISTS exclude_overlapping_animal_appointments;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0003_add_exclusion_constraints'),
    ]

    operations = [
        migrations.RunPython(add_animal_exclusion_constraint, drop_animal_exclusion_constraint),
    ]
