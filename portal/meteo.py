"""Météo synthétique pour le dashboard (Open-Meteo, zéro dépendance).

Requêtes HTTP via urllib (stdlib uniquement), cache mémoire 30 min par
process serveur. Échec réseau : retourne la dernière valeur connue sinon
None — le dashboard s'affiche simplement sans le hero météo.
"""

import json
import time
import urllib.parse
import urllib.request

DUREE_CACHE = 1800          # secondes
DUREE_CACHE_GEO = 86400     # géocodage : 24 h

CODES_METEO = {
    0: ("☀️", "Ciel dégagé"),
    1: ("🌤", "Plutôt dégagé"),
    2: ("⛅", "Partiellement nuageux"),
    3: ("☁️", "Couvert"),
    45: ("🌫", "Brouillard"),
    48: ("🌫", "Brouillard givrant"),
    51: ("🌦", "Bruine légère"),
    53: ("🌦", "Bruine"),
    55: ("🌦", "Bruine forte"),
    61: ("🌧", "Pluie légère"),
    63: ("🌧", "Pluie"),
    65: ("🌧", "Pluie forte"),
    66: ("🌧", "Pluie verglaçante"),
    67: ("🌧", "Pluie verglaçante forte"),
    71: ("🌨", "Neige légère"),
    73: ("🌨", "Neige"),
    75: ("❄️", "Neige forte"),
    77: ("❄️", "Grains de neige"),
    80: ("🌦", "Averses légères"),
    81: ("🌧", "Averses"),
    82: ("⛈", "Averses fortes"),
    85: ("🌨", "Averses de neige"),
    86: ("🌨", "Averses de neige fortes"),
    95: ("⛈", "Orage"),
    96: ("⛈", "Orage avec grêle"),
    99: ("⛈", "Orage violent avec grêle"),
}

_cache = {}


def _charger(url, delai=4.0):
    with urllib.request.urlopen(url, timeout=delai) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def _coordonnees(exploitant):
    """Latitude/longitude de l'exploitation : coordonnées saisies si
    présentes, sinon géocodage de la ville (France)."""
    if exploitant.latitude is not None and exploitant.longitude is not None:
        return round(exploitant.latitude, 4), round(exploitant.longitude, 4)
    ville = (exploitant.ville or "").strip()
    if not ville:
        return None
    maintenant = time.time()
    cle = ("geo", ville.lower())
    if cle in _cache and maintenant - _cache[cle][0] < DUREE_CACHE_GEO:
        return _cache[cle][1]
    coords = None
    try:
        parametres = urllib.parse.urlencode(
            {"name": ville, "count": 1, "language": "fr", "country": "FR"})
        donnees = _charger(
            "https://geocoding-api.open-meteo.com/v1/search?" + parametres)
        resultats = donnees.get("results") or []
        if resultats:
            r = resultats[0]
            coords = (round(r["latitude"], 4), round(r["longitude"], 4))
    except Exception:
        coords = None
    _cache[cle] = (maintenant, coords)
    return coords


def meteo_synthese(exploitant):
    """Météo en direct à l'exploitation : température, min/max du jour,
    vent, pluie. None si indisponible (pas de localisation / réseau)."""
    coords = _coordonnees(exploitant)
    if not coords:
        return None
    latitude, longitude = coords
    maintenant = time.time()
    cle = ("meteo", latitude, longitude)
    if cle in _cache and maintenant - _cache[cle][0] < DUREE_CACHE:
        return _cache[cle][1]
    parametres = urllib.parse.urlencode({
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto"})
    try:
        donnees = _charger(
            "https://api.open-meteo.com/v1/forecast?" + parametres)
    except Exception:
        return _cache[cle][1] if cle in _cache else None
    actuel = donnees.get("current") or {}
    jour = donnees.get("daily") or {}
    if "weather_code" not in actuel or not jour.get("temperature_2m_max"):
        return _cache[cle][1] if cle in _cache else None
    emoji, libelle = CODES_METEO.get(actuel["weather_code"], ("🌡", "Météo"))
    synthese = {
        "emoji": emoji,
        "libelle": libelle,
        "temperature": round(actuel.get("temperature_2m") or 0),
        "max": round(jour["temperature_2m_max"][0]),
        "min": round(jour["temperature_2m_min"][0]),
        "vent": round(actuel.get("wind_speed_10m") or 0),
        "pluie": jour["precipitation_sum"][0] or 0,
        "lieu": exploitant.ville or exploitant.nom_espace,
    }
    _cache[cle] = (maintenant, synthese)
    return synthese
