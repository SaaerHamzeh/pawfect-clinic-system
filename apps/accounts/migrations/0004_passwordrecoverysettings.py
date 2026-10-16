from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordRecoverySettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "recovery_code_hash",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=128,
                        verbose_name="تجزئة رمز استعادة كلمة المرور",
                    ),
                ),
                ("failed_attempts", models.PositiveIntegerField(default=0, verbose_name="محاولات الاستعادة الفاشلة")),
                ("locked_until", models.DateTimeField(blank=True, null=True, verbose_name="مقفل حتى")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")),
            ],
            options={
                "verbose_name": "إعدادات استعادة كلمة المرور",
                "verbose_name_plural": "إعدادات استعادة كلمة المرور",
            },
        ),
    ]
