from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0004_retourutilisateur"),
    ]

    operations = [
        migrations.AddField(
            model_name="exploitant",
            name="frequence_publication",
            field=models.CharField(
                choices=[("HEBDO", "Hebdomadaire"),
                         ("QUINZAINE", "Tous les quinze jours"),
                         ("MENSUEL", "Mensuelle")],
                default="HEBDO",
                help_text=("Cadence des publications saisonnières diffusées "
                           "aux clients : la ligne de publication du "
                           "dashboard suit cette fréquence."),
                max_length=10,
                verbose_name="Fréquence de publication"),
        ),
    ]
