# Élargit ProfilClient.photo_url : les URL des CDN
# (Facebook, Drive…) dépassent souvent 200 caractères.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0015_parametresvitrine_modules"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profilclient",
            name="photo_url",
            field=models.URLField(
                "Photo externe", blank=True,
                help_text="Lien vers une photo hébergée ailleurs "
                          "(drive, cloud, réseau) : rien n'est hébergé "
                          "par le portail.",
                max_length=1024),
        ),
    ]
