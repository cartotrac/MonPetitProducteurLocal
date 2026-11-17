from django.db import migrations, models


class Migration(migrations.Migration):
    """Unités de vente personnalisées : les champs unite_vente
    (Produit, LigneCarte) passent de 2 à 16 caractères — la liste
    par défaut (kg, pièce, botte, barquette) reste proposée, un
    libellé libre saisi par l'exploitant est désormais accepté."""

    dependencies = [
        ("portal", "0010_exploitant_quinzaine_paire"),
    ]

    operations = [
        migrations.AlterField(
            model_name="produit",
            name="unite_vente",
            field=models.CharField(
                choices=[("KG", "le kg"), ("PC", "la pièce"),
                         ("BO", "la botte"), ("BQ", "la barquette")],
                default="KG", max_length=16,
                verbose_name="Unité de vente"),
        ),
        migrations.AlterField(
            model_name="lignecarte",
            name="unite_vente",
            field=models.CharField(
                choices=[("KG", "le kg"), ("PC", "la pièce"),
                         ("BO", "la botte"), ("BQ", "la barquette")],
                default="KG", max_length=16,
                verbose_name="Unité de vente"),
        ),
    ]
