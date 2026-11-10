"""Répare les conserveries de démo : catalogue 100 % conserverie.

Les espaces de démonstration « Conserverie du Sor » et « Conserves de la
Villaine » ont été créées avant que le catalogue Conserverie soit
chargé : leur catalogue et leur production de la semaine ont donc été
piochés dans d'autres activités (fruits, ruche…). Cette commande :

1. supprime leurs produits HORS catalogue Conserverie ;
2. complète leur catalogue depuis les produits types Conserverie ;
3. reconstruit la production de la semaine (6 produits, estimations) ;
4. s'assure qu'une semaine à venir publiée existe.

Idempotent : relancer ne duplique rien.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from portal.models import (Categorie, Exploitant, LigneCommande,
                           LignePanier, LigneRecolte, Panier, Produit,
                           ProduitStandard, SemaineRecolte)

CONSERVERIES = [
    ("demo.conserverie.sor", Decimal("4.20"),
     "Nouvelle fournée : ratatouille et confiture de figue !"),
    ("demo.bretagne.conserverie", Decimal("4.00"),
     "Velouté de potimarron de retour en bocal 750 g."),
]


class Command(BaseCommand):
    help = ("Répare les conserveries de démo : catalogue et production "
            "de la semaine 100 % conserverie.")

    def handle(self, *args, **options):
        aujourd_hui = datetime.date.today()
        lundi = aujourd_hui - datetime.timedelta(
            days=aujourd_hui.weekday())
        for utilisateur, prix_base, note in CONSERVERIES:
            user = User.objects.filter(username=utilisateur).first()
            if user is None or not hasattr(user, "exploitant"):
                self.stdout.write(self.style.WARNING(
                    f"Compte {utilisateur} introuvable : ignoré."))
                continue
            exploitant = user.exploitant

            # 1. Produits hors catalogue conserverie. Les lignes de
            #    commande et de panier les protègent (FK PROTECT) :
            #    on supprime d'abord ces lignes (et les paniers qui
            #    se retrouvent vides), puis les produits.
            hors_catalogue = Produit.objects.filter(
                exploitant=exploitant).exclude(
                origine_standard__activite=(
                    Exploitant.Activite.CONSERVERIE))
            nb_lc, _ = LigneCommande.objects.filter(
                produit__in=hors_catalogue).delete()
            nb_lp, _ = LignePanier.objects.filter(
                produit__in=hors_catalogue).delete()
            # Paniers vidés par ces suppressions (et paniers vides)
            Panier.objects.filter(
                exploitant=exploitant, lignes__isnull=True).delete()
            supprimes = hors_catalogue.delete()[0]

            # 2. Catalogue conserverie complet (même logique que
            #    peupler_demo : catégorie type par produit, prix
            #    progressifs par catégorie, pas de doublon de slug)
            slugs_vus = set(Produit.objects.filter(
                exploitant=exploitant).values_list("slug", flat=True))
            conserverie = list(ProduitStandard.objects.filter(
                activite=Exploitant.Activite.CONSERVERIE)[:24])
            produits = list(Produit.objects.filter(
                exploitant=exploitant,
                origine_standard__activite=(
                    Exploitant.Activite.CONSERVERIE)))
            for std in conserverie:
                if Produit.objects.filter(
                        exploitant=exploitant,
                        origine_standard=std).exists():
                    continue
                slug = slugify(std.nom)
                if slug in slugs_vus:
                    continue
                slugs_vus.add(slug)
                cat, _cree = Categorie.objects.get_or_create(
                    exploitant=exploitant, nom=std.categorie)
                if _cree:
                    cat.position = exploitant.categories.count()
                    cat.save()
                rang = Produit.objects.filter(
                    exploitant=exploitant, categorie=cat).count()
                produits.append(Produit.objects.create(
                    exploitant=exploitant, nom=std.nom, categorie=cat,
                    unite_vente=std.unite_vente,
                    attributs={"saisons": std.saisons},
                    origine_standard=std,
                    prix=prix_base + Decimal(rang) * Decimal("0.50"),
                    actif=True))

            # 3. Production de la semaine (publiée) reconstruite sur
            #    6 produits conserverie, estimations 10, 12, 14…
            semaine, _cree = SemaineRecolte.objects.get_or_create(
                exploitant=exploitant, lundi=lundi,
                defaults={"note": note, "publiee": True})
            semaine.note = note
            semaine.publiee = True
            semaine.save()
            semaine.lignes.all().delete()
            for i, produit in enumerate(produits[:6]):
                LigneRecolte.objects.create(
                    recolte=semaine, produit=produit,
                    quantite_estimee=Decimal(10 + 2 * i),
                    prix_unitaire=produit.prix)

            # 4. Une semaine à venir publiée (comme peupler_demo)
            SemaineRecolte.objects.get_or_create(
                exploitant=exploitant,
                lundi=lundi + datetime.timedelta(days=7),
                defaults={"publiee": True})

            self.stdout.write(self.style.SUCCESS(
                f"🥫 {exploitant.nom_espace} : {supprimes} produit(s) "
                f"hors conserverie retiré(s) ({nb_lc} ligne(s) de "
                f"commande, {nb_lp} ligne(s) de panier), {len(produits)} "
                "produits conserverie, production de la semaine "
                "reconstruite."))
