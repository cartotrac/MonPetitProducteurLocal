from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0017_lignerecolte_quantite_prix_facultatifs"),
    ]

    operations = [
        migrations.AddField(
            model_name="categorie",
            name="emoji",
            field=models.CharField(blank=True, default="", max_length=8, verbose_name="Emoji"),
        ),
    ]
