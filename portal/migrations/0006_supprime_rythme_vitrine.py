from django.db import migrations


class Migration(migrations.Migration):

    """Suppression du champ rythme_publication de ParametresVitrine :
    réglage purement indicatif fusionné dans la FRÉQUENCE de
    publication de l'espace (Exploitant.frequence_publication,
    sélecteur du dashboard), qui pilote désormais aussi le libellé
    de l'encart vitrine."""

    dependencies = [
        ("portal", "0005_frequence_publication"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="parametresvitrine",
            name="rythme_publication",
        ),
    ]
