"""Simule l'historique quotidien des dénombrements du portail (démo).

Reconstitue les photos quotidiennes de StatistiqueQuotidienne sur
les N derniers jours (60 par défaut) pour habiller les fenêtres de
stats des badges de la page de recherche : courbes croissantes à
rythme aléatoire — de 0 à 12 créations par jour et par métier,
tendance accélérée vers aujourd'hui — chaque série finissant sur
le dénombrement RÉEL du portail : badge et dernier point du graphe
concordent donc toujours.

La commande ne touche AUCUN compte : elle ne réécrit que les
lignes agrégées de StatistiqueQuotidienne (aucune donnée
personnelle) de la fenêtre demandée, hors le jour même (toujours
recalculé par la page de recherche). Relancer la commande régénère
la fenêtre avec un autre aléa ; --graine rend le tirage
reproductible.

Usage :  python manage.py simuler_stats_demo --jours 60 --graine 42
"""
import datetime
import random

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from portal.marches import identifier_marches
from portal.models import (Exploitant, StatistiqueQuotidienne, User,
                           Visiteur)

ACTIVITES_RESTAURATION = (Exploitant.Activite.FOODTRUCK,
                          Exploitant.Activite.TRAITEUR,
                          Exploitant.Activite.RESTAURANT)


def courbe(total, jours, alea, pente=1.6, maxi=12):
    """Courbe cumulée croissante de 0 à « total » en « jours » étapes.

    Le poids de chaque jour suit (position ** pente) — pente > 1
    accélère la croissance vers aujourd'hui — bruité de ±50 % et
    borné à « maxi » créations par jour. L'écart d'arrondi est
    réparti pour que le cumul final tombe EXACTEMENT sur total.
    Retourne jours + 1 cumuls (dernier = total, jour même).
    """
    if jours <= 0:
        raise CommandError("--jours : nombre de jours invalide")
    if total <= 0:
        return [0] * jours + [max(0, total)]
    poids = [(i + 1) ** pente * alea.uniform(0.5, 1.5)
             for i in range(jours)]
    somme = sum(poids)
    increments = [min(maxi, int(total * p / somme)) for p in poids]
    # Ajuster le tirage pour cumuler exactement total.
    ecart = total - sum(increments)
    for _ in range(20):
        if ecart == 0:
            break
        ordre = (sorted(range(jours), key=lambda k: poids[k],
                        reverse=ecart > 0)
                 if ecart > 0 else range(jours - 1, -1, -1))
        for k in ordre:
            if ecart == 0:
                break
            if ecart > 0:
                ajout = min(ecart, maxi - increments[k])
                increments[k] += ajout
                ecart -= ajout
            else:
                retrait = min(-ecart, increments[k])
                increments[k] -= retrait
                ecart += retrait
    if ecart != 0:
        # Données plus grosses que maxi x jours : last recours, la
        # borne par jour est relâchée au prorata.
        increments = [max(0, round(total * p / somme)) for p in poids]
        cumul, cumuls = 0, []
        for inc in increments:
            cumul += inc
            cumuls.append(cumul)
        cumuls[-1] = total
        return cumuls
    cumuls = [0]
    for inc in increments:
        cumuls.append(cumuls[-1] + inc)
    return cumuls


