"""Géocode côté serveur les points de livraison sans position.

Rattrapage ponctuel (O6 du diagnostic) : les points créés avant le
géocodage automatique à l'adresse — ou saisis par un parcours sans
carte — reçoivent une position via Nominatim. Les points déjà
positionnés (à la main ou par la carte) ne sont JAMAIS touchés.

Usage :
    python manage.py geocoder_points            # géocode, montre le bilan
    python manage.py geocoder_points --limit 5 # au plus 5 appels
"""
from django.core.management.base import BaseCommand

from portal.geocodage import geocoder_adresse
from portal.models import PointLivraison


class Command(BaseCommand):
    help = ("Géocode (Nominatim) les points de livraison sans "
            "latitude/longitude, à partir de leur adresse.")

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0,
                            help="Nombre maximum de points à traiter "
                                 "(0 = tous).")

    def handle(self, *args, **options):
        limite = options.get("limit") or 0
        sans_position = (PointLivraison.objects
                         .filter(latitude__isnull=True)
                         | PointLivraison.objects
                         .filter(longitude__isnull=True)).distinct()
        total = sans_position.count()
        geocodes, sans_adresse, introuvables = 0, 0, 0
        for point in sans_position[:limite or None]:
            if not (point.adresse or point.ville):
                sans_adresse += 1
                continue
            position = geocoder_adresse(
                point.adresse, point.ville, point.code_postal)
            if position:
                point.latitude, point.longitude = position
                point.save(update_fields=["latitude", "longitude"])
                geocodes += 1
                self.stdout.write(f"🎯 {point.nom} ({point.ville}) : "
                                  f"{position[0]:.5f}, {position[1]:.5f}")
            else:
                introuvables += 1
                self.stdout.write(self.style.NOTICE(
                    f"❓ {point.nom} ({point.ville}) : adresse non "
                    "trouvée — à placer sur la carte."))
        bilan = (f"{geocodes} point(s) géocodé(s), "
                 f"{introuvables} adresse(s) introuvable(s), "
                 f"{sans_adresse} sans adresse, "
                 f"{total} point(s) sans position au départ.")
        if geocodes:
            self.stdout.write(self.style.SUCCESS(bilan))
        else:
            self.stdout.write(bilan)
