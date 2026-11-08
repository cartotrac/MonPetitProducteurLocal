"""Peuple l'instance avec des fermes et clients de DÉMONSTRATION.

Crée des exploitations fictives — le Tarn, ses départements
limitrophes (Aveyron, Aude, Hérault, Haute-Garonne, Tarn-et-Garonne),
la Bretagne, la Loire, la Corse, La Réunion et la Martinique — avec
des catalogues MIXTES multi-catégories (issus des produits types),
points de livraison, créneaux, récoltes de la semaine, clients de démo
et un historique de commandes/paniers couvrant tous les statuts : de
quoi montrer le portail de bout en bout, y compris la recherche
géographique, en quelques clics.

Les fermes de démo sont identifiables partout (vignettes de recherche,
carte, fiche producteur) par un badge 🧪 DÉMO et le champ
« Exploitation de démonstration » (page Paramètres).

⚠️ Toutes les données sont FICTIVES : noms, SIRET (valides au format
Luhn mais inventés), adresses et coordonnées ne référencent aucune
entreprise réelle.

Usage :
    python manage.py peupler_demo            # crée si absent (idempotent)
    python manage.py peupler_demo --purge   # supprime les comptes de démo
    python manage.py peupler_demo --reset-commandes
                                           # PONCTUEL : efface TOUTES
                                           # les commandes/paniers
                                           # (comptes réels inclus)
    python manage.py peupler_demo --reset-commandes-demo
                                           # courant : efface les
                                           # commandes/paniers des
                                           # SEULES fermes de démo et
                                           # régénère le jeu

Comptes d'essai « sans engagement » (mot de passe demo1234!) :
    demo.pro     : espace producteur (La Ferme Découverte)
    demo.public  : espace client (Camille Public)

La purge efface TOUS les comptes de démo : ceux du jeu actuel, tout
compte en « demo.* » et toute exploitation marquée « démo » dans la
base (même issue d'un jeu plus ancien) — le jeu peut donc être purgé
et repeuplé à volonté.

Comptes créés (mot de passe : demo1234!) :
    Tarn        : demo.maraicher, demo.vergers, demo.fromager
    Limitrophes : demo.aveyron.eleveur, demo.aveyron.maraicher,
                  demo.aude.apiculteur, demo.herault.arboriculteur,
                  demo.toulouse.fromager, demo.montauban.maraicher
    Bretagne    : demo.brest.maraicher, demo.rennes.eleveur
    Loire       : demo.loire.maraicher, demo.loire.apiculteur
    Corse       : demo.corse.eleveur, demo.corse.fromager
    Réunion     : demo.reunion.maraicher, demo.reunion.arboriculteur
    Martinique  : demo.martinique.maraicher, demo.martinique.eleveur
    Brasseries : demo.brasserie.sor, demo.brasserie.leguer
    Foodtrucks  : demo.foodtruck.pizza.lavaur,
                  demo.foodtruck.pizza.rennes,
                  demo.foodtruck.burger.castres,
                  demo.foodtruck.sandwichs.albi,
                  demo.foodtruck.rotisseur.toulouse
    Traiteurs   : demo.traiteur.gaillac, demo.traiteur.lavaur,
                  demo.traiteur.montauban, demo.traiteur.brest,
                  demo.traiteur.rennes
    Clients     : demo.cliente, demo.client
    Marchés    : jeu étendu « marchés & boutiques partagés » —
                 demo.maraicher.giroussens, demo.apiculteur.lavaur,
                 demo.arboriculteur.lavaur, demo.eleveur.lavaur
                 (marché de Lavaur), demo.fromager.gaillac,
                 demo.maraicher.gaillac (marché de Gaillac),
                 demo.conserverie.gaillac, demo.miellerie.gaillac
                 (boutique de la gare de Gaillac), demo.traiteur.castres,
                 demo.foodtruck.crepes.gaillac
"""
import datetime
from decimal import Decimal
from itertools import count

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils.text import slugify
from django.utils import timezone

from portal.models import (Bulletin, Carte, Categorie, Commande,
                           CreneauLivraison, Exploitant, LigneCarte,
                           LigneCommande, LignePanier, LigneRecolte,
                           Panier, PointLivraison, Produit,
                           ProduitStandard, ProfilClient, SemaineRecolte)

MOT_DE_PASSE_DEMO = "demo1234!"

# Tables dont les séquences (PostgreSQL) sont réinitialisées après
# un effacement des commandes / paniers : les nouveaux objets
# repartent des index 1 au lieu de continuer la numérotation.
TABLES_SEQUENCE = ("portal_commande", "portal_panier",
                   "portal_lignecommande", "portal_lignepanier")