class Command(BaseCommand):
    help = ("Simule l'historique des dénombrements (pros par métier, "
            "marchés, boutiques, clients, visiteurs) sur les N derniers "
            "jours — voir la docstring du module.")

    def add_arguments(self, parser):
        parser.add_argument("--jours", type=int, default=60,
                            help="Taille de la fenêtre simulée "
                                 "(défaut : 60)")
        parser.add_argument("--graine", type=int, default=None,
                            help="Graine aléatoire pour un tirage "
                                 "reproductible")

    def handle(self, *args, **options):
        jours = options["jours"]
        if jours < 2:
            raise CommandError("--jours : simuler au moins 2 jours")
        alea = random.Random(options["graine"])
        aujourdhui = timezone.localdate()

        # Dénombrements cibles = état RÉEL actuel du portail, par
        # métier et par bascule Démo / Réel (les colonnes « _reels »
        # servent aux fenêtres de stats du mode 🧡 Réel).
        tous = Exploitant.objects.filter(visible=True)
        reels = tous.exclude(est_demo=True)
        marches_tous = identifier_marches(inclure_demo=True)
        nb_marches_tous = sum(1 for m in marches_tous if m["est_marche"])
        marches_reels = identifier_marches(inclure_demo=False)
        nb_marches_reels = sum(1 for m in marches_reels
                               if m["est_marche"])
        cibles = {
            "nb_locaux":
                tous.exclude(activite__in=ACTIVITES_RESTAURATION).count(),
            "nb_locaux_reels":
                reels.exclude(activite__in=ACTIVITES_RESTAURATION).count(),
            "nb_restauration":
                tous.filter(activite__in=ACTIVITES_RESTAURATION).count(),
            "nb_restauration_reels":
                reels.filter(activite__in=ACTIVITES_RESTAURATION).count(),
            "nb_marches": nb_marches_tous,
            "nb_marches_reels": nb_marches_reels,
            "nb_boutiques": len(marches_tous) - nb_marches_tous,
            "nb_boutiques_reels": len(marches_reels) - nb_marches_reels,
            "nb_clients": (User.objects
                           .filter(exploitant__isnull=True,
                                   membres_exploitation__isnull=True)
                           .count()),
            "nb_visiteurs": Visiteur.objects.count(),
        }
        courbes = {cle: courbe(total, jours, alea)
                   for cle, total in cibles.items()}
        for cle, total in cibles.items():
            if courbes[cle][jours] != total:
                raise CommandError(
                    "Courbe incohérente pour " + cle + " : "
                    + str(courbes[cle][jours]) + " != " + str(total))
        # Les variantes réelles ne peuvent pas dépasser les totaux
        # du jour correspondant (files de la bascule Démo / Réel).
        for reelle, complete in (("nb_locaux_reels", "nb_locaux"),
                                ("nb_restauration_reels",
                                 "nb_restauration"),
                                ("nb_marches_reels", "nb_marches"),
                                ("nb_boutiques_reels", "nb_boutiques")):
            for i in range(jours + 1):
                courbes[reelle][i] = min(courbes[reelle][i],
                                         courbes[complete][i])

        # Écriture : jours simulés jusqu'à hier, le jour même reste
        # recalculé par la page de recherche (photo du jour réelle).
        ecrits = 0
        for i in range(jours):
            date = aujourdhui - datetime.timedelta(days=jours - i)
            locaux = courbes["nb_locaux"][i]
            restos = courbes["nb_restauration"][i]
            locaux_r = courbes["nb_locaux_reels"][i]
            restos_r = courbes["nb_restauration_reels"][i]
            StatistiqueQuotidienne.objects.update_or_create(
                date=date,
                defaults={
                    "nb_producteurs": locaux + restos,
                    "nb_pros_reels": locaux_r + restos_r,
                    "nb_locaux": locaux,
                    "nb_locaux_reels": locaux_r,
                    "nb_restauration": restos,
                    "nb_restauration_reels": restos_r,
                    "nb_marches": courbes["nb_marches"][i],
                    "nb_marches_reels": courbes["nb_marches_reels"][i],
                    "nb_boutiques": courbes["nb_boutiques"][i],
                    "nb_boutiques_reels":
                        courbes["nb_boutiques_reels"][i],
                    "nb_clients": courbes["nb_clients"][i],
                    "nb_visiteurs": courbes["nb_visiteurs"][i],
                })
            ecrits += 1

        resume = ", ".join(cle + "=" + str(total)
                           for cle, total in cibles.items())
        self.stdout.write(self.style.SUCCESS(
            "Historique simulé : " + str(ecrits)
            + " jours (jusqu'à hier). Cibles du jour : " + resume))
