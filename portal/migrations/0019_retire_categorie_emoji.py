from django.db import migrations


class Migration(migrations.Migration):
    """Retire le champ Categorie.emoji : l'émoji est porté par le
    PRODUIT (édité dans le catalogue, deviné sinon), pas par la
    rubrique. L'émoji affiché en tête d'un groupe de publication est
    désormais dérivé du premier article du groupe qui en a un."""

    dependencies = [
        ("portal", "0018_categorie_emoji"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="categorie",
            name="emoji",
        ),
    ]