def reinitialiser_sequences():
    """Repositionne les compteurs d'id de PostgreSQL à 1 pour les
    tables de commandes et paniers (sans effet sur les autres SGBD)."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as curseur:
        for table in TABLES_SEQUENCE:
            curseur.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), 1, false)",
                [table])


def _siret_valide(prefixe13):
    """Complète 13 chiffres par la clé de Luhn (règle du modèle Produit
    — indices pairs doublés depuis la gauche sur 14 chiffres)."""
    total = 0
    for i, chiffre in enumerate(prefixe13):
        valeur = int(chiffre)
        if i % 2 == 0:
            valeur *= 2
            if valeur > 9:
                valeur -= 9
        total += valeur
    cle = (10 - total % 10) % 10
    return prefixe13 + str(cle)


_SIRET_SEQ = count(1)


def _ferme_spec(utilisateur, ferme, activite, mode, cp, adresse, ville,
                lat, lon, tel, description, prix_base, mix, points,
                creneaux, note_semaine, bulletin_objet, bulletin_corps,
                specialite=None, type_point=None):
    """Construit la spécification d'une ferme de démo (appel compact).
    Le préfixe SIRET (13 chiffres, clé de Luhn ajoutée ensuite) est
    dérivé du code postal + un compteur global unique."""
    return {
        "utilisateur": utilisateur, "ferme": ferme, "activite": activite,
        "mode": mode,
        "siret_prefixe": cp + "123400" + str(next(_SIRET_SEQ)).zfill(2),
        "adresse": adresse, "ville": ville, "cp": cp,
        "lat": lat, "lon": lon, "tel": tel,
        "description": description, "prix_base": prix_base, "mix": mix,
        "specialite": specialite, "type_point": type_point,
        "points": points, "creneaux": creneaux, "note_semaine": note_semaine,
        "bulletin": (bulletin_objet, bulletin_corps),
    }


A = Exploitant.Activite
M = Exploitant.ModeProduction


def _type_deduit(nom):
    """Devine le type d'un point d'après son libellé (jeu de démo) :
    « Marché … » / « Halle … » → Marché, « Boutique … » → Boutique ;
    sinon le type par défaut (point de livraison)."""
    bas = nom.lower()
    if bas.startswith(("marché", "marche", "halle")):
        return PointLivraison.Type.MARCHE
    if bas.startswith("boutique"):
        return PointLivraison.Type.BOUTIQUE
    return PointLivraison.Type.LIVRAISON

FERMES = [
    # ── Tarn ──────────────────────────────────────────────────────
    {
        "utilisateur": "demo.maraicher",
        "ferme": "Les Jardins du Sor",
        "activite": A.MARAICHER, "mode": M.PERMA,
        "siret_prefixe": "8150012300003",
        "adresse": "Chemin de Gandalou", "ville": "Lavaur",
        "cp": "81500", "lat": 43.699, "lon": 1.915,
        "tel": "05 63 00 00 03",
        "description": ("Jardin maraîcher en permaculture dans la vallée "
                        "du Sor : légumes de saison, herbes aromatiques, "
                        "œufs fermiers et fruits du verger, en "
                        "distribution directe."),
        "prix_base": Decimal("2.20"),
        "mix": [
            {"activite": A.MARAICHER, "limite": 24},
            {"activite": A.ARBORICULTEUR, "categorie": "Fruits",
             "limite": 6},
            {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 2},
            {"activite": A.APICULTEUR, "limite": 3},
        ],
        "points": [
            ("Marché de Lavaur", "Place de la Halle",
             "Lavaur", "81500", 43.700, 1.900),
            ("Quai de Rabastens", "Parking des halles",
             "Rabastens", "81600", 43.820, 1.722),
        ],
        "creneaux": [(6, "08:00", "12:00", 0), (2, "17:30", "19:30", 1)],
        "note_semaine": "Arrivée des premières courges — butternut et potimarron !",
        "bulletin": ("Paniers de la semaine aux Jardins du Sor",
                     "Courges d'hiver, poireaux, choux kale et salades "
                     "d'automne. Œufs fermiers en nombre limité, "
                     "pensez à les réserver avec votre panier."),
    },
    {
        "utilisateur": "demo.vergers",
        "ferme": "Les Vergers de l'Agout",
        "activite": A.ARBORICULTEUR, "mode": M.AB,
        "siret_prefixe": "8137012340001",
        "adresse": "Chemin des Hauts, lieu-dit Las Rives",
        "ville": "Saint-Sulpice-la-Pointe", "cp": "81370",
        "lat": 43.656, "lon": 2.138,
        "tel": "05 63 00 00 01",
        "description": ("Vergers familiaux conduits en agriculture "
                        "biologique au bord de l'Agout : pommes, poires, "
                        "petits fruits et jus de la ferme, récoltés à "
                        "maturité et vendus en circuit court."),
        "prix_base": Decimal("1.90"),
        "mix": [
            {"activite": A.ARBORICULTEUR, "limite": 20},
            {"activite": A.APICULTEUR, "limite": 4},
            {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 3},
        ],
        "points": [
            ("Marché de Saint-Sulpice", "Place de la Halle",
             "Saint-Sulpice-la-Pointe", "81370", 43.660, 2.140),
            ("Place de Gaillac", "Place du marché couvert",
             "Gaillac", "81600", 43.900, 1.895),
        ],
        "creneaux": [(6, "08:30", "12:00", 0), (3, "17:00", "19:00", 1)],
        "note_semaine": "Premières pommes Gala de la saison — mûres à point !",
        "bulletin": ("Récolte de la semaine aux Vergers de l'Agout",
                     "Pommes Gala et Reinette arrivent au marché, "
                     "poires Williams à maturité. Les barquettes de "
                     "framboises partent vite : commandez tôt !"),
    },
    {
        "utilisateur": "demo.fromager",
        "ferme": "Ferme des Cabanes",
        "activite": A.FROMAGER, "mode": M.PAYSAN,
        "siret_prefixe": "8128076540002",
        "adresse": "Route de Montredon, lieu-dit Les Cabanes",
        "ville": "Réalmont", "cp": "81280",
        "lat": 43.778, "lon": 2.531,
        "tel": "05 63 00 00 02",
        "description": ("Ferme fromagère familiale en agriculture paysanne "
                        "sur les coteaux du Dadou : tomme de brebis, "
                        "fromages frais et caillé, fabrication à la ferme "
                        "en bidons de cuivre."),
        "prix_base": Decimal("4.50"),
        "mix": [
            {"activite": A.FROMAGER, "limite": 20},
            {"activite": A.APICULTEUR, "limite": 2},
            {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 2},
        ],
        "points": [
            ("Halte de Réalmont", "Place de la République",
             "Réalmont", "81280", 43.775, 2.528),
            ("Marché de Castres", "Place Jean Jaurès (étal n°12)",
             "Castres", "81100", 43.605, 2.242),
        ],
        "creneaux": [(6, "09:00", "12:30", 0), (4, "16:30", "18:30", 1)],
        "note_semaine": "Tomme de brebis affinée 3 mois — stock limité.",
        "bulletin": ("Fromages de la semaine à la Ferme des Cabanes",
                     "La tomme de brebis 3 mois d'affinage est de retour ! "
                     "Fromage frais du vendredi et caillé à emporter "
                     "directement au marché."),
    },
    # ── Conserveries (nouvelle activité 🥫) ────────────────────────
    _ferme_spec(
        "demo.conserverie.sor", "Conserverie du Sor", A.CONSERVERIE,
        M.AB, "81500", "Le Bourg, lieu-dit Las Garrigues",
        "Giroussens", 43.832, 1.696, "05 63 00 00 21",
        "Atelier de transformation en agriculture biologique dans la "
        "vallée du Sor : confitures cuites au chaudron, bocaux de "
        "légumes, terrines et coulis, tout est fait à la ferme.",
        Decimal("4.20"),
        [{"activite": A.CONSERVERIE, "limite": 24}],
        [("Marché de Giroussens", "Place de la Halle",
          "Giroussens", "81500", 43.835, 1.690),
         ("Marché de Lavaur", "Place de la Halle",
          "Lavaur", "81500", 43.700, 1.900)],
        [(6, "08:30", "12:30", 0), (5, "16:00", "19:00", 1)],
        "Nouvelle fournée : ratatouille et confiture de figue !",
        "Bocaux de la semaine à la Conserverie du Sor",
        "Terrine de campagne, ratatouille et coulis de tomate "
        "sortent de l'atelier ; la confiture de figue part vite, "
        "pensez à réserver vos bocaux."),
    _ferme_spec(
        "demo.bretagne.conserverie", "Conserves de la Villaine",
        A.CONSERVERIE, M.PAYSAN, "35310",
        "Route de Bain, lieu-dit Le Boël",
        "Bain-de-Bretagne", 47.842, -1.682, "02 99 00 00 22",
        "Conserverie paysanne en Ille-et-Vilaine : soupes et veloutés "
        "du jardin, conserves de légumes bretons, terrines et sauces "
        " maison, cuissons de saison.",
        Decimal("4.00"),
        [{"activite": A.CONSERVERIE, "limite": 24}],
        [("Marché de Bain", "Place du Champ de Foire",
          "Bain-de-Bretagne", "35310", 47.840, -1.680)],
        [(6, "09:00", "12:30", 0)],
        "Velouté de potimarron de retour en bocal 750 g.",
        "Bocaux de la semaine aux Conserves de la Villaine",
        "Soupes d'hiver, choucroute et haricots verts en bocal, "
        "terrine de campagne de la semaine : tout est au marché de "
        "Bain dès 9 h."),
    # ── Comptes d'essai « sans engagement » ────────────────────────
    # Fermes à communiquer aux personnes qui veulent tester l'espace
    # pro sans créer leur compte : demo.pro (producteur) et
    # demo.public (client, dans CLIENTS ci-dessous).
    _ferme_spec(
        "demo.pro", "La Ferme Découverte", A.MARAICHER,
        M.AB, "81500", "Route de Sor, lieu-dit Larérou",
        "Lavaur", 43.700, 1.905, "05 63 00 00 30",
        "Ferme d'essai du portail : espace pro de démonstration à "
        "communiquer aux producteurs qui veulent tester sans créer "
        "leur compte. Maraîchage bio, paniers hebdomadaires.",
        Decimal("2.50"),
        [{"activite": A.MARAICHER, "limite": 20},
         {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 3},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché de Lavaur", "Place de la Halle",
          "Lavaur", "81500", 43.700, 1.900)],
        [(6, "08:00", "12:00", 0), (3, "17:00", "19:00", 0)],
        "Semaine d'essai : salades, radis et premières courges.",
        "Paniers de la semaine à la Ferme Découverte",
        "L'espace pro de cette ferme est un compte d'essai : "
        "expérimentez librement les produits, récoltes et commandes."),
    # ── Aveyron (2) ──────────────────────────────────────────────
    _ferme_spec(
        "demo.aveyron.eleveur", "Ferme de l'Aubrac", A.ELEVEUR, M.PAYSAN,
        "12200", "Route de Laguiole, lieu-dit Coubjacou",
        "Villefranche-de-Rouergue", 44.349, 2.032, "05 65 00 00 04",
        "Élevage d'Aubrac en agriculture paysanne sur les causse : "
        "viande de bœuf et d'agneau, vente directe à la ferme et au "
        "marché de Villefranche.",
        Decimal("6.00"),
        [{"activite": A.ELEVEUR, "limite": 20},
         {"activite": A.APICULTEUR, "limite": 3}],
        [("Marché de Villefranche", "Place de la Halle",
          "Villefranche-de-Rouergue", "12200", 44.350, 2.030)],
        [(6, "08:00", "12:00", 0)],
        "Agneaux de pâturage prêts pour les fêtes de fin d'année.",
        "Viande de la semaine à la Ferme de l'Aubrac",
        "Colis de bœuf et agneau disponibles à la ferme ; le miel de "
        "causse part vite, réservez-le avec votre colis."),
    _ferme_spec(
        "demo.aveyron.maraicher", "Les Jardins de l'Ondes", A.MARAICHER,
        M.AB, "12000", "Chemin des Berges, Vallon des Ondes",
        "Rodez", 44.561, 2.575, "05 65 00 00 05",
        "Maraîchage biologique sur les hauteurs de Rodez : légumes de "
        "saison, salades et herbes, paniers hebdomadaires.",
        Decimal("2.40"),
        [{"activite": A.MARAICHER, "limite": 20},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché couvert de Rodez", "Place du Foirail",
          "Rodez", "12000", 44.352, 2.573)],
        [(6, "08:00", "12:30", 0), (4, "16:30", "19:00", 0)],
        "Retour des épinards d'hiver et des mâches.",
        "Paniers de la semaine aux Jardins de l'Ondes",
        "Légumes racines, choux et salades d'hiver du Rouergue. "
        "Paniers de 5 ou 8 € à retirer au Foirail."),
    # ── Aude (1) ──────────────────────────────────────────────────
    _ferme_spec(
        "demo.aude.apiculteur", "Ruchers de la Clamoux", A.APICULTEUR,
        M.AB, "11170", "Vallée de la Clamoux, lieu-dit La Prade",
        "Caunes-Minervois", 43.336, 2.531, "04 68 00 00 06",
        "Ruchers d'altitude sur les contreforts de la Montagne Noire : "
        "miels de garrigue, châtaignier et fleurs de printemps, cires "
        "et pollens, en bio.",
        Decimal("4.00"),
        [{"activite": A.APICULTEUR, "limite": 20},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits", "limite": 4}],
        [("Marché de Caunes", "Place de la Halle",
          "Caunes-Minervois", "11170", 43.335, 2.530)],
        [(3, "16:00", "19:00", 0)],
        "Récolte de miel de châtaignier — berlingots disponibles.",
        "Miel de la semaine aux Ruchers de la Clamoux",
        "Miels de garrigue et de châtaignier du Minervois, cire "
        "d'abeille et pollen frais. Vente au marché le mercredi."),
    # ── Hérault (1) ───────────────────────────────────────────────
    _ferme_spec(
        "demo.herault.arboriculteur", "Les Oliviers du Vic", A.ARBORICULTEUR,
        M.RAISONNE, "34500", "Chemin du Vic, lieu-dit Le Puech",
        "Béziers", 43.343, 3.221, "04 67 00 00 07",
        "Oliviers et vergers du Biterrois : huile d'olive de la "
        "première pression, olives de table, pêches et abricots "
        "de pleine saison, en agriculture raisonnée.",
        Decimal("2.10"),
        [{"activite": A.ARBORICULTEUR, "limite": 20},
         {"activite": A.APICULTEUR, "limite": 3},
         {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 3}],
        [("Les Halles de Béziers", "Place Pierre-Pascal",
          "Béziers", "34500", 43.341, 3.218)],
        [(5, "08:00", "12:00", 0)],
        "Nouvelle huile d'olive AOC — tombée début novembre.",
        "Récolte de la semaine aux Oliviers du Vic",
        "Huile d'olive nouvelle, olives cassées et pêches de vigne. "
        "Œufs du jour et miel de garrigue en complément."),
    # ── Haute-Garonne (1) ─────────────────────────────────────────
    _ferme_spec(
        "demo.toulouse.fromager", "Ferme du Lauragais", A.FROMAGER,
        M.PAYSAN, "31250", "Route de Sorèze, lieu-dit Lacombe",
        "Revel", 43.460, 2.004, "05 61 00 00 08",
        "Ferme du Lauragais au bord du lac de Saint-Ferréol : tomme de "
        "vache, fromages frais et yaourts au lait cru, fabrication "
        "à la ferme deux fois par jour.",
        Decimal("5.00"),
        [{"activite": A.FROMAGER, "limite": 18},
         {"activite": A.APICULTEUR, "limite": 2},
         {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 2}],
        [("Halle de Revel", "Place de la Halle",
          "Revel", "31250", 43.455, 2.007)],
        [(6, "09:00", "12:00", 0), (2, "17:00", "19:00", 0)],
        "Yaourts au lait cru à la vanille — fabrication du samedi.",
        "Fromages de la semaine à la Ferme du Lauragais",
        "Tomme de vache du Lauragais, fromage frais et yaourts. "
        "La traite du soir, c'est à 17 h : venez y goûter !"),
    # ── Tarn-et-Garonne (1) ───────────────────────────────────────
    _ferme_spec(
        "demo.montauban.maraicher", "Jardins du Tarn-et-Garonne",
        A.MARAICHER, M.PERMA, "82000", "Chemin de Sapiac",
        "Montauban", 44.017, 1.355, "05 63 00 00 09",
        "Maraîchage en permaculture dans la plaine du Tarn : légumes "
        "de saison, aromatiques et petits fruits, paniers et marché "
        "de Montauban.",
        Decimal("2.30"),
        [{"activite": A.MARAICHER, "limite": 18},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits", "limite": 5},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché de Sapiac", "Marché couvert de Sapiac",
          "Montauban", "82000", 44.012, 1.348)],
        [(6, "08:00", "12:00", 0), (3, "16:30", "19:00", 0)],
        "Choux-fleurs et brocolis — pleine saison.",
        "Paniers de la semaine aux Jardins du Tarn-et-Garonne",
        "Légumes d'automne de la plaine : choux, poireaux, salades. "
        "Pommes et poires du verger en supplément du panier."),
    # ── Bretagne (2) ──────────────────────────────────────────────
    _ferme_spec(
        "demo.brest.maraicher", "Jardins de l'Élorn", A.MARAICHER, M.AB,
        "29000", "Route de Landerneau, lieu-dit Kerivad",
        "Quimper", 47.996, -4.108, "02 98 00 00 10",
        "Maraîchage bio en bord d'Élorn : choux-fleurs, artichauts, "
        "poireaux et pommes de terre de primeur, le goût du "
        "littoral breton.",
        Decimal("2.60"),
        [{"activite": A.MARAICHER, "limite": 20},
         {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 3},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché de Quimper", "Place du Jubilé",
          "Quimper", "29000", 47.997, -4.100)],
        [(5, "08:00", "12:30", 0)],
        "Artichauts bretons primeurs — arrive en quantité cette semaine.",
        "Paniers de la semaine aux Jardins de l'Élorn",
        "Choux-fleurs, artichauts et poireaux du Finistère. Œufs "
        "de pleines mer du vendredi, beurre demi-sel de la ferme."),
    _ferme_spec(
        "demo.rennes.eleveur", "Ferme de la Vilaine", A.ELEVEUR, M.RAISONNE,
        "35600", "Les Rives de la Vilaine, lieu-dit Tréhan",
        "Redon", 47.652, -2.083, "02 99 00 00 11",
        "Élevage bovin en agriculture raisonnée dans la vallée de la "
        "Vilaine : veaux, bœufs et porc de la ferme, colis et "
        "vente directe.",
        Decimal("5.80"),
        [{"activite": A.ELEVEUR, "limite": 18},
         {"activite": A.FROMAGER, "limite": 5}],
        [("Marché de Redon", "Place de la République",
          "Redon", "35600", 47.650, -2.080)],
        [(6, "08:30", "12:30", 0)],
        "Colis de bœuf : commandes avant le vendredi midi.",
        "Viande de la semaine à la Ferme de la Vilaine",
        "Colis de bœuf et de veau de la vallée de la Vilaine ; "
        "tomme fermière et fromage frais en complément du colis."),
    # ── Loire (2) ─────────────────────────────────────────────────
    _ferme_spec(
        "demo.loire.maraicher", "Jardins du Gier", A.MARAICHER, M.PERMA,
        "42400", "Rue du Gier, lieu-dit Montferré",
        "Saint-Chamond", 45.473, 4.522, "04 77 00 00 12",
        "Maraîchage en permaculture dans la vallée du Gier : légumes "
        "de saison et aromatiques, paniers hebdomadaires à "
        "Saint-Chamond et Saint-Étienne.",
        Decimal("2.50"),
        [{"activite": A.MARAICHER, "limite": 18},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits", "limite": 5},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché de Saint-Chamond", "Place de la Halle",
          "Saint-Chamond", "42400", 45.470, 4.530),
         ("Marché de Saint-Étienne", "Grand Marché de Carnot",
          "Saint-Étienne", "42000", 45.439, 4.387)],
        [(6, "08:00", "12:00", 0), (5, "08:00", "12:00", 1)],
        "Cardons et blettes du Gier, spécialités foréziennes.",
        "Paniers de la semaine aux Jardins du Gier",
        "Légumes de la vallée du Gier : cardons, blettes, poireaux. "
        "Pommes du Pilat et miel de sapin en supplément."),
    _ferme_spec(
        "demo.loire.apiculteur", "Ruchers du Pilat", A.APICULTEUR, M.AB,
        "42220", "Route du Pilat, lieu-dit Les Sellières",
        "Bourg-Argental", 45.322, 4.292, "04 77 00 00 13",
        "Ruchers d'altitude dans le parc naturel du Pilat : miels de "
        "sapin, d'acacia et de montagne, gelée royale et propolis, "
        "en agriculture biologique.",
        Decimal("5.20"),
        [{"activite": A.APICULTEUR, "limite": 20},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits", "limite": 4}],
        [("Marché de Bourg-Argental", "Place de la Halle",
          "Bourg-Argental", "42220", 45.320, 4.290)],
        [(3, "16:00", "19:00", 0)],
        "Miel de sapin du Pilat — récolte d'altitude exceptionnelle.",
        "Miel de la semaine aux Ruchers du Pilat",
        "Miels de sapin et d'acacia du massif du Pilat, pollen et "
        "propolis. Pommes des vergers voisins en supplément."),
    # ── Corse (2) ─────────────────────────────────────────────────
    _ferme_spec(
        "demo.corse.eleveur", "Bergerie de Restonica", A.ELEVEUR, M.PAYSAN,
        "20250", "Route de la Restonica, lieu-dit Talcu",
        "Corte", 42.309, 9.148, "04 95 00 00 14",
        "Bergerie transhumante de la vallée de la Restonica : agneaux "
        "de lait, brocciu et charcuterie de montagne, les saveurs "
        "de la Corse de l'intérieur.",
        Decimal("7.00"),
        [{"activite": A.ELEVEUR, "limite": 18},
         {"activite": A.FROMAGER, "limite": 6},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché de Corte", "Place Paoli",
          "Corte", "20250", 42.306, 9.150)],
        [(5, "08:00", "12:00", 0)],
        "Brocciu frais de la traite du matin — du mardi au vendredi.",
        "Produits de la semaine à la Bergerie de Restonica",
        "Brocciu AOP, agneau de lait et figatellu de la vallée. "
        "Miel de maquis de nos ruchers d'altitude en supplément."),
    _ferme_spec(
        "demo.corse.fromager", "Fromagerie de Balagne", A.FROMAGER, M.AB,
        "20260", "Route de Calenzana, lieu-dit Spano",
        "Calvi", 42.569, 8.762, "04 95 00 00 15",
        "Fromagerie de brebis en Balagne, entre mer et montagne : "
        "tomme corse, brin d'amour et fromages frais, en "
        "agriculture biologique.",
        Decimal("6.50"),
        [{"activite": A.FROMAGER, "limite": 18},
         {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 2}],
        [("Port de Calvi", "Quai des Pêcheurs (étal été)",
          "Calvi", "20260", 42.570, 8.760)],
        [(6, "09:00", "12:30", 0)],
        "Brin d'amour affiné 2 mois — lot limité.",
        "Fromages de la semaine à la Fromagerie de Balagne",
        "Tomme corse et brin d'amour de la Balagne, fromage frais "
        "du vendredi. Œufs de la ferme voisine en supplément."),
    # ── La Réunion (2) ────────────────────────────────────────────
    _ferme_spec(
        "demo.reunion.maraicher", "Légumes des Hauts", A.MARAICHER, M.AB,
        "97410", "Chemin des Manguiers, Les Savannahs",
        "Saint-Pierre", -21.339, 55.478, "06 92 00 00 16",
        "Maraîchage bio sur les hauts de Saint-Pierre : chouchous, "
        "brèdes, piments et légumes créoles, paniers du terroir "
        "réunionnais.",
        Decimal("3.00"),
        [{"activite": A.MARAICHER, "limite": 20},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits", "limite": 5}],
        [("Marché forain de Saint-Pierre", "Terrain de l'Est",
          "Saint-Pierre", "97410", -21.340, 55.480)],
        [(6, "07:00", "11:00", 0), (3, "16:00", "18:00", 0)],
        "Chouchous des hauts — pleine récolte cette semaine.",
        "Paniers de la semaine aux Légumes des Hauts",
        "Brèdes songes, chouchous, piments et légumes créoles de "
        "La Réunion. Mangues et ananas Victoria du jardin en "
        "supplément du panier."),
    _ferme_spec(
        "demo.reunion.arboriculteur", "Vanilleraie de Sainte-Suzanne",
        A.ARBORICULTEUR, M.RAISONNE, "97441", "Chemin de la Vanilleraie",
        "Sainte-Suzanne", -20.906, 55.612, "06 92 00 00 17",
        "Vanilleraie et verger tropical au pied de la Rivière du "
        "Mât : gousses de vanille Bourbon, ananas Victoria et "
        "fruits de la passion, préparés à la ferme.",
        Decimal("3.50"),
        [{"activite": A.ARBORICULTEUR, "limite": 15},
         {"activite": A.APICULTEUR, "limite": 3}],
        [("Marché de Saint-André", "Champ Bazar",
         "Saint-André", "97490", -20.960, 55.650)],
        [(5, "07:30", "11:30", 0)],
        "Ananas Victoria mûres — récolte du jeudi.",
        "Récolte de la semaine à la Vanilleraie de Sainte-Suzanne",
        "Gousses de vanille Bourbon préparées à la ferme, ananas "
        "Victoria et fruits de la passion. Miel de fleurs tropicales "
        "des ruches du jardin."),
    # ── Martinique (2) ────────────────────────────────────────────
    _ferme_spec(
        "demo.martinique.maraicher", "Jardins Créoles du Lamentin",
        A.MARAICHER, M.AB, "97232", "Route de Duclos, lieu-dit La Jetée",
        "Le Lamentin", 14.610, -60.941, "06 96 00 00 18",
        "Maraîchage bio en plein cœur de la Martinique : ignames, "
        "dachines, christophines et légumes créoles, paniers "
        "ékotè et marché du Lamentin.",
        Decimal("3.20"),
        [{"activite": A.MARAICHER, "limite": 18},
         {"activite": A.APICULTEUR, "limite": 3}],
        [("Marché du Lamentin", "Place du Marché Couvert",
          "Le Lamentin", "97232", 14.608, -60.939)],
        [(6, "07:00", "11:00", 0), (4, "15:30", "18:00", 0)],
        "Ignames pays — récolte fraîche du jour.",
        "Paniers de la semaine aux Jardins Créoles",
        "Ignames, dachines, christophines et légumes créoles du "
        "Lamentin. Miel de fleurs de canne des ruches de la "
        "habitation voisine."),
    _ferme_spec(
        "demo.martinique.eleveur", "Élevage des Trois-Îlets",
        A.ELEVEUR, M.PAYSAN, "97229", "Route d'Anse à l'Âne",
        "Les Trois-Îlets", 14.541, -61.031, "06 96 00 00 19",
        "Élevage paysan face à la baie de Fort-de-France : porc "
        "créole, volailles de plein air et produits de la ferme "
        "transformés sur place.",
        Decimal("5.50"),
        [{"activite": A.ELEVEUR, "limite": 16},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché des Trois-Îlets", "Place des Artisans",
          "Les Trois-Îlets", "97229", 14.540, -61.035)],
        [(5, "08:00", "12:00", 0)],
        "Poulets de plein air — commande avant le jeudi.",
        "Produits de la semaine à l'Élevage des Trois-Îlets",
        "Porc créole, volailles de plein air et boudin de la "
        "ferme. Miel de forêt tropicale en supplément du colis."),
    # ── Micro-brasseries (mode boutique / stock à date) ───────────
    _ferme_spec(
        "demo.brasserie.sor", "Brasserie du Sor", A.MICRO_BRASSEUR, M.AB,
        "81600", "Route de Cordes, lieu-dit Les Chais",
        "Gaillac", 43.898, 1.898, "05 63 00 00 20",
        "Micro-brasserie bio au bord du Sor : blondes, ambrées, IPA et "
        "bières de saison brassées en petits lots, fûts et bouteilles "
        "en vente directe à la boutique de la brasserie.",
        Decimal("4.00"),
        [{"activite": A.MICRO_BRASSEUR, "limite": 18},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Boutique de la brasserie", "Route de Cordes",
          "Gaillac", "81600", 43.897, 1.899),
         ("Marché de Gaillac", "Place du marché couvert",
          "Gaillac", "81600", 43.900, 1.895)],
        [(5, "16:00", "19:30", 0), (6, "08:30", "12:30", 1)],
        "Nouvelle IPA aux houblons du Tarn — série limitée !",
        "Bières de la semaine à la Brasserie du Sor",
        "L'IPA aux houblons locaux arrive en fûts et en bouteilles ; "
        "la rousse de garde et la blanche restent disponibles toute la "
        "semaine en boutique. Miel de bruyère de la ferme voisine."),
    _ferme_spec(
        "demo.brasserie.leguer", "Brasserie du Léguer", A.MICRO_BRASSEUR,
        M.RAISONNE, "22300", "Quai du Léguer, zone du Rosmeur",
        "Lannion", 48.732, -3.478, "02 96 00 00 21",
        "Micro-brasserie lannionnaise en agriculture raisonnée : "
        "blondes et brunes maltées, weizen épicée et stout au blé noir, "
        "fûts 20 L pour les Associations et bouteilles en boutique.",
        Decimal("4.20"),
        [{"activite": A.MICRO_BRASSEUR, "limite": 18},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Boutique de la brasserie", "2 quai du Léguer",
          "Lannion", "22300", 48.733, -3.477)],
        [(3, "15:00", "19:00", 0), (5, "15:00", "19:00", 0)],
        "Stout au blé noir : le lot de novembre arrive en boutique.",
        "Bières de la semaine à la Brasserie du Léguer",
        "Blonde, ambrée et weizen en bouteilles et en fûts ; le stout "
        "au blé noir arrive mercredi. Miel de sarrasin des ruches de "
        "la baie de Lannion en complément."),
    # ── Foodtrucks 🚚 : emplacements du soir, spécialité au camion ─
    _ferme_spec(
        "demo.foodtruck.pizza.lavaur", "Pizza Vago", A.FOODTRUCK,
        M.RAISONNE, "81500", "Place de la Halle (parking nord)",
        "Lavaur", 43.700, 1.918, "05 63 00 00 41",
        "Camion pizza du centre de Lavaur : pâte fraîche du jour, "
        "cuisson au feu de bois, margherita, reine et 4 fromages, "
        "menus du soir et desserts maison.",
        Decimal("9.00"),
        [{"activite": A.FOODTRUCK, "limite": 12}],
        [("Emplacement Place de la Halle", "Place de la Halle",
          "Lavaur", "81500", 43.700, 1.900),
         ("Quai de Rabastens", "Parking des halles",
          "Rabastens", "81600", 43.820, 1.722)],
        [(4, "18:00", "21:30", 0), (5, "18:00", "22:00", 0),
         (6, "11:00", "14:00", 0)],
        "Spécial 4 fromages : le bleu d'Auvergne arrive au camion.",
        "Au camion cette semaine",
        "Pizzas au feu de bois jeudi et vendredi soir place de la "
        "Halle, samedi midi aussi. Menu enfant disponible.",
        specialite=Exploitant.Specialite.PIZZA,
        type_point=PointLivraison.Type.EMPLACEMENT),
    _ferme_spec(
        "demo.foodtruck.pizza.rennes", "Fornu Pizza Truck", A.FOODTRUCK,
        M.CONV, "35000", "Place Sainte-Anne (jeudi soirs)",
        "Rennes", 48.110, -1.678, "02 99 00 00 41",
        "Camion pizza rennais : pâtes maturées 48 h, produits bretons "
        "(andouille, emmental de Bretagne), menus et boissons locales.",
        Decimal("9.00"),
        [{"activite": A.FOODTRUCK, "limite": 12}],
        [("Emplacement Place Sainte-Anne", "Place Sainte-Anne",
          "Rennes", "35000", 48.109, -1.679),
         ("Marché des Lices", "Marché des Lices",
          "Rennes", "35000", 48.110, -1.672)],
        [(4, "18:00", "22:00", 0), (6, "10:00", "14:00", 1)],
        "La pizza aux andouilles de Guémené revient ce week-end.",
        "Fornu : pizzas du week-end",
        "Jeudi soir place Sainte-Anne, dimanche midi aux Lices. "
        "Pâtes maturées 48 h, cuisson 90 secondes.",
        specialite=Exploitant.Specialite.PIZZA,
        type_point=PointLivraison.Type.EMPLACEMENT),
    _ferme_spec(
        "demo.foodtruck.burger.castres", "Burger du Dadou", A.FOODTRUCK,
        M.RAISONNE, "81100", "Parking de la Rouère",
        "Castres", 43.605, 2.240, "05 63 00 00 42",
        "Burger gourmand castrais : viande du Tarn, frites maison "
        "coupées minute, cheddar affiné et burger végétarien.",
        Decimal("9.50"),
        [{"activite": A.FOODTRUCK, "limite": 12}],
        [("Emplacement Parking de la Rouère", "Parking de la Rouère",
          "Castres", "81100", 43.604, 2.241)],
        [(4, "18:00", "22:00", 0), (5, "18:00", "22:00", 0)],
        "Double burger : le cheddar affiné 6 mois est de retour.",
        "Burger du Dadou : cette semaine",
        "Jeudi et vendredi soir, parking de la Rouère. Frites maison "
        "et limonade artisanale du Tarn.",
        specialite=Exploitant.Specialite.BURGER,
        type_point=PointLivraison.Type.EMPLACEMENT),
    _ferme_spec(
        "demo.foodtruck.sandwichs.albi", "Le Camion Gourmand",
        A.FOODTRUCK, M.CONV, "81000", "Place du Vigan (midi)",
        "Albi", 43.930, 2.150, "05 63 00 00 43",
        "Sandwichs et plats du jour à Albi : pain de la boulangerie "
        "voisine, produits du marché, kebab agneau et poulet, wrap du "
        "moment et barquettes à emporter.",
        Decimal("9.00"),
        [{"activite": A.FOODTRUCK, "limite": 12}],
        [("Emplacement Place du Vigan", "Place du Vigan",
          "Albi", "81000", 43.929, 2.148)],
        [(3, "11:30", "14:30", 0), (6, "11:30", "15:00", 0),
         (5, "18:30", "22:00", 0)],
        "Plat du jour vendredi : confit de canard et pommes sarlaises.",
        "Le Camion Gourmand : menus de la semaine",
        "Sandwichs le midi en semaine et samedi, plat du jour en "
        "barquette, et le vendredi soir c'est kebab !",
        specialite=Exploitant.Specialite.SANDWICHS,
        type_point=PointLivraison.Type.EMPLACEMENT),
    _ferme_spec(
        "demo.foodtruck.rotisseur.toulouse", "Rôti-Route",
        A.FOODTRUCK, M.RAISONNE, "31000", "Allées Jean-Jaurès",
        "Toulouse", 43.595, 1.444, "05 61 00 00 44",
        "Rôtisseur ambulant : poulets fermiers des Landes rôtis sur "
        "place, pommes de terre au gras de volaille, gratins et "
        "plats familiaux à emporter.",
        Decimal("11.00"),
        [{"activite": A.FOODTRUCK, "limite": 12}],
        [("Emplacement Allées Jean-Jaurès", "Allées Jean-Jaurès",
          "Toulouse", "31000", 43.595, 1.440),
         ("Emplacement Capitole", "Place du Capitole",
          "Toulouse", "31000", 43.604, 1.444)],
        [(5, "17:00", "21:00", 0), (6, "10:30", "13:30", 1)],
        "Ce samedi au Capitole : poulets fermiers et gratin dauphinois.",
        "Rôti-Route : rôtisserie du week-end",
        "Vendredi soir allées Jean-Jaurès, samedi midi place du "
        "Capitole. Poulets fermiers des Landes, rôtis devant vous.",
        specialite=Exploitant.Specialite.ROTISSEUR,
        type_point=PointLivraison.Type.EMPLACEMENT),
    # ── Traiteurs 🥗 : boutique en centre-ville, plats du jour ─────
    _ferme_spec(
        "demo.traiteur.gaillac", "Saveurs du Girou", A.TRAITEUR,
        M.RAISONNE, "81600", "5 rue des Abattoirs",
        "Gaillac", 43.920, 1.894, "05 63 00 00 51",
        "Traiteur gaillacois : terrines et pâtés maison, plats "
        "cuisinés du terroir, salades composées et menus du jour à "
        "emporter ou à déguster sur place.",
        Decimal("8.00"),
        [{"activite": A.TRAITEUR, "limite": 12}],
        [("Boutique Saveurs du Girou", "5 rue des Abattoirs",
          "Gaillac", "81600", 43.900, 1.896),
         ("Marché couvert de Gaillac", "Place du marché couvert",
          "Gaillac", "81600", 43.900, 1.895)],
        [(2, "09:00", "18:00", 0), (6, "08:00", "12:30", 1)],
        "Terrine de lièvre : la fournée de samedi arrive en boutique.",
        "La semaine chez Saveurs du Girou",
        "Menus du jour en boutique du mardi au samedi, terrines et "
        "pâtés frais, plats cuisinés pour la famille.",
        type_point=PointLivraison.Type.BOUTIQUE),
    _ferme_spec(
        "demo.traiteur.lavaur", "La Table de Lavaur", A.TRAITEUR,
        M.CONV, "81500", "12 rue Alsace-Lorraine",
        "Lavaur", 43.700, 1.905, "05 63 00 00 52",
        "Traiteur lavaurais : plats cuisinés de saison, volailles du "
        "Tarn, gratins et desserts maison, formules midi et plateaux "
        "pour les familles.",
        Decimal("8.50"),
        [{"activite": A.TRAITEUR, "limite": 12}],
        [("Boutique La Table de Lavaur", "12 rue Alsace-Lorraine",
          "Lavaur", "81500", 43.700, 1.905)],
        [(2, "10:00", "19:00", 0), (4, "10:00", "19:00", 0),
         (6, "09:00", "13:00", 0)],
        "Cassoulet maison : cuite du mercredi, à réserver !",
        "Chez La Table de Lavaur",
        "Cassoulet du mercredi, poulet fermier du vendredi, et le "
        "plat du jour chaque midi en boutique.",
        type_point=PointLivraison.Type.BOUTIQUE),
    _ferme_spec(
        "demo.traiteur.montauban", "Montauban Gourmand", A.TRAITEUR,
        M.RAISONNE, "82000", "18 rue de la République",
        "Montauban", 43.999, 1.352, "05 63 00 00 53",
        "Traiteur montalbanais : spécialités du Sud-Ouest, confits, "
        "terrines et pâtés, menus du jour et buffets pour vos "
        "réceptions.",
        Decimal("8.00"),
        [{"activite": A.TRAITEUR, "limite": 12}],
        [("Boutique Montauban Gourmand", "18 rue de la République",
          "Montauban", "82000", 43.998, 1.350),
         ("Marché de Montauban", "Place du marché couvert",
          "Montauban", "82000", 44.015, 1.353)],
        [(2, "09:00", "18:30", 0), (6, "08:00", "13:00", 1),
         (6, "15:00", "19:00", 0)],
        "Confit de canard : le lot du mois est arrivé.",
        "La semaine chez Montauban Gourmand",
        "Menus du jour en boutique, confits et terrines du "
        "Sud-Ouest, plateaux repas et buffets sur commande.",
        type_point=PointLivraison.Type.BOUTIQUE),
    _ferme_spec(
        "demo.traiteur.brest", "Armor Traiteur", A.TRAITEUR,
        M.CONV, "29200", "24 rue de Siam",
        "Brest", 48.390, -4.486, "02 98 00 00 54",
        "Traiteur brestois : poissons et fruits de mer cuisinés, "
        "terrines marines, plats du jour et plateaux pour vos "
        "apéritifs et repas de famille.",
        Decimal("8.50"),
        [{"activite": A.TRAITEUR, "limite": 12}],
        [("Boutique Armor Traiteur", "24 rue de Siam",
          "Brest", "29200", 48.389, -4.487)],
        [(2, "09:30", "19:00", 0), (5, "09:30", "19:00", 0),
         (6, "09:30", "18:00", 0)],
        "Terrine de saumon aux algues : nouvelle fournée vendredi.",
        "Armor Traiteur : la semaine iodée",
        "Poissons cuisinés, terrines marines et plateaux de fruits "
        "de mer sur commande, boutique rue de Siam.",
        type_point=PointLivraison.Type.BOUTIQUE),
    _ferme_spec(
        "demo.traiteur.rennes", "Traiteur Rennais", A.TRAITEUR,
        M.RAISONNE, "35000", "8 rue Saint-Michel",
        "Rennes", 48.110, -1.680, "02 99 00 00 55",
        "Traiteur rennais : galettes garnies, plats bretons "
        "cuisinés, gratins et desserts maison, formules midi et "
        "buffets pour toutes les occasions.",
        Decimal("8.00"),
        [{"activite": A.TRAITEUR, "limite": 12}],
        [("Boutique Traiteur Rennais", "8 rue Saint-Michel",
          "Rennes", "35000", 48.110, -1.681),
         ("Marché des Lices", "Marché des Lices",
          "Rennes", "35000", 48.110, -1.672)],
        [(2, "09:00", "18:30", 0), (6, "08:30", "13:30", 1)],
        "Far aux pruneaux : le quatre-quarts du samedi.",
        "Traiteur Rennais : menus de la semaine",
        "Plats bretons cuisinés en boutique rue Saint-Michel, "
        "stand au marché des Lices le samedi matin.",
        type_point=PointLivraison.Type.BOUTIQUE),
    # ── MARCHÉ PARTAGÉ de Lavaur : quatre pros déclarent LE MÊME
    #    marché sous des noms DIFFÉRENTS et à quelques dizaines de
    #    mètres d'écart — le mode 🎪 Marchés & Boutiques doit les
    #    regrouper en UNE fiche (nom le plus probable, horaires
    #    fusionnés, liste des producteurs). ────────────────────────
    _ferme_spec(
        "demo.maraicher.giroussens", "Jardins du Girou", A.MARAICHER,
        M.AB, "81500", "Chemin de Lasbordes, lieu-dit Pourque",
        "Giroussens", 43.833, 1.698, "05 63 00 00 61",
        "Petit jardin maraîcher bio sur les coteaux du Girou : "
        "légumes de saison, salades et aromatiques, paniers "
        "hebdomadaires et stand du samedi à Lavaur.",
        Decimal("2.30"),
        [{"activite": A.MARAICHER, "limite": 16},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché couvert de Lavaur", "Place de la Halle",
          "Lavaur", "81500", 43.701, 1.901)],
        [(6, "08:00", "12:30", 0)],
        "Salades d'automne et radis noir du Girou.",
        "Paniers de la semaine aux Jardins du Girou",
        "Légumes des coteaux du Girou, stand au marché couvert "
        "de Lavaur le samedi matin. Miel de la ferme voisine en "
        "supplément."),
    _ferme_spec(
        "demo.apiculteur.lavaur", "Ruchers de l'Agout", A.APICULTEUR,
        M.AB, "81500", "Route de Toulouse, lieu-dit La Vauré",
        "Lavaur", 43.706, 1.921, "05 63 00 00 62",
        "Ruchers fixes entre Agout et Dadou : miels de fleurs, "
        "de châtaignier et de garrigue, pollens et cires, "
        "stand de la halle de Lavaur chaque samedi.",
        Decimal("4.50"),
        [{"activite": A.APICULTEUR, "limite": 10},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits",
          "limite": 3}],
        [("Halle de Lavaur", "Place de la Halle",
          "Lavaur", "81500", 43.699, 1.902)],
        [(6, "08:30", "12:30", 0)],
        "Miel de châtaignier de l'automne — berlingots disponibles.",
        "Miels de la semaine aux Ruchers de l'Agout",
        "Miel de châtaignier et pollen frais à la halle de "
        "Lavaur samedi matin. Pommes du verger voisin en "
        "supplément."),
    _ferme_spec(
        "demo.arboriculteur.lavaur", "Les Noyers de l'Agout",
        A.ARBORICULTEUR, M.RAISONNE, "81500",
        "Chemin des Noyeraies, lieu-dit Lagarrigue",
        "Lavaur", 43.692, 1.888, "05 63 00 00 63",
        "Noyeraie et verger au bord de l'Agout : noix fraîches, "
        "pommes, poires et jus pressé à la ferme, vente au "
        "marché hebdomadaire de Lavaur.",
        Decimal("2.80"),
        [{"activite": A.ARBORICULTEUR, "limite": 14},
         {"activite": A.APICULTEUR, "limite": 2}],
        [("Marché hebdo de Lavaur", "Esplanade de la Halle",
          "Lavaur", "81500", 43.698, 1.903)],
        [(6, "08:00", "12:00", 0)],
        "Noix fraîches de la première récolte — cassettes de 1 kg.",
        "Récolte de la semaine aux Noyers de l'Agout",
        "Noix fraîches, pommes et jus pressé au marché de "
        "Lavaur le samedi. Miel de tilleul des ruches du coteau."),
    _ferme_spec(
        "demo.eleveur.lavaur", "Élevage de l'Agout", A.ELEVEUR,
        M.PAYSAN, "81500", "Route de Sor, lieu-dit Engalès",
        "Lavaur", 43.710, 1.905, "05 63 00 00 64",
        "Élevage de veaux et volailles en agriculture paysanne "
        "dans la plaine de l'Agout : colis de viande, poulets "
        "fermiers et œufs, étal du samedi à Lavaur.",
        Decimal("5.50"),
        [{"activite": A.ELEVEUR, "limite": 12},
         {"activite": A.FROMAGER, "limite": 3}],
        [("Marché de la Halle", "Place de la Halle",
          "Lavaur", "81500", 43.702, 1.898)],
        [(6, "08:30", "12:30", 0)],
        "Poulets fermiers du lundi : à réserver avant vendredi soir.",
        "Viande de la semaine à l'Élevage de l'Agout",
        "Colis de veau, poulets fermiers et œufs à l'étal du "
        "marché de Lavaur. Tomme de la ferme voisine en "
        "supplément."),
    # ── MARCHÉ PARTAGÉ de Gaillac + BOUTIQUE PARTAGÉE de la gare :
    #    deux pros au marché couvert, deux pros à la boutique de la
    #    gare — deux clusters distincts à fusionner séparément. ────
    _ferme_spec(
        "demo.fromager.gaillac", "Tomme de Gaillac", A.FROMAGER,
        M.PAYSAN, "81600", "Route de Toulouse, lieu-dit La Rivalie",
        "Gaillac", 43.895, 1.885, "05 63 00 00 65",
        "Ferme laitière et fromagerie du Gaillacois : tomme de "
        "vache, fromages frais et yaourts au lait cru, stand du "
        "marché couvert de Gaillac.",
        Decimal("4.80"),
        [{"activite": A.FROMAGER, "limite": 12},
         {"activite": A.ELEVEUR, "categorie": "Œufs", "limite": 2}],
        [("Marché couvert de Gaillac", "Place du marché couvert",
          "Gaillac", "81600", 43.899, 1.896)],
        [(6, "08:30", "12:30", 0), (3, "16:30", "19:00", 0)],
        "Tomme de vache affinée 2 mois — le lot de novembre.",
        "Fromages de la semaine à la Tomme de Gaillac",
        "Tomme de vache et fromages frais au marché couvert de "
        "Gaillac, mercredi soir et samedi matin. Œufs de la "
        "ferme en supplément."),
    _ferme_spec(
        "demo.maraicher.gaillac", "Paniers du Tarn", A.MARAICHER,
        M.PERMA, "81600", "Chemin de Rieux, lieu-dit Les Pradets",
        "Gaillac", 43.905, 1.880, "05 63 00 00 66",
        "Maraîchage en permaculture sur les rives du Tarn : "
        "légumes de plein champ et sous serre, paniers "
        "hebdomadaires et stand du grand marché de Gaillac.",
        Decimal("2.40"),
        [{"activite": A.MARAICHER, "limite": 16},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits",
          "limite": 4}],
        [("Grand Marché de Gaillac", "Place du marché couvert",
          "Gaillac", "81600", 43.901, 1.894)],
        [(6, "08:00", "12:30", 0), (4, "17:00", "19:30", 0)],
        "Pleines saison des poireaux et premières mâches.",
        "Paniers de la semaine aux Paniers du Tarn",
        "Légumes de saison du Tarn au grand marché de Gaillac "
        "samedi matin, retrait des paniers jeudi soir aussi. "
        "Pommes du verger en supplément."),
    _ferme_spec(
        "demo.conserverie.gaillac", "Bocaux du Ségala", A.CONSERVERIE,
        M.AB, "81600", "Route de la Gare, lieu-dit Le Colombié",
        "Gaillac", 43.900, 1.883, "05 63 00 00 67",
        "Atelier de bocaux bio du Ségala : soupes, terrines, "
        "confitures et conserves de légumes, en vente à la "
        "boutique de la gare de Gaillac et au marché.",
        Decimal("4.30"),
        [{"activite": A.CONSERVERIE, "limite": 14}],
        [("Boutique de la Gare", "2 place de la Gare",
          "Gaillac", "81600", 43.898, 1.890),
         ("Marché couvert de Gaillac", "Place du marché couvert",
          "Gaillac", "81600", 43.900, 1.895)],
        [(3, "15:00", "19:00", 0), (6, "08:30", "12:30", 1)],
        "Velouté de potimarron et confiture de coing du moment.",
        "Bocaux de la semaine aux Bocaux du Ségala",
        "Soupes, terrines et confitures à la boutique de la "
        "gare de Gaillac ; étal au marché couvert le samedi."),
    _ferme_spec(
        "demo.miellerie.gaillac", "Ruchers de la Gare", A.APICULTEUR,
        M.AB, "81600", "Avenue de la Gare, lieu-dit Las Crozes",
        "Gaillac", 43.896, 1.885, "05 63 00 00 68",
        "Miellerie de la gare : miels toutes fleurs, gelée royale "
        "et cires façonnées, vente en boutique à la gare de "
        "Gaillac et au marché couvert.",
        Decimal("4.60"),
        [{"activite": A.APICULTEUR, "limite": 10},
         {"activite": A.ARBORICULTEUR, "categorie": "Fruits",
          "limite": 3}],
        [("Boutique gare de Gaillac", "4 place de la Gare",
          "Gaillac", "81600", 43.8975, 1.8905),
         ("Marché de Gaillac (halle)", "Place du marché couvert",
          "Gaillac", "81600", 43.9005, 1.8955)],
        [(2, "14:00", "18:30", 0), (6, "09:00", "12:30", 1)],
        "Gelée royale fraîche de la semaine — pots de 30 g.",
        "Miels de la semaine aux Ruchers de la Gare",
        "Miels toutes fleurs et gelée royale à la boutique de "
        "la gare ; pommes et poires du Gaillacois en supplément."),
    # ── Restauration : un traiteur de plus (boutique Castres) et un
    #    foodtruck de plus (emplacements de Gaillac) — les libellés
    #    « 📜 Cartes » du menu Publications se testent dessus. ──────
    _ferme_spec(
        "demo.traiteur.castres", "Le Buffet Castrais", A.TRAITEUR,
        M.RAISONNE, "81100", "6 rue de la Mairie",
        "Castres", 43.606, 2.241, "05 63 00 00 69",
        "Traiteur castrais : volailles du Tarn et farcis de "
        "saison, terrines, gratins et menus du jour à emporter "
        "en boutique au cœur de Castres.",
        Decimal("8.20"),
        [{"activite": A.TRAITEUR, "limite": 12}],
        [("Boutique Le Buffet Castrais", "6 rue de la Mairie",
          "Castres", "81100", 43.6055, 2.2405)],
        [(2, "09:30", "18:30", 0), (5, "09:30", "18:30", 0),
         (6, "09:00", "13:00", 0)],
        "Farcis de saison : courgons du jardin et chair à saucisse.",
        "Chez Le Buffet Castrais",
        "Menus du jour en boutique, volailles farcies du week-end "
        "et terrines maison, à emporter rue de la Mairie.",
        type_point=PointLivraison.Type.BOUTIQUE),
    _ferme_spec(
        "demo.foodtruck.crepes.gaillac", "Crêpes du Vieux Gaillac",
        A.FOODTRUCK, M.CONV, "81600",
        "Place de la Libération (soirs de marché)",
        "Gaillac", 43.899, 1.893, "05 63 00 00 70",
        "Camion crêpes et galettes de sarrasin du vieux "
        "Gaillac : pâte du moment, cidre du coin et desserts "
        "de la ferme, place de la Libération.",
        Decimal("7.50"),
        [{"activite": A.FOODTRUCK, "limite": 12}],
        [("Emplacement place de la Libération",
          "Place de la Libération",
          "Gaillac", "81600", 43.899, 1.893)],
        [(5, "18:00", "22:30", 0), (6, "11:00", "14:00", 0)],
        "Galette complète au bleu de la tomme de Gaillac.",
        "Au camion cette semaine",
        "Galettes de sarrasin et crêpes maison vendredi soir et "
        "samedi midi place de la Libération, cidre doux du coin.",
        type_point=PointLivraison.Type.EMPLACEMENT),
]

CLIENTS = [
    {"utilisateur": "demo.cliente", "prenom": "Marie", "nom": "Dupont",
     "email": "marie.dupont@example.fr", "tel": "06 12 34 56 78",
     "ville": "Gaillac", "cp": "81600"},
    {"utilisateur": "demo.client", "prenom": "Paul", "nom": "Martin",
     "email": "paul.martin@example.fr", "tel": "06 98 76 54 32",
     "ville": "Castres", "cp": "81100"},
    # Compte client « sans engagement » : à communiquer aux personnes
    # qui veulent essayer le portail sans créer leur propre compte.
    {"utilisateur": "demo.public", "prenom": "Camille", "nom": "Public",
     "email": "camille.public@example.fr", "tel": "06 11 22 33 44",
     "ville": "Lavaur", "cp": "81500"},
]


class Command(BaseCommand):
    help = ("Crée des données de démonstration fictives (Tarn et "
            "départements limitrophes, Bretagne, Loire, Corse, Réunion, "
            "Martinique ; clients, commandes et paniers). Idempotent ; "
            "--purge efface tout compte de démo, même d'un jeu plus "
            "ancien.")

    def add_arguments(self, parser):
        parser.add_argument("--purge", action="store_true",
                            help="Supprime les comptes et données de démo")
        parser.add_argument(
            "--reset-commandes", action="store_true",
            help=("Efface TOUTES les commandes et paniers de la base "
                  "(comptes réels inclus) puis régénère les commandes "
                  "et paniers du jeu de démo pour toutes les fermes. "
                  "Usage ponctuel uniquement."))
        parser.add_argument(
            "--reset-commandes-demo", action="store_true",
            help=("Efface UNIQUEMENT les commandes et paniers des "
                  "fermes de démonstration (les commandes réelles "
                  "sont conservées) puis régénère le jeu de démo."))

    def _lundi(self):
        today = timezone.localdate()
        return today - datetime.timedelta(days=today.weekday())

    def _ferme(self, spec, recree_commandes=False):
        """Exploitation de démo : compte, fiche, catalogue, points,
        créneaux, récolte de la semaine, bulletin."""
        if User.objects.filter(username=spec["utilisateur"]).exists():
            # Compte déjà présent : on s'assure au minimum qu'il porte
            # le badge démo, puis on passe (idempotence) — sauf avec
            # --reset-commandes, où l'on récupère catalogue et points
            # pour régénérer les commandes et paniers de démo.
            Exploitant.objects.filter(
                user__username=spec["utilisateur"]
            ).update(est_demo=True)
            if not recree_commandes:
                self.stdout.write(self.style.NOTICE(
                    f"Compte {spec['utilisateur']} déjà présent : ferme "
                    "ignorée (badge démo réappliqué)."))
                return None
            exploitant = Exploitant.objects.get(
                user__username=spec["utilisateur"])
            produits = list(exploitant.produits.filter(actif=True))
            points = list(exploitant.points_livraison.all())
            if not produits or not points:
                self.stdout.write(self.style.NOTICE(
                    f"Compte {spec['utilisateur']} : catalogue ou "
                    "point de livraison vide, commandes non régénérées."))
                return None
            self.stdout.write(self.style.NOTICE(
                f"Compte {spec['utilisateur']} déjà présent : ferme "
                "conservée, commandes de démo régénérées."))
            return exploitant, produits, points
        user = User.objects.create_user(
            username=spec["utilisateur"], password=MOT_DE_PASSE_DEMO,
            first_name="Famille", last_name=spec["ferme"],
            email=spec["utilisateur"] + "@example.fr")
        exploitant = Exploitant.objects.create(
            user=user, nom_ferme=spec["ferme"], activite=spec["activite"],
            mode_production=spec["mode"],
            specialite=spec.get("specialite") or "",
            siret=_siret_valide(spec["siret_prefixe"]),
            description=spec["description"], adresse=spec["adresse"],
            ville=spec["ville"], code_postal=spec["cp"],
            telephone=spec["tel"], latitude=spec["lat"],
            longitude=spec["lon"], visible=True, est_demo=True)

        # Catalogue MIXTE multi-catégories : on pioche dans les
        # catalogues types de plusieurs activités (la catégorie type
        # de chaque produit devient une catégorie du producteur) ;
        # les prix progressent au sein de chaque catégorie.
        produits = []
        slugs_vus = set()
        for source in spec["mix"]:
            qs = ProduitStandard.objects.filter(
                activite=source["activite"])
            if source.get("categorie"):
                qs = qs.filter(categorie=source["categorie"])
            for std in qs[:source["limite"]]:
                if Produit.objects.filter(
                        exploitant=exploitant,
                        origine_standard=std).exists():
                    continue
                # Les catalogues croisés peuvent contenir des produits
                # homonymes (ex. « Fraise » en maraîcher et en fruits) :
                # le slug du produit étant dérivé du nom, on ne garde
                # que le premier pour éviter la collision (exploitant,
                # slug).
                slug_produit = slugify(std.nom)
                if slug_produit in slugs_vus:
                    continue
                slugs_vus.add(slug_produit)
                cat, _cree = Categorie.objects.get_or_create(
                    exploitant=exploitant, nom=std.categorie)
                if _cree:
                    cat.position = exploitant.categories.count()
                    cat.save()
                rang = (Produit.objects
                        .filter(exploitant=exploitant, categorie=cat)
                        .count())
                produit = Produit.objects.create(
                    exploitant=exploitant, nom=std.nom, categorie=cat,
                    unite_vente=std.unite_vente,
                    attributs={"saisons": std.saisons},
                    origine_standard=std,
                    prix=spec["prix_base"] + Decimal(rang) * Decimal("0.50"),
                    actif=True)
                produits.append(produit)

        # Points de livraison + créneaux. Le type est déduit du libellé
        # quand la saisie est explicite : les points « Marché … » et
        # « Boutique … » alimentent le mode Marchés & Boutiques de la
        # recherche (le type explicite de la spécification prime).
        points = []
        for nom, adresse, ville, cp, lat, lon in spec["points"]:
            points.append(PointLivraison.objects.create(
                exploitant=exploitant, nom=nom, adresse=adresse,
                ville=ville, code_postal=cp, latitude=lat, longitude=lon,
                type_point=(spec.get("type_point") or _type_deduit(nom))))
        for jour, debut, fin, idx_point in spec["creneaux"]:
            CreneauLivraison.objects.create(
                exploitant=exploitant, point_livraison=points[idx_point],
                jour=jour,
                heure_debut=datetime.time.fromisoformat(debut),
                heure_fin=datetime.time.fromisoformat(fin),
                frequence=CreneauLivraison.Frequence.HEBDO)

        # Récolte de la semaine en cours (publiée) + une semaine à venir
        lundi = self._lundi()
        for decal, publiee in ((0, True), (7, True)):
            semaine = SemaineRecolte.objects.create(
                exploitant=exploitant,
                lundi=lundi + datetime.timedelta(days=decal),
                note=(spec["note_semaine"] if decal == 0 else ""),
                publiee=publiee)
            if decal == 0:
                for i, produit in enumerate(produits[:6]):
                    LigneRecolte.objects.create(
                        recolte=semaine, produit=produit,
                        quantite_estimee=Decimal(10 + 2 * i),
                        prix_unitaire=produit.prix)
        Bulletin.objects.create(
            exploitant=exploitant, objet=spec["bulletin"][0],
            corps=spec["bulletin"][1])
        self.stdout.write(self.style.SUCCESS(
            f"🌾 {exploitant.nom_ferme} créée ({spec['ville']}, compte "
            f"{spec['utilisateur']}, mot de passe {MOT_DE_PASSE_DEMO}) : "
            f"{len(produits)} produits en "
            f"{exploitant.categories.count()} catégories, "
            f"{len(points)} point(s)."))
        return exploitant, produits, points

    def _clients(self):
        clients = []
        for spec in CLIENTS:
            if User.objects.filter(username=spec["utilisateur"]).exists():
                user = User.objects.filter(
                    username=spec["utilisateur"]).first()
            else:
                user = User.objects.create_user(
                    username=spec["utilisateur"], password=MOT_DE_PASSE_DEMO,
                    first_name=spec["prenom"], last_name=spec["nom"],
                    email=spec["email"])
                self.stdout.write(self.style.SUCCESS(
                    f"👤 Client {spec['utilisateur']} créé "
                    f"(mot de passe {MOT_DE_PASSE_DEMO})."))
            ProfilClient.objects.get_or_create(
                user=user,
                defaults={"telephone": spec["tel"], "ville": spec["ville"],
                          "code_postal": spec["cp"]})
            clients.append(user)
        return clients

    def _commande(self, exploitant, produits, point, client, lignes,
                  statut, jours, panier_statut=None, quantite_livree=None):
        """Commande (+ éventuellement son panier numéroté) de démo."""
        date_livraison = self._lundi() + datetime.timedelta(days=jours)
        nom = (client.get_full_name() if client else "Client anonyme")
        commande = Commande.objects.create(
            exploitant=exploitant, client=client, nom_client=nom,
            email_client=(client.email if client else ""),
            telephone_client=("" if client else "06 11 22 33 44"),
            point_livraison=point, date_livraison=date_livraison,
            statut=statut,
            validee_le=(timezone.now() if statut != Commande.Statut.NOUVELLE
                        else None),
            note="")
        total = Decimal("0")
        for produit, quantite in lignes:
            LigneCommande.objects.create(
                commande=commande, produit=produit, quantite=quantite,
                prix_unitaire=produit.prix)
            total += quantite * produit.prix
        commande.total = total
        commande.save()
        if panier_statut:
            panier = Panier.objects.create(
                exploitant=exploitant, client=client, nom_client=nom,
                email_client=(client.email if client else ""),
                telephone_client=(
                    (client.profil_client.telephone
                     if hasattr(client, "profil_client") else "")
                    if client else "06 11 22 33 44"),
                numero=Panier.prochain_numero(exploitant, date_livraison,
                                               point),
                date_livraison=date_livraison, point_livraison=point,
                commande=commande, statut=panier_statut)
            total_panier = Decimal("0")
            for produit, quantite in lignes:
                q = quantite
                if quantite_livree is not None:
                    q = quantite_livree.get(produit.pk, quantite)
                if q <= 0:
                    continue
                LignePanier.objects.create(
                    panier=panier, produit=produit, quantite=q,
                    prix_unitaire=produit.prix)
                total_panier += q * produit.prix
            panier.total = total_panier
            panier.save()
        return commande

    def _cartes_demo(self):
        """Cartes / boutiques de DÉMONSTRATION : une carte ACTIVE par
        traiteur et foodtruck (« Carte du moment » — sections Entrées,
        Plats, Desserts) et par producteur en mode boutique (fromager,
        apiculteur, conserverie, micro-brasseur — « En boutique en ce
        moment »). Les lignes reprennent les produits actifs de la
        ferme ; une carte déjà active est conservée telle quelle."""
        concernees = ("FOODTRUCK", "TRAITEUR", "FROMAGER", "APICULTEUR",
                      "CONSERVERIE", "MICRO_BRASSEUR")
        nb_cartes = 0
        fermes = Exploitant.objects.filter(
            est_demo=True, activite__in=concernees)
        for ferme in fermes:
            if ferme.cartes.filter(
                    statut=Carte.Statut.ACTIVE).exists():
                continue
            restauration = ferme.activite in ("FOODTRUCK", "TRAITEUR")
            carte = Carte.objects.create(
                exploitant=ferme,
                nom=("Carte du moment" if restauration
                     else "En boutique en ce moment"),
                statut=Carte.Statut.ACTIVE)
            produits = list(ferme.produits.filter(actif=True)
                            .select_related("categorie")
                            .order_by("categorie__position", "nom")[:8])
            for n, produit in enumerate(produits):
                section = ""
                if restauration:
                    section = ("Entrées" if n < 2
                               else "Plats" if n < 6 else "Desserts")
                elif produit.categorie:
                    section = produit.categorie.nom
                LigneCarte.objects.create(
                    carte=carte, produit=produit, section=section,
                    unite_vente=produit.unite_vente, prix=None,
                    position=n + 1)
            nb_cartes += 1
        if nb_cartes:
            self.stdout.write(self.style.SUCCESS(
                "Cartes de démo créées : " + str(nb_cartes)
                + " carte(s) active(s) — traiteurs, foodtrucks et "
                "boutiques de producteurs."))

    def handle(self, *args, **options):
        if options["purge"]:
            # Purge LARGE : tout compte « demo.* », toute exploitation
            # marquée « démo » (même créée par un jeu plus ancien
            # aujourd'hui disparu de la liste) et les fermes du jeu
            # courant (au cas où un compte aurait été renommé).
            connus = ([s["utilisateur"] for s in FERMES]
                      + [s["utilisateur"] for s in CLIENTS])
            users = (User.objects.filter(username__startswith="demo.")
                     | User.objects.filter(exploitant__est_demo=True)
                     | User.objects.filter(
                         exploitant__nom_ferme__in=[
                             s["ferme"] for s in FERMES])
                     ).distinct()
            # Les lignes de commandes et paniers de démo portent des
            # clés étrangères PROTÉGÉES (produits, points) : sans cet
            # effacement préalable, la suppression du compte échoue
            # (ProtectedError) et les fermes sont conservées avec leurs
            # anciens points — les nouveaux types MARCHE/BOUTIQUE ne
            # sont alors jamais appliqués au jeu de démo.
            cibles = list(users)
            ids = [u.pk for u in cibles]
            Panier.objects.filter(exploitant__user_id__in=ids).delete()
            Commande.objects.filter(exploitant__user_id__in=ids).delete()
            n, purges = 0, []
            for user in cibles:
                try:
                    n += user.delete()[0]
                    purges.append(user.username)
                except Exception as erreur:  # PROTECT éventuel
                    self.stdout.write(self.style.ERROR(
                        f"Impossible de supprimer {user.username} "
                        f"({erreur})."))
            if connus and not purges:
                self.stdout.write(self.style.NOTICE(
                    "Aucun compte de démo trouvé à purger."))
            elif purges:
                self.stdout.write(self.style.SUCCESS(
                    f"Comptes de démo supprimés : "
                    f"{', '.join(sorted(purges))} ({n} objet(s))."))
            # Si la purge a vidé TOUTES les commandes et paniers (base
            # 100 % démo), les index repartent de 1 au repeuplement.
            if not Panier.objects.exists() and not Commande.objects.exists():
                reinitialiser_sequences()
                self.stdout.write(self.style.SUCCESS(
                    "Base sans commande ni panier : index réinitialisés."))
            return

        reset_total = bool(options.get("reset_commandes"))
        reset_demo = bool(options.get("reset_commandes_demo"))
        recree = reset_total or reset_demo
        if reset_total:
            # Nettoyage PONCTUEL : on efface TOUTES les commandes et
            # paniers de la base (comptes réels inclus), puis le
            # peuplement ci-dessous régénère les commandes du jeu de
            # démo pour chaque ferme. Panier d'abord (FK SET_NULL),
            # commandes ensuite.
            nb_paniers = Panier.objects.count()
            nb_commandes = Commande.objects.count()
            Panier.objects.all().delete()
            Commande.objects.all().delete()
            reinitialiser_sequences()
            self.stdout.write(self.style.SUCCESS(
                f"Commandes et paniers effacés : {nb_commandes} "
                f"commande(s), {nb_paniers} panier(s) supprimé(s), "
                "index réinitialisés."))
        elif reset_demo:
            # Nettoyage courant : seules les commandes et paniers des
            # fermes de DÉMONSTRATION sont effacés — les commandes
            # réelles des vrais comptes sont conservées.
            nb_paniers = Panier.objects.filter(
                exploitant__est_demo=True).count()
            nb_commandes = Commande.objects.filter(
                exploitant__est_demo=True).count()
            Panier.objects.filter(exploitant__est_demo=True).delete()
            Commande.objects.filter(exploitant__est_demo=True).delete()
            reinitialiser_sequences()
            self.stdout.write(self.style.SUCCESS(
                f"Commandes et paniers de DÉMO effacés : {nb_commandes} "
                f"commande(s), {nb_paniers} panier(s) — les commandes "
                "réelles sont conservées, index réinitialisés."))

        # Les catalogues types par activité doivent être en base avant
        # de piocher les produits : foodtrucks et traiteurs reposent
        # entièrement dessus (évite les catalogues erronés).
        call_command("charger_catalogues_activites")

        clients = self._clients()
        for spec in FERMES:
            resultat = self._ferme(spec, recree_commandes=recree)
            if resultat is None:
                continue
            exploitant, produits, points = resultat
            # Garde-fou : les catalogues types comptent une dizaine de
            # produits, mais on reste robuste si un est plus court.
            def pick(i):
                return produits[i % len(produits)]
            deux = [(pick(0), Decimal("2")),
                    (pick(2), Decimal("1"))]
            trois = [(pick(1), Decimal("3")),
                     (pick(3), Decimal("2")),
                     (pick(4), Decimal("1"))]
            # 1. Commande à valider (portail, cliente avec compte)
            self._commande(exploitant, produits, points[0], clients[0],
                            deux, Commande.Statut.NOUVELLE, jours=6)
            # 2. Commande validée → panier en préparation
            self._commande(exploitant, produits, points[0], clients[1],
                           trois, Commande.Statut.VALIDEE, jours=6,
                           panier_statut=Panier.Statut.PREPARATION)
            # 3. Panier prêt (commande sans compte, au marché)
            self._commande(exploitant, produits, points[-1], None,
                           deux, Commande.Statut.VALIDEE, jours=5,
                           panier_statut=Panier.Statut.PRET)
            # 4. Panier livré (lecture seule) avec un ajustement
            ajuste = {pick(1).pk: Decimal("2")}  # 3 kg souhaités → 2 livrés
            self._commande(exploitant, produits, points[-1], clients[0],
                           trois, Commande.Statut.VALIDEE, jours=-2,
                           panier_statut=Panier.Statut.LIVRE,
                           quantite_livree=ajuste)
            # 5. Panier PRÊT pour le compte client d'essai (demo.public)
            #    → permet de tester « Valider la réception ».
            if len(clients) > 2:
                self._commande(exploitant, produits, points[0], clients[2],
                               deux, Commande.Statut.VALIDEE, jours=6,
                               panier_statut=Panier.Statut.PRET)
            # 6. Commande ANNULEE PAR LE CLIENT avec motif : teste le
            #    filtre pro « ❌ Annulées client » et l'affichage du
            #    motif des deux côtés.
            annul_client = self._commande(
                exploitant, produits, points[0], clients[1],
                deux, Commande.Statut.ANNULEE, jours=4)
            annul_client.annulee_par = Commande.AnnulationPar.CLIENT
            annul_client.motif_annulation = ("Finalement absent ce "
                                             "jour-là, désolé !")
            annul_client.save()
            # 7. Panier ANNULE PAR LE PRODUCTEUR : la commande repasse
            #    « Annulée (producteur) » et le motif du panier est
            #    visible côté client — teste le filtre « 🚫 Annulées
            #    par moi » et le bloc motif côté « Mes commandes ».
            annul_pro = self._commande(
                exploitant, produits, points[-1], clients[0],
                deux, Commande.Statut.VALIDEE, jours=3,
                panier_statut=Panier.Statut.PREPARATION)
            panier_pro = Panier.objects.filter(
                commande=annul_pro).first()
            if panier_pro is not None:
                panier_pro.statut = Panier.Statut.ANNULE
                panier_pro.motif_annulation = ("Récolte insuffisante "
                                               "cette semaine, désolé.")
                panier_pro.save()
            annul_pro.statut = Commande.Statut.ANNULEE
            annul_pro.annulee_par = Commande.AnnulationPar.PRODUCTEUR
            annul_pro.save()
        self._cartes_demo()

        self.stdout.write(self.style.SUCCESS(
            f"Démonstration prête : {len(FERMES)} fermes fictives "
            "(Tarn et départements limitrophes, Bretagne, Loire, Corse, "
            "Réunion, Martinique + 2 micro-brasseries et 2 conserveries "
            "en boutique, 5 foodtrucks et 5 traiteurs) avec "
            f"{len(CLIENTS)} clients, commandes à valider, paniers en "
            "préparation, prêts et livrés (lecture seule)."))
        self.stdout.write("Connexion producteur : demo.maraicher, "
                          "demo.vergers, demo.fromager, etc. — mot de "
                          "passe " + MOT_DE_PASSE_DEMO)
