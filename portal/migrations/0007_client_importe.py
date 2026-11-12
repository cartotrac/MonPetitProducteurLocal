from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0006_supprime_rythme_vitrine"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientImporte",
            fields=[
                ("id", models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name="ID")),
                ("nom", models.CharField(max_length=150,
                                          verbose_name="Nom du client")),
                ("email", models.EmailField(blank=True, max_length=254,
                                             verbose_name="E-mail")),
                ("telephone", models.CharField(blank=True, max_length=20,
                                               verbose_name="Téléphone")),
                ("ajoute_le", models.DateTimeField(
                    auto_now_add=True, verbose_name="Importé le")),
                ("client", models.ForeignKey(
                    blank=True, help_text="Renseigné automatiquement à "
                    "l'import si un compte utilise cet e-mail.",
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="clients_importes_chez",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Compte Localien rattaché")),
                ("exploitant", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="clients_importes",
                    to="portal.exploitant",
                    verbose_name="Espace pro")),
            ],
            options={
                "verbose_name": "Client importé",
                "verbose_name_plural": "Clients importés",
                "ordering": ["nom"],
            },
        ),
    ]
