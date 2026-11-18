from django.db import migrations, models


class Migration(migrations.Migration):
    """Champ « modules » de ParametresVitrine : blocs d'info
    optionnels de la vitrine publique (à propos, horaires, FAQ,
    mini-carte), activés par le gérant depuis Paramètres > Mon
    espace. Un module absent du JSON n'est pas affiché."""

    dependencies = [
        ("portal", "0014_categorie_unique_par_catalogue"),
    ]

    operations = [
        migrations.AddField(
            model_name="parametresvitrine",
            name="modules",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Modules vitrine"),
        ),
    ]
