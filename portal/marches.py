"""Détection des MARCHÉS et BOUTIQUES de producteurs : agrégation
des points déclarés par les pros (type Marché ou Boutique) situés à
moins de ~250 m les uns des autres. Un même marché déclaré par
plusieurs producteurs devient UNE entité, avec :

- le nom le plus probable (d'après les saisies des pros) ;
- la position moyenne du groupe de points ;
- les créneaux horaires FUSIONNÉS par jour (chevauchements et
  doublons absorbés : 10h–12h + 11h30–13h → 10h–13h) ;
- la liste des producteurs rattachés et leurs créneaux à eux.

Marchés et boutiques restent VIRTUELS : rien n'est stocké en base,
tout est recalculé à la demande (mode 🎪 de la page de recherche,
fiche publique /marche/<slug>/). Le slug intègre l'empreinte des
points agrégés : il est stable tant que les données ne changent pas.
"""

import hashlib
import math
from collections import Counter, defaultdict

from django.urls import reverse
from django.utils.text import slugify

from .models import CreneauLivraison, Exploitant, PointLivraison

# Rayon d'agrégation : deux points saisis à moins de BUFFER_METRES
# l'un de l'autre décrivent le même marché / la même boutique.
BUFFER_METRES = 250

JOURS = {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi",
         5: "Vendredi", 6: "Samedi", 7: "Dimanche"}

# Les traiteurs et foodtrucks ne sont PAS des producteurs : leurs
# boutiques et emplacements relèvent du mode restauration, pas du
# mode marchés de producteurs.
ACTIVITES_RESTAURATION = (Exploitant.Activite.FOODTRUCK,
                          Exploitant.Activite.TRAITEUR)


def _distance_metres(lat1, lon1, lat2, lon2):
    """Distance au sol en mètres (approximation locale, largement
    suffisante pour un rayon d'agrégation de quelques centaines de
    mètres)."""
    lat_moy = math.radians((lat1 + lat2) / 2)
    return math.hypot((lat2 - lat1) * 111_320.0,
                      (lon2 - lon1) * 111_320.0 * math.cos(lat_moy))


def _fusion_intervalles(intervalles):
    """Fusionne les créneaux d'un même jour : tri par début puis
    absorption des chevauchements (10:00–12:00 + 11:30–13:00 →
    10:00–13:00) — les doublons exacts disparaissent au passage."""
    fusionnes = []
    for debut, fin in sorted(intervalles):
        if fin <= debut:
            continue
        if fusionnes and debut <= fusionnes[-1][1]:
            fusionnes[-1][1] = max(fusionnes[-1][1], fin)
        else:
            fusionnes.append([debut, fin])
    return fusionnes


def _nom_probable(noms):
    """Nom le plus probable d'après les saisies pros : le plus
    fréquent ; égalité → un libellé explicite (contient « marché »,
    « halle » ou « boutique »), puis le plus court, puis
    alphabétique."""
    comptes = Counter(noms)

    def cle(nom):
        bas = nom.lower()
        return (-comptes[nom],
                0 if any(mot in bas for mot in
                         ("marché", "marche", "halle", "boutique"))
                else 1,
                len(nom), nom)

    return sorted(comptes, key=cle)[0]


def _plus_frequent(valeurs):
    comptes = Counter(v for v in valeurs if v)
    return comptes.most_common(1)[0][0] if comptes else ""


def _clusters(points):
    """Regroupe les points d'un même type par proximité (union
    simple : chaque point rejoint le premier cluster dont un membre
    est à moins de 250 m)."""
    clusters = []
    for p in sorted(points, key=lambda x: (x.latitude, x.longitude)):
        for cluster in clusters:
            voisin = any(
                _distance_metres(p.latitude, p.longitude,
                                 q.latitude, q.longitude) <= BUFFER_METRES
                for q in cluster)
            if voisin:
                cluster.append(p)
                break
        else:
            clusters.append([p])
    return clusters


