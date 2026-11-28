"""Géocodage côté serveur (Nominatim / OpenStreetMap).

La carte interactive des points de livraison couvre déjà le geste
précis (clic, déplacement de marqueur, adresse déduite) ; ce module
est le FILET DE SÉCURITÉ du parcours purement textuel : un point
créé ou modifié par son adresse seule (sans passage par la carte)
reçoit une position automatique, sans rien demander au gérant.

Règles d'usage Nominatim (openstreetmap.org/copyright) : un appel
par sauvegarde, jamais de rafale ; User-Agent identifiable ;
timeout court pour ne jamais retarder l'enregistrement ; un échec
(réseau, zéro résultat) n'est jamais bloquant — le point reste
simplement « non localisé » et l'UI propose de le placer à la main.
"""
import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

URL_RECHERCHE = "https://nominatim.openstreetmap.org/search"
TIMEOUT_DEFAUT = 4  # secondes : au-delà, on rend la main au gérant


def geocoder_adresse(adresse="", ville="", code_postal="",
                     timeout=TIMEOUT_DEFAUT):
    """Position (latitude, longitude) d'une adresse française, ou
    None. Ne lève JAMAIS : réseau coupé, réponse illisible ou
    zéro résultat renvoient None silencieusement (log info)."""
    morceaux = [m.strip() for m in (adresse, code_postal, ville)
                if m and m.strip()]
    if not morceaux:
        return None
    parametres = urllib.parse.urlencode({
        "q": ", ".join(morceaux),
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "fr",
        "addressdetails": 0,
    })
    requete = urllib.request.Request(
        URL_RECHERCHE + "?" + parametres,
        headers={"User-Agent": getattr(
            settings, "NOMINATIM_USER_AGENT",
            "MonPetitProducteurLocal (+https://mppl.cartotrac.fr)")})
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8"))
        premier = donnees[0] if donnees else {}
        lat = float(premier.get("lat") or 0)
        lon = float(premier.get("lon") or 0)
        if lat and lon:
            return lat, lon
        return None
    except Exception as erreur:  # réseau, timeout, JSON, DNS…
        logger.info("Géocodage Nominatim indisponible pour %s : %s",
                    ", ".join(morceaux), erreur)
        return None
