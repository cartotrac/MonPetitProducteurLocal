from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0016_profilclient_photo_url_1024"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lignerecolte",
            name="quantite_estimee",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name="Quantité estimée"),
        ),
        migrations.AlterField(
            model_name="lignerecolte",
            name="prix_unitaire",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name="Prix unitaire (€)"),
        ),
    ]
