from django.db import migrations


def remove_other_species(apps, schema_editor):
    AnimalSpecies = apps.get_model("settings", "AnimalSpecies")
    AnimalSpecies.objects.filter(code="OTHER").delete()
    AnimalSpecies.objects.filter(name="أخرى").delete()


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("settings", "0002_seed_initial_lookups"),
    ]

    operations = [
        migrations.RunPython(remove_other_species, reverse_func),
    ]
