from django.db import migrations, models


class Migration(migrations.Migration):
    """Unicité des catégories : (exploitant, nom) → (exploitant,
    catalogue, nom). Un même nom de catégorie peut désormais exister
    dans plusieurs catalogues d'un même espace pro — indispensable
    pour la duplication de catalogues (l'ancienne contrainte
    mono-liste faisait échouer toute duplication avec IntegrityError
    « duplicate key … (exploitant_id, nom) already exists »)."""

    dependencies = [
        ("portal", "0013_alter_catalogue_exploitant_alter_catalogue_id"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="categorie",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="categorie",
            constraint=models.UniqueConstraint(
                fields=["exploitant", "catalogue", "nom"],
                name="categorie_unique_par_catalogue"),
        ),
    ]
