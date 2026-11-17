from django.db import migrations, models
import django.db.models.deletion


def creer_catalogues(apps, schema_editor):
    """Données existantes : un catalogue « Catalogue principal » par
    espace pro, actif, auquel toutes ses catégories et produits sont
    rattachés (aucune perte, aucun doublon)."""
    Catalogue = apps.get_model("portal", "Catalogue")
    Categorie = apps.get_model("portal", "Categorie")
    Produit = apps.get_model("portal", "Produit")
    Exploitant = apps.get_model("portal", "Exploitant")
    for ex in Exploitant.objects.all():
        catalogue = Catalogue.objects.create(
            exploitant=ex, nom="Catalogue principal", actif=True,
            position=1)
        Categorie.objects.filter(exploitant=ex).update(catalogue=catalogue)
        Produit.objects.filter(exploitant=ex).update(catalogue=catalogue)


class Migration(migrations.Migration):
    """Multi-catalogues par espace pro : modèle Catalogue (un seul
    actif à la fois, archivage réversible), rattachement des
    catégories et des produits, médias externes par catégorie
    (attributs JSON)."""

    dependencies = [
        ("portal", "0011_unite_vente_personnalisee"),
    ]

    operations = [
        migrations.CreateModel(
            name="Catalogue",
            fields=[
                ("id", models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False,
                                        verbose_name="ID")),
                ("nom", models.CharField(max_length=120,
                                         verbose_name="Nom")),
                ("actif", models.BooleanField(
                    default=False,
                    help_text="Un seul catalogue actif à la fois par "
                              "espace pro : c'est lui qui permet "
                              "l'édition rapide des listes de "
                              "publications saisonnières ou fixes.",
                    verbose_name="Catalogue actif")),
                ("archive", models.BooleanField(
                    default=False,
                    help_text="Catalogue rangé : plus proposé à "
                              "l'édition ni aux publications, "
                              "réactivable à tout moment.",
                    verbose_name="Archivé")),
                ("position", models.PositiveSmallIntegerField(
                    default=0, verbose_name="Position")),
                ("cree_le", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("exploitant", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="catalogues",
                    to="portal.exploitant",
                    verbose_name="Espace pro")),
            ],
            options={
                "verbose_name": "Catalogue",
                "verbose_name_plural": "Catalogues",
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddField(
            model_name="categorie",
            name="catalogue",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="categories", to="portal.catalogue",
                verbose_name="Catalogue"),
        ),
        migrations.AddField(
            model_name="categorie",
            name="attributs",
            field=models.JSONField(
                blank=True, default=dict,
                help_text='Ex : {"medias": ["https://…"]}',
                verbose_name="Attributs libres"),
        ),
        migrations.AddField(
            model_name="produit",
            name="catalogue",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="produits", to="portal.catalogue",
                verbose_name="Catalogue"),
        ),
        migrations.RunPython(creer_catalogues, migrations.RunPython.noop),
    ]