def _fabrique_marche(type_point, cluster, creneaux_par_point):
    """Construit l'entité (marché ou boutique) d'un cluster de
    points : nom probable, position moyenne, horaires fusionnés et
    producteurs rattachés (chacun avec SES créneaux sur place)."""
    nom = _nom_probable([p.nom for p in cluster])
    ville = _plus_frequent([p.ville for p in cluster])
    code_postal = _plus_frequent([p.code_postal for p in cluster])
    adresse = _plus_frequent([p.adresse for p in cluster])
    latitude = sum(p.latitude for p in cluster) / len(cluster)
    longitude = sum(p.longitude for p in cluster) / len(cluster)

    horaires_jour = defaultdict(list)
    producteurs = {}
    for p in cluster:
        for c in creneaux_par_point.get(p.pk, []):
            horaires_jour[c.jour].append((c.heure_debut, c.heure_fin))
            producteurs.setdefault(c.exploitant_id, {
                "exploitant": c.exploitant, "creneaux": []})["creneaux"].append(c)

    horaires_txt = []
    for jour in sorted(horaires_jour):
        plages = " · ".join(
            f"{d.strftime('%H:%M')}–{f.strftime('%H:%M')}"
            for d, f in _fusion_intervalles(horaires_jour[jour]))
        horaires_txt.append(f"{JOURS[jour]} {plages}")

    liste_producteurs = []
    for fiche in producteurs.values():
        e = fiche["exploitant"]
        cren_txt = sorted(
            f"{JOURS[c.jour]} {c.heure_debut.strftime('%H:%M')}–"
            f"{c.heure_fin.strftime('%H:%M')}"
            for c in fiche["creneaux"])
        # Vignette unifiée (même rendu que la page de recherche) :
        # horaires du producteur limités à SES créneaux sur ce marché
        # ou cette boutique — même structure que _horaire_vignette.
        e.horaires = [{"txt": t, "point": "", "itineraire": ""}
                      for t in cren_txt]
        liste_producteurs.append({
            "exploitant": e,
            "nom_espace": e.nom_espace,
            "slug": e.slug,
            "url": e.get_absolute_url(),
            "activite": e.activite,
            "libelle_activite": e.get_activite_display(),
            "symbole": e.emoji_vitrine,
            "mode_production": e.mode_production,
            "ville": e.ville,
            "est_demo": e.est_demo,
            "creneaux_txt": cren_txt,
        })
    liste_producteurs.sort(key=lambda p: p["nom_espace"])

    empreinte = hashlib.sha1(
        "|".join(str(p.pk) for p in sorted(cluster,
                                           key=lambda p: p.pk)).encode()
    ).hexdigest()[:6]
    slug = f"{slugify(nom)}-{slugify(ville)}-{empreinte}"

    return {
        "slug": slug,
        "url": reverse("portal:marche_detail", args=[slug]),
        "nom": nom,
        "type": type_point,
        "est_marche": type_point == PointLivraison.Type.MARCHE,
        "symbole": ("🎪" if type_point == PointLivraison.Type.MARCHE
                    else "🏪"),
        "ville": ville,
        "code_postal": code_postal,
        "adresse": adresse,
        "latitude": latitude,
        "longitude": longitude,
        "horaires_txt": horaires_txt,
        "nb_producteurs": len(liste_producteurs),
        "producteurs": liste_producteurs,
    }


def identifier_marches(inclure_demo=True):
    """Recalcule à la demande la liste des marchés et boutiques de
    producteurs (points type Marché ou Boutique, exploitants visibles
    hors traiteurs/foodtrucks, avec coordonnées). inclure_demo=False
    retire les exploitations de démonstration : le mode « Réel » de
    la page de recherche n'affiche alors que les marchés et boutiques
    tenus par de vrais producteurs."""
    points = (PointLivraison.objects
              .filter(type_point__in=(PointLivraison.Type.MARCHE,
                                      PointLivraison.Type.BOUTIQUE),
                      exploitant__visible=True)
              .exclude(latitude=None, longitude=None)
              .exclude(exploitant__activite__in=ACTIVITES_RESTAURATION)
              .select_related("exploitant")
              .order_by("ville", "nom"))
    if not inclure_demo:
        # Mode « Réel » de la recherche : les espaces fictifs de
        # démonstration (et leurs stands) n'entrent pas dans le calcul.
        points = points.exclude(exploitant__est_demo=True)

    creneaux_par_point = defaultdict(list)
    if points:
        for c in (CreneauLivraison.objects
                  .filter(point_livraison__in=points)
                  .select_related("exploitant", "exploitant__user")):
            creneaux_par_point[c.point_livraison_id].append(c)

    par_type = defaultdict(list)
    for p in points:
        par_type[p.type_point].append(p)

    marches = []
    for type_point, pts in par_type.items():
        for cluster in _clusters(pts):
            marches.append(
                _fabrique_marche(type_point, cluster, creneaux_par_point))
    marches.sort(key=lambda m: (m["ville"], m["nom"]))
    return marches
