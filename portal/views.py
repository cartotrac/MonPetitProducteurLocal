import csv
import datetime
import io
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode

import django.core.mail
from django.conf import settings

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (AnnonceForm, BulletinForm, InscriptionClientForm,
                    InscriptionExploitantForm, InscriptionFermeSeuleForm,
                    MessagerieForm, ProduitForm, ProfilExploitantForm,
                    ProfilPersonnelForm)
from .marches import identifier_marches
from .meteo import meteo_synthese
from .models import (Annonce, Bulletin, Carte, Categorie, Commande,
                    CreneauLivraison, Exploitant, Favori, LigneCarte,
                    LigneCommande, LignePanier, LigneRecolte,
                    MembreExploitation, Panier,
                    ParametresVitrine, PointLivraison, PreferenceContact,
                    Produit, ProduitStandard, ProfilClient,
                    SemaineRecolte, StatistiqueQuotidienne, Visiteur,
                    espace_actif, espaces_pro, exploitant_actif,
                    exploitant_pour, nom_affiche)
from .notifications import envoyer_sms, notifier_client
from .management.commands.charger_catalogues_activites import (
    emoji_pour_nom)

# Unités vendues à la pièce : quantités entières uniquement.
UNITES_ENTIERES = ("PC", "BO", "BQ")


def apres_connexion(request):
    """Après connexion (et après inscription) : un compte pro tombe
    directement sur son dashboard ; un client sur « Mes commandes » ;
    un visiteur non connecté sur l'accueil. Un compte Google tout neuf
    (créé depuis la page de connexion) passe d'abord par le choix
    d'espace ; les parcours « Devenir Localien » et « Créer mon espace
    pro » court-circuitent ce choix : le type est déjà décidé."""
    if not request.user.is_authenticated:
        return redirect("portal:home")
    espaces = espaces_pro(request.user)
    if len(espaces) > 1:
        return redirect("portal:choix_espace_pro")
    if len(espaces) == 1:
        request.session["mppl_espace_actif"] = espaces[0][0].pk
        return redirect("portal:dashboard")
    intention = request.session.pop("mppl_google_intent", None)
    compte_neuf = request.session.pop("mppl_compte_neuf", False)
    if intention == "pro":
        return redirect("portal:register_producer")
    if intention == "client":
        return redirect("portal:my_orders")
    if compte_neuf:
        return redirect("portal:choix_espace")
    return redirect("portal:my_orders")


@login_required
def choix_espace(request):
    """Première connexion d'un compte Google tout neuf : choix entre
    devenir Localien (client) et créer un espace pro. Le choix n'est
    pas définitif — un client peut créer son espace pro plus tard, un
    pro reste un client à part entière."""
    espaces = espaces_pro(request.user)
    if len(espaces) > 1:
        return redirect("portal:choix_espace_pro")
    if len(espaces) == 1:
        request.session["mppl_espace_actif"] = espaces[0][0].pk
        return redirect("portal:dashboard")
    if request.method == "POST":
        if request.POST.get("action") == "pro":
            return redirect("portal:register_producer")
        messages.success(request, "Bienvenue ! Votre compte client est "
                                  "prêt : commandez vos producteurs "
                                  "locaux.")
        return redirect("portal:my_orders")
    return render(request, "portal/choix_espace.html")


@login_required
def choix_espace_pro(request):
    """Connexion d'un compte rattaché à plusieurs espaces pro : choix
    de l'espace à gérer pour cette session — ou continuer en
    Localien (commandes au nom propre). Le choix est réversible à
    chaque connexion."""
    espaces = espaces_pro(request.user)
    if len(espaces) < 2:
        return redirect("portal:apres_connexion")
    if request.method == "POST":
        if request.POST.get("action") == "client":
            request.session.pop("mppl_espace_actif", None)
            messages.success(request, "Vous continuez en Localien : "
                             "vos commandes sont passées à votre nom.")
            return redirect("portal:my_orders")
        try:
            pk = int(request.POST.get("espace", "0"))
        except (TypeError, ValueError):
            pk = 0
        for ex, _role in espaces:
            if ex.pk == pk:
                request.session["mppl_espace_actif"] = pk
                return redirect("portal:dashboard")
        messages.error(request, "Espace introuvable : choisissez dans "
                       "la liste.")
        return redirect("portal:choix_espace_pro")
    return render(request, "portal/choix_espace_pro.html", {
        "espaces": [{
            "exploitant": ex,
            "role_libelle": ("Gérant·e / propriétaire"
                             if role == "GERANT" else "Compte rattaché"),
        } for ex, role in espaces],
        "salutation_nom": nom_affiche(request.user),
    })


@login_required
def bascule_espace(request):
    """Bascule du bandeau (bouton à côté du mode sombre) : entre
    l'espace pro — multi-espace : page de choix si besoin — et le
    grand public « Localien » (menus clients, commandes au nom
    propre / alias)."""
    if request.method != "POST":
        return redirect("portal:home")
    if request.POST.get("action") == "pro":
        espaces = espaces_pro(request.user)
        if not espaces:
            return redirect("portal:apres_connexion")
        if len(espaces) == 1:
            request.session["mppl_espace_actif"] = espaces[0][0].pk
            return redirect("portal:dashboard")
        return redirect("portal:choix_espace_pro")
    # Retour en grand public : plus d'espace sélectionné, bandeau et
    # menus côté client, commandes au nom propre (alias).
    request.session.pop("mppl_espace_actif", None)
    messages.success(request, "Retour en grand public : vos commandes "
                     "sont passées à votre nom (alias).")
    return redirect("portal:producer_search")


def google_entree_pro(request):
    """« Continuer avec Google » depuis « Créer mon espace pro » :
    l'intention est mémorisée en session — au retour de Google, le
    formulaire de l'exploitation (nom, activité, carte…) est proposé
    directement, le profil étant repris du compte Google."""
    request.session["mppl_google_intent"] = "pro"
    return redirect(reverse("google_login") + "?process=signup")


def google_entree_client(request):
    """« Continuer avec Google » depuis « Devenir Localien » : au
    retour de Google, le compte client est prêt et l'utilisateur tombe
    directement sur « Mes commandes »."""
    request.session["mppl_google_intent"] = "client"
    return redirect(reverse("google_login") + "?process=signup")


def mentions_legales(request):
    """Mentions légales : application libre (dépôt GitHub), instance
    hébergée par son opérateur, hébergeur technique AlwaysData."""
    return render(request, "portal/mentions.html",
                      {"retour_form": _retour_form_initial(request)})


def politique_confidentialite(request):
    """Politique de confidentialité : données traitées par le portail,
    connexion Google incluse (page exigée par l'écran de consentement
    OAuth de Google — URL publique à y déclarer)."""
    return render(request, "portal/confidentialite.html")


def conditions_utilisation(request):
    """Conditions d'utilisation du service (page exigée par l'écran
    de consentement OAuth de Google — URL publique à y déclarer)."""
    return render(request, "portal/cgu.html")


def charte_logo(request):
    """Charte graphique et logo du portail : symbole, déclinaisons,
    couleurs et règles d'usage — fichiers SVG téléchargeables et
    export PNG (écran de consentement Google inclus)."""
    return render(request, "portal/charte_logo.html")


def home(request):
    """Landing : bandeau, hero, présentation du portail — et les
    chiffres clés segmentés (pros par métier, marchés et boutiques
    identifiés, clients, visiteurs) avec historique 30 jours."""
    activites_restauration = (Exploitant.Activite.FOODTRUCK,
                              Exploitant.Activite.TRAITEUR,
                              Exploitant.Activite.RESTAURANT)
    nb_pros = (Exploitant.objects.filter(visible=True).count())
    nb_visibles = Exploitant.objects.filter(visible=True).count()
    nb_producteurs_locaux = (Exploitant.objects
                             .filter(visible=True)
                             .exclude(activite__in=activites_restauration)
                             .count())
    nb_foodtrucks = (Exploitant.objects
                     .filter(visible=True,
                             activite=Exploitant.Activite.FOODTRUCK).count())
    nb_traiteurs = (Exploitant.objects
                    .filter(visible=True,
                            activite=Exploitant.Activite.TRAITEUR).count())
    nb_restaurants = (Exploitant.objects
                      .filter(visible=True,
                              activite=Exploitant.Activite.RESTAURANT)
                      .count())
    marches_identifies = identifier_marches()
    nb_marches = sum(1 for m in marches_identifies if m["est_marche"])
    nb_boutiques = len(marches_identifies) - nb_marches
    nb_clients = (User.objects
                  .filter(exploitant__isnull=True,
                          membres_exploitation__isnull=True).count())
    nb_visiteurs = Visiteur.objects.count()
    aujourdhui = timezone.localdate()
    StatistiqueQuotidienne.objects.update_or_create(
        date=aujourdhui,
        defaults={"nb_producteurs": nb_visibles,
                  "nb_clients": nb_clients,
                  "nb_visiteurs": nb_visiteurs})
    lignes_stats = list(StatistiqueQuotidienne.objects.filter(
        date__gte=aujourdhui - datetime.timedelta(days=29))
        .order_by("date"))
    graphs = {"producteurs": _serie_stats("nb_producteurs", lignes_stats),
              "clients": _serie_stats("nb_clients", lignes_stats),
              "visiteurs": _serie_stats("nb_visiteurs", lignes_stats)}
    return render(request, "portal/home.html", {
        "nb_pros": nb_pros,
        "nb_producteurs_locaux": nb_producteurs_locaux,
        "nb_foodtrucks": nb_foodtrucks,
        "nb_traiteurs": nb_traiteurs,
        "nb_restaurants": nb_restaurants,
        "nb_marches": nb_marches,
        "nb_boutiques": nb_boutiques,
        "nb_clients": nb_clients,
        "nb_visiteurs": nb_visiteurs,
        "graph_producteurs": graphs["producteurs"],
        "graph_clients": graphs["clients"],
        "graph_visiteurs": graphs["visiteurs"],
    })


def _recherche_producteurs(q, dept, modes, activites,
                           inclure_demo=True):
    """Jeu de critères -> queryset d'exploitants visibles (partagé par
    la recherche simple et par les filtres combinés enregistrés).
    « modes » et « activites » acceptent une ou plusieurs valeurs
    (listes à choix multiple) : la sélection s'additionne (ex : Bio OU
    Permaculture), les autres critères se croisent. inclure_demo=False
    exclut les exploitations fictives de démonstration : la bascule
    🎃 Démo / 🧡 Réel de la recherche filtre ainsi EN AMONT."""
    # Tolère les valeurs uniques héritées (chaîne ou listes plates)
    if isinstance(modes, str):
        modes = [modes] if modes else []
    if isinstance(activites, str):
        activites = [activites] if activites else []
    modes = [m for m in modes if m]
    activites = [a for a in activites if a]
    exploitants = Exploitant.objects.filter(visible=True)
    if not inclure_demo:
        exploitants = exploitants.exclude(est_demo=True)
    if q:
        exploitants = exploitants.filter(
            Q(nom_espace__icontains=q) | Q(ville__icontains=q)
            | Q(code_postal__icontains=q)
            | Q(departement__icontains=q)
            | Q(produits__nom__icontains=q)
            | Q(produits__categorie__nom__icontains=q)).distinct()
    if dept:
        # Département saisi (« 81 », « Tarn »…) OU code postal commençant
        # par ces chiffres : un exploitant sans champ département rempli
        # reste trouvable depuis son code postal — et les cas NOMADES
        # (foodtrucks) restent aussi trouvable par les codes postaux et
        # villes de leurs emplacements et points déclarés.
        exploitants = exploitants.filter(
            Q(departement__iexact=dept)
            | Q(code_postal__istartswith=dept)
            | Q(points_livraison__code_postal__istartswith=dept)
            | Q(points_livraison__ville__icontains=dept)).distinct()
    if modes:
        exploitants = exploitants.filter(mode_production__in=modes)
    if activites:
        exploitants = exploitants.filter(activite__in=activites)
    return exploitants


def _serie_stats(champ, lignes):
    """Série prête à dessiner (barres en %) + tendance sur ~7 jours,
    pour les mini-graphes des badges de la page de recherche."""
    if isinstance(champ, (list, tuple)):
        valeurs = [sum(getattr(s, c) or 0 for c in champ)
                   for s in lignes]
    else:
        valeurs = [getattr(s, champ) for s in lignes]
    if not valeurs:
        return {"points": [], "tendance": 0, "dernier": 0}
    maximum = max(valeurs, default=0) or 1
    points = []
    for ligne, valeur in zip(lignes, valeurs):
        points.append({
            "hauteur": round(100 * valeur / maximum),
            "valeur": valeur,
            "jour": ligne.date.strftime("%d/%m"),
            "titre": f"{ligne.date.strftime('%d/%m')} : {valeur}",
        })
    reference = valeurs[0] if len(valeurs) < 8 else valeurs[-8]
    return {"points": points, "tendance": valeurs[-1] - reference,
            "dernier": valeurs[-1] if valeurs else 0}


def producer_search(request):
    """Recherche multi-critères : texte (exploitant, produit, ville),
    activités, modes de production — plus la CARTE des résultats.
    Le champ « Département, région ou code postal » est purement
    SPATIAL : il ne filtre pas le jeu de résultats, la carte zoome
    dessus au chargement et filtre les vignettes par emprise."""
    q = request.GET.get("q", "").strip()
    dept = request.GET.get("dept", "").strip()
    # Listes à choix multiple : Ctrl/clic pour combiner plusieurs
    # modes de production ou activités dans une même recherche.
    mode_choisi = [m for m in request.GET.getlist("mode") if m.strip()]
    activite_choisie = [a for a in request.GET.getlist("activite")
                        if a.strip()]
    # Bascule 🎃 Démo / 🧡 Réel : active par défaut (comptes fictifs
    # visibles). En mode « Réel », les comptes de démonstration sont
    # filtrés EN AMONT de tout le reste — vignettes, carte, marchés
    # déduits, dénombrements et autres filtres (texte, spatial,
    # activités, modes) ne voient que le jeu filtré.
    demo = request.GET.get("demo", "1") != "0"
    visibles = Exploitant.objects.filter(visible=True)
    if not demo:
        visibles = visibles.exclude(est_demo=True)
    # « dept » n'entre PAS dans le queryset : il pilote uniquement
    # le zoom cartographique (data-zone), la carte filtre ensuite
    # les vignettes par emprise.
    exploitants = _recherche_producteurs(q, "", mode_choisi,
                                         activite_choisie,
                                         inclure_demo=demo)
    # Mode de visualisation : « producteurs » (toutes les activités
    # sauf foodtrucks et traiteurs — ils n'ont PLUS rien à faire sur
    # cette carte), « restauration » (uniquement ces deux-là) ou
    # « marches » (marchés et boutiques de producteurs déduits de
    # leurs points et créneaux déclarés). Liste de choix, titre,
    # carte, légende et vignettes s'adaptent au mode demandé.
    visu = request.GET.get("visu", "").strip()
    visu_marches = visu == "marches"
    activites_restauration = (Exploitant.Activite.FOODTRUCK,
                              Exploitant.Activite.TRAITEUR,
                              Exploitant.Activite.RESTAURANT)
    if visu == "restauration":
        exploitants = exploitants.filter(
            activite__in=activites_restauration)
    elif not visu_marches and visu != "tout":
        exploitants = exploitants.exclude(
            activite__in=activites_restauration)
    exploitants = list(exploitants.order_by("nom_espace"))
    # Marchés & boutiques identifiés (modes marches et All-in-1) :
    # entités virtuelles recalculées à la demande ; les filtres texte
    # et département s'y appliquent aussi (nom, ville, adresse, CP).
    marches = []
    type_marche_choisi = []
    if visu_marches or visu == "tout":
        marches = identifier_marches(inclure_demo=demo)
        if q:
            marches = [m for m in marches if q.lower() in (
                f"{m['nom']} {m['ville']} {m['adresse']}".lower())]
        # Filtre « Marchés / Boutiques » propre au mode marches ;
        # tout décocher = marchés et boutiques.
        type_marche_choisi = [t for t in request.GET.getlist("type_marche")
                              if t in ("MARCHE", "BOUTIQUE")]
        if type_marche_choisi:
            marches = [m for m in marches
                       if m["type"] in type_marche_choisi]
            # Mode All-in-1 : filtrer sur les marchés/boutiques ne
            # garde QUE ces entités — sur la carte comme dans les
            # vignettes. Les producteurs qui les alimentent restent
            # accessibles depuis la fiche générée de chaque marché
            # ou boutique (lien « Voir la fiche » des popups).
            if visu == "tout":
                exploitants = []
    # Dénombrements affichés à côté du titre : producteurs visibles,
    # clients inscrits (comptes non pro), visiteurs (sessions anonymes),
    # + photo quotidienne pour l'historique / tendance des badges.
    nb_producteurs = Exploitant.objects.filter(visible=True).count()
    nb_clients = (User.objects
                  .filter(exploitant__isnull=True,
                          membres_exploitation__isnull=True).count())
    nb_visiteurs = Visiteur.objects.count()
    # Badges de la page selon le mode : total des pros inscrits puis
    # dénombrements propres à chaque mode de visualisation
    # (producteurs locaux / traiteurs & foodtrucks / marchés &
    # boutiques de producteurs).
    nb_pros = visibles.count()
    nb_producteurs_locaux = (visibles
                             .exclude(
                                 activite__in=activites_restauration)
                             .count())
    nb_foodtrucks = (visibles
                     .filter(activite=Exploitant.Activite.FOODTRUCK)
                     .count())
    nb_traiteurs = (visibles
                    .filter(activite=Exploitant.Activite.TRAITEUR)
                    .count())
    nb_restaurants = (visibles
                      .filter(activite=Exploitant.Activite.RESTAURANT)
                      .count())
    tous_marches = (marches if visu_marches
                    else identifier_marches(inclure_demo=demo))
    nb_marches = sum(1 for m in tous_marches if m["est_marche"])
    nb_boutiques = len(tous_marches) - nb_marches
    aujourdhui = timezone.localdate()
    # Photo quotidienne enrichie : les fenêtres de stats des badges
    # suivent la bascule 🎃 Démo / 🧡 Réel ET le mode de
    # visualisation — chaque dénombrement est donc enregistré en
    # deux variantes, avec et sans les comptes de démonstration.
    tous_visibles = Exploitant.objects.filter(visible=True)
    reels = tous_visibles.exclude(est_demo=True)
    marches_tous = identifier_marches(inclure_demo=True)
    nb_marches_tous = sum(1 for m in marches_tous if m["est_marche"])
    nb_boutiques_tous = len(marches_tous) - nb_marches_tous
    marches_reels = identifier_marches(inclure_demo=False)
    nb_marches_reels = sum(1 for m in marches_reels
                           if m["est_marche"])
    nb_boutiques_reels = len(marches_reels) - nb_marches_reels
    photo = {
        "nb_producteurs": nb_producteurs,
        "nb_clients": nb_clients,
        "nb_visiteurs": nb_visiteurs,
        "nb_pros_reels": reels.count(),
        "nb_locaux": tous_visibles.exclude(
            activite__in=activites_restauration).count(),
        "nb_locaux_reels": reels.exclude(
            activite__in=activites_restauration).count(),
        "nb_restauration": tous_visibles.filter(
            activite__in=activites_restauration).count(),
        "nb_restauration_reels": reels.filter(
            activite__in=activites_restauration).count(),
        "nb_marches": nb_marches_tous,
        "nb_boutiques": nb_boutiques_tous,
        "nb_marches_reels": nb_marches_reels,
        "nb_boutiques_reels": nb_boutiques_reels,
    }
    StatistiqueQuotidienne.objects.update_or_create(
        date=aujourdhui, defaults=photo)
    # Compléter une seule fois les lignes antérieures au
    # déploiement de ces champs (tous à zéro = jamais enrichies) :
    # on y reporte la photo du jour pour un historique continu,
    # les jours suivants s'enrichissent naturellement.
    StatistiqueQuotidienne.objects.exclude(date=aujourdhui).filter(
        nb_pros_reels=0, nb_locaux=0, nb_restauration=0,
        nb_marches=0).update(
            nb_pros_reels=photo["nb_pros_reels"],
            nb_locaux=photo["nb_locaux"],
            nb_locaux_reels=photo["nb_locaux_reels"],
            nb_restauration=photo["nb_restauration"],
            nb_restauration_reels=photo["nb_restauration_reels"],
            nb_marches=photo["nb_marches"],
            nb_boutiques=photo["nb_boutiques"],
            nb_marches_reels=photo["nb_marches_reels"],
            nb_boutiques_reels=photo["nb_boutiques_reels"])
    lignes_stats = list(StatistiqueQuotidienne.objects.filter(
        date__gte=aujourdhui - datetime.timedelta(days=89))
        .order_by("date"))
    # Champs des séries selon la bascule Démo / Réel : les colonnes
    # « _reels » excluent les comptes de démonstration ; le second
    # badge reçoit la série de SON mode (locaux, restauration ou
    # marchés+boutiques).
    champ_pros = "nb_producteurs" if demo else "nb_pros_reels"
    champ_locaux = "nb_locaux" if demo else "nb_locaux_reels"
    champ_resto = ("nb_restauration" if demo
                   else "nb_restauration_reels")
    champ_marches = "nb_marches" if demo else "nb_marches_reels"
    champ_boutiques = ("nb_boutiques" if demo
                       else "nb_boutiques_reels")
    graphs = {"producteurs": _serie_stats(champ_pros, lignes_stats),
              "locaux": _serie_stats(champ_locaux, lignes_stats),
              "restauration": _serie_stats(champ_resto, lignes_stats),
              "marches": _serie_stats([champ_marches, champ_boutiques],
                                      lignes_stats),
              "clients": _serie_stats("nb_clients", lignes_stats),
              "visiteurs": _serie_stats("nb_visiteurs", lignes_stats)}
    # Horaires de retrait / boutique : créneaux récurrents par espace,
    # affichés au survol des vignettes.
    horaires = {}
    for c in (CreneauLivraison.objects
              .filter(exploitant__in=exploitants)
              .select_related("point_livraison")
              .order_by("jour", "heure_debut")):
        horaires.setdefault(c.exploitant_id, []).append(
            _horaire_vignette(c))
    for e in exploitants:
        e.horaires = horaires.get(e.pk, [])
    # Favoris de l'utilisateur connecté : l'étoile des vignettes est
    # pleine pour les espaces déjà suivis.
    favoris_slugs = (
        list(Favori.objects.filter(
            user=request.user, exploitant__in=exploitants)
            .values_list("exploitant__slug", flat=True))
        if request.user.is_authenticated else [])
    # Position « chez moi » du bouton 🏠 de la carte : coordonnées de
    # l'exploitation pour un pro connecté, géolocalisation du
    # navigateur pour un client connecté, pas de bouton sinon.
    home_carte = None
    if request.user.is_authenticated:
        moi = exploitant_actif(request)
        if moi and moi.latitude is not None and moi.longitude is not None:
            home_carte = {"lat": moi.latitude, "lon": moi.longitude}
        else:
            home_carte = {"lat": None, "connecte": True}
    # Données carto : uniquement les résultats filtrés avec
    # coordonnées — en mode marches, les entités affichées sont les
    # marchés et boutiques identifiés (même bloc json_script, la clé
    # est_marche les distingue côté JS). En mode All-in-1, les
    # marchés et boutiques identifiés s'AJOUTENT aux professionnels.
    marches_carte = ([{
        "est_marche": True,
        "nom": m["nom"],
        "type": m["type"],
        "symbole": m["symbole"],
        "ville": m["ville"],
        "latitude": m["latitude"],
        "longitude": m["longitude"],
        "url": m["url"],
        "nb_producteurs": m["nb_producteurs"],
        "horaires_txt": m["horaires_txt"][:4],
    } for m in marches]
        if (visu_marches or visu == "tout") else [])
    if visu_marches:
        carte_data = marches_carte
    else:
        # Position dynamique des foodtrucks : emplacement du créneau
        # en cours ou du prochain arrêt s'ils sont définis, adresse
        # déclarée sinon — la carte retranscrit leur emplacement au
        # moment de la recherche (cas nomades). En mode All-in-1, la
        # carte commence par les marchés et boutiques identifiés.
        carte_data = list(marches_carte)
        for e in exploitants:
            lat, lon, libelle_position = e.latitude, e.longitude, ""
            if e.activite == Exploitant.Activite.FOODTRUCK:
                position = _position_dynamique_foodtruck(e)
                if position:
                    lat, lon, libelle_position = position
            if lat is None or lon is None:
                continue
            # Favori direct depuis le popup de la carte : l'étoile
            # du marqueur reflète l'état pour le compte connecté.
            carte_data.append({
                "nom_espace": e.nom_espace,
                "mode_production": e.mode_production,
                "activite": e.activite,
                "specialite": e.specialite if e.activite in Exploitant.ACTIVITES_AVEC_SPECIALITE else "",
                "symbole": e.emoji_vitrine,
                "ville": e.ville,
                "latitude": lat,
                "longitude": lon,
                "position_libelle": libelle_position,
                "est_demo": e.est_demo,
                "url": e.get_absolute_url(),
                "slug": e.slug,
                "connecte": request.user.is_authenticated,
                "est_favori": e.slug in favoris_slugs,
                "url_favori": reverse("portal:favoris_toggle",
                                      args=[e.slug]),
            })
    # Liste de choix d'activités adaptée au mode : seuls les deux
    # foodtruck / traiteur en mode restauration, tous les autres en
    # mode producteurs.
    if visu == "tout":
        # Mode All-in-1 : le filtre d'activités propose TOUTES les
        # activités — producteurs, restauration et foodtrucks.
        activite_cases = list(Exploitant.Activite.choices)
    else:
        activite_cases = [
            c for c in Exploitant.Activite.choices
            if (c[0] in activites_restauration)
            == (visu == "restauration")]
    # Le bouton « Filtrer » passe en rouge (et un « ✕ Retirer »
    # apparaît) dès qu'un filtre — texte, zone spatiale ou cases
    # cochées — est actif.
    filtre_actif = bool(q or dept or mode_choisi
                        or activite_choisie or type_marche_choisi)
    # Pagination des vignettes : 25 par page par défaut, réglable
    # 10 / 25 / 50 / 100 via « par_page ». La CARTE conserve toujours
    # le jeu complet des résultats filtrés : seule la grille des
    # vignettes est découpée en pages.
    try:
        par_page = int(request.GET.get("par_page", 25))
    except (TypeError, ValueError):
        par_page = 25
    if par_page not in (10, 25, 50, 100):
        par_page = 25
    paginator = Paginator(exploitants, par_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    # Paramètres de l'URL courante (hors pagination) : les liens de
    # page et le sélecteur « par page » conservent ainsi les filtres
    # actifs — y compris les listes à choix multiple (mode, activité).
    filtres_get = [
        (cle, valeur)
        for cle in request.GET.keys()
        if cle not in ("page", "par_page")
        for valeur in request.GET.getlist(cle)]
    query_pages = urlencode(filtres_get, doseq=True)
    # Fenêtre de numéros de page (max 7 boutons + ellipses).
    nb_pages = paginator.num_pages
    courante = page_obj.number
    if nb_pages <= 7:
        pages_pagination = list(range(1, nb_pages + 1))
    else:
        pages_pagination = []
        precedent = None
        for n in sorted({1, 2, courante - 1, courante, courante + 1,
                         nb_pages - 1, nb_pages}):
            if 1 <= n <= nb_pages:
                if precedent is not None and n - precedent > 1:
                    pages_pagination.append("…")
                pages_pagination.append(n)
                precedent = n
    # Salutation personnalisée (en tête de la page) : alias ou nom
    # du compte ; en mode espace pro, rôle et structure suivent.
    salutation = None
    if request.user.is_authenticated:
        salutation = {"nom": nom_affiche(request.user)}
        actif = espace_actif(request)
        if actif is not None:
            salutation["espace"] = actif.nom_espace
            salutation["role_libelle"] = (
                "Gérant·e / propriétaire"
                if actif.user_id == request.user.id
                else "Compte rattaché")
            salutation["activite"] = actif.get_activite_display()
            salutation["specialite"] = (actif.get_specialite_display()
                                        if actif.specialite else "")
    return render(request, "portal/search_results.html", {
        "salutation": salutation,
        "exploitants": page_obj,
        "nb_resultats": paginator.count,
        "par_page": par_page,
        "par_page_choices": (10, 25, 50, 100),
        "page_obj": page_obj,
        "pages_pagination": pages_pagination,
        "filtres_get": filtres_get,
        "query_pages": query_pages,
        "carte_data": carte_data,
        "activites": activite_cases,
        "visu": visu,
        "demo": demo,
        "home_carte": home_carte,
        "marches": marches,
        "resultats_vides": not carte_data,
        "nb_pros": nb_pros,
        "nb_producteurs_locaux": nb_producteurs_locaux,
        "nb_foodtrucks": nb_foodtrucks,
        "nb_traiteurs": nb_traiteurs,
        "nb_restaurants": nb_restaurants,
        "nb_marches": nb_marches,
        "nb_boutiques": nb_boutiques,
        "nb_producteurs": nb_producteurs,
        "nb_clients": nb_clients,
        "nb_visiteurs": nb_visiteurs,
        "graph_producteurs": graphs["producteurs"],
        "graph_clients": graphs["clients"],
        "graph_visiteurs": graphs["visiteurs"],
        "graph_locaux": graphs["locaux"],
        "graph_restauration": graphs["restauration"],
        "graph_marches": graphs["marches"],
        "q": q, "dept": dept,
        "mode_choisi": mode_choisi, "activite_choisie": activite_choisie,
        "type_marche_choisi": type_marche_choisi,
        "filtre_actif": filtre_actif,
        "favoris_slugs": favoris_slugs,
    })


def producteurs_geojson(request):
    """Données carte : exploitants visibles avec coordonnées — les
    foodtrucks sont positionnés sur l'emplacement de leur créneau en
    cours ou de leur prochain arrêt au moment de la requête (adresse
    déclarée en repli)."""
    # Bascule 🎃 Démo / 🧡 Réel : paramètre « demo » (1 par défaut) —
    # la page de recherche en mode « Réel » ne charge que les vrais
    # producteurs sur la carte.
    inclure_demo = request.GET.get("demo", "1") != "0"
    exploitants = Exploitant.objects.filter(visible=True)
    if not inclure_demo:
        exploitants = exploitants.exclude(est_demo=True)
    data = []
    for e in exploitants:
        lat, lon, libelle_position = e.latitude, e.longitude, ""
        if e.activite == Exploitant.Activite.FOODTRUCK:
            position = _position_dynamique_foodtruck(e)
            if position:
                lat, lon, libelle_position = position
        if lat is None or lon is None:
            continue
        data.append({
            "slug": e.slug,
            "nom_espace": e.nom_espace,
            "mode_production": e.mode_production,
            "activite": e.activite,
            "specialite": e.specialite if e.activite in Exploitant.ACTIVITES_AVEC_SPECIALITE else "",
            "symbole": e.emoji_vitrine,
            "ville": e.ville,
            "latitude": lat,
            "longitude": lon,
            "position_libelle": libelle_position,
            "est_demo": e.est_demo,
            "url": e.get_absolute_url(),
        })
    return JsonResponse(list(data), encoder=DjangoJSONEncoder, safe=False)


def marche_detail(request, slug):
    """Fiche PUBLIQUE d'un marché ou d'une boutique de producteurs :
    entité VIRTUELLE recalculée à la demande (aucune ligne dédiée en
    base) — nom le plus probable, position moyenne, horaires déduits
    des créneaux déclarés, et les producteurs rattachés, groupés par
    catégorie d'activité."""
    for marche in identifier_marches():
        if marche["slug"] == slug:
            # États favoris des producteurs du marché : l'étoile des
            # vignettes unifiées reflète le compte connecté.
            favoris_slugs = (
                list(Favori.objects.filter(
                    user=request.user,
                    exploitant__slug__in=[p["slug"]
                                          for p in marche["producteurs"]])
                    .values_list("exploitant__slug", flat=True))
                if request.user.is_authenticated else [])
            return render(request, "portal/marche_detail.html",
                          {"marche": marche,
                           "favoris_slugs": favoris_slugs})
    raise Http404("Marché ou boutique de producteurs inconnu.")


def producer_detail(request, slug):
    """Page publique d'un exploitant : récolte de la semaine + à venir,
    météo en direct sur place et bandeau des créneaux de livraison."""
    exploitant = get_object_or_404(Exploitant, slug=slug, visible=True)
    today = timezone.localdate()
    lundi = today - datetime.timedelta(days=today.weekday())
    semaines_avenir = list(
        SemaineRecolte.objects.filter(exploitant=exploitant, publiee=True,
                                      lundi__gt=lundi).order_by("lundi"))
    semaine = (SemaineRecolte.objects.filter(exploitant=exploitant,
                                             publiee=True,
                                             lundi__lte=lundi)
               .order_by("-lundi").first())
    lignes = list(semaine.lignes.select_related("produit__categorie",
                                                "produit__origine_standard")
                  if semaine else [])
    # Produits regroupés par catégorie (même présentation que côté
    # maraîcher) : tri par position de catégorie puis nom.
    lignes.sort(key=lambda l: (
        (l.produit.categorie.position if l.produit.categorie else 9999)
        or 9999,
        l.produit.categorie.nom if l.produit.categorie else "zz",
        l.produit.nom))
    groupes, courant = [], None
    for ligne in lignes:
        nom_cat = (ligne.produit.categorie.nom
                   if ligne.produit.categorie else "Autres produits")
        if not groupes or groupes[-1][0] != nom_cat:
            groupes.append((nom_cat, []))
        groupes[-1][1].append(ligne)
    vitrine, _cree = ParametresVitrine.objects.get_or_create(
        exploitant=exploitant)
    # Équipe affichée sur la vitrine : gérant + associés rattachés,
    # avec leur photo de profil externe si elle existe.
    def _membre(user, role):
        try:
            photo = user.profil_client.photo_url
        except Exception:
            photo = ""
        return {"nom": user.get_full_name() or user.username,
                "role": role, "photo_url": photo}
    equipe = [_membre(exploitant.user, "Gérant")]
    equipe += [_membre(m.user, "Associé·e")
                for m in exploitant.membres.select_related("user")]
    # Dispo restante par produit (colonne de saisie directe sur la
    # vitrine : les quantités partent pré-remplies vers la commande).
    restes = {}
    if semaine:
        offres_recolte, _mode = _offres_commande(exploitant, semaine)
        restes = {o["produit"].pk: o["reste"] for o in offres_recolte}
    est_favori = (request.user.is_authenticated
                  and Favori.objects.filter(user=request.user,
                                            exploitant=exploitant).exists())
    nature_favori = ""
    if est_favori:
        nature_favori = (Favori.objects.filter(
            user=request.user, exploitant=exploitant)
            .values_list("nature", flat=True).first() or "")
    # Carte / boutique stable (traiteurs, foodtrucks, fromagers,
    # apiculteurs, conserveries, micro-brasseurs) : la vitrine
    # publique affiche la carte ACTIVE en plus de l'encart de la
    # semaine — sélection permanente, esprit boutique.
    carte_active = (Carte.objects.filter(
        exploitant=exploitant,
        statut=Carte.Statut.ACTIVE)
        .prefetch_related("lignes__produit",
                          "lignes__produit__origine_standard")
        .first())
    # Restant par ligne de la carte active : stock publié − quantités
    # des commandes VALIDÉES (après ajustement éventuel du pro).
    restes_carte = {}
    if carte_active:
        stocks_carte = _stocks_carte(exploitant)
        for l in carte_active.lignes.all():
            if l.produit_id is not None and l.stock is not None:
                reste = stocks_carte.get(l.produit_id, (None, None))[1]
                if reste is not None:
                    restes_carte[l.pk] = reste
    return render(request, "portal/producer_detail.html", {
        "exploitant": exploitant,
        "restes_carte": restes_carte,
        "carte_active": carte_active,
        "vitrine": vitrine,
        "reseaux": vitrine.reseaux or {},
        "equipe": equipe,
        "semaine": semaine,
        "lignes": lignes,
        "groupes_categories": groupes,
        "semaines_avenir": semaines_avenir,
        "restes": restes,
        "est_favori": est_favori,
        "nature_favori": nature_favori,
        "est_compte_pro": exploitant_actif(request) is not None,
        "meteo": meteo_synthese(exploitant),
        "points_livraison": exploitant.points_livraison.all(),
        "creneaux": exploitant.creneaux.select_related("point_livraison"),
    })


# ---------------------------------------------------------------- registres


@login_required
def favoris_toggle(request, slug):
    """Ajoute/retire un producteur des favoris (étoile sur la vitrine).
    Les comptes pro précisent la nature : Fournisseur ou Client pro ;
    les clients l'ajoutent simplement. Redirige vers la vitrine."""
    exploitant = get_object_or_404(Exploitant, slug=slug, visible=True)
    nature = request.POST.get("nature", Favori.Nature.CLIENT)
    if nature not in Favori.Nature.values:
        nature = Favori.Nature.CLIENT
    # Un non-pro ne peut créer que des favoris « client »
    if (nature != Favori.Nature.CLIENT
            and exploitant_actif(request) is None):
        nature = Favori.Nature.CLIENT
    favori = Favori.objects.filter(user=request.user,
                                   exploitant=exploitant).first()
    if favori:
        favori.delete()
        messages.info(request, f"{exploitant.nom_espace} retiré de vos "
                       "favoris.")
    else:
        Favori.objects.create(user=request.user, exploitant=exploitant,
                              nature=nature)
        libelle = dict(Favori.Nature.choices).get(nature, "")
        messages.success(request, f"{exploitant.nom_espace} ajouté à vos "
                         f"favoris ⭐ ({libelle.lower()})")
    # Depuis une vignette (recherche, favoris), revenir à la page
    # d'origine au lieu de la vitrine de l'espace.
    suite = request.POST.get("next", "")
    if suite.startswith("/"):
        return redirect(suite)
    return redirect("portal:producer_detail", slug=slug)


def _horaire_vignette(c):
    """Créneau pour l'encart horaires des vignettes : texte, point
    nommé et — pour les MARCHÉS, EMPLACEMENTS et BOUTIQUES publics
    seulement —
    un lien d'itinéraire Google Maps (calcul d'itinéraire au
    survol). Les points de livraison gardent leur position exacte
    pour les clients des paniers livrés : rien ne transite sur les
    pages publiques."""
    entree = {
        "txt": (f"{c.get_jour_display()} "
                f"{c.heure_debut.strftime('%H:%M')}–"
                f"{c.heure_fin.strftime('%H:%M')}"),
        "point": "",
        "itineraire": "",
    }
    if c.point_livraison:
        p = c.point_livraison
        entree["point"] = f"{p.emoji_type} {p.nom}"
        if (p.type_point in (PointLivraison.Type.MARCHE,
                             PointLivraison.Type.EMPLACEMENT,
                             PointLivraison.Type.BOUTIQUE)
                and p.latitude is not None
                and p.longitude is not None):
            entree["itineraire"] = (
                "https://www.google.com/maps/dir/?api=1"
                f"&destination={p.latitude:.6f},{p.longitude:.6f}")
    return entree


def _horaires_exploitants(exploitants):
    """Créneaux récurrents de boutique / point de livraison par espace,
    pour l'encart horaires des vignettes (même présentation que la
    page de recherche)."""
    horaires = {}
    for c in (CreneauLivraison.objects
              .filter(exploitant__in=list(exploitants))
              .select_related("point_livraison")
              .order_by("jour", "heure_debut")):
        horaires.setdefault(c.exploitant_id, []).append(
            _horaire_vignette(c))
    for e in exploitants:
        e.horaires = horaires.get(e.pk, [])


@login_required
def mes_producteurs(request):
    """Les favoris du compte : côté client, les producteurs suivis et
    les espaces déjà commandés ; côté pro, distinction Fournisseurs /
    Clients pro (les espaces déjà commandés sont intégrées). Les
    vignettes reprennent la présentation de la page de recherche
    (horaires au survol inclus)."""
    favoris = list(Favori.objects.filter(user=request.user)
                   .select_related("exploitant"))
    exploitant_ids = [f.exploitant_id for f in favoris]
    deja_commandes = (Exploitant.objects.filter(
        visible=True, commandes__client=request.user)
        .exclude(pk__in=exploitant_ids)
        .distinct().order_by("nom_espace"))
    est_pro = exploitant_actif(request) is not None
    favoris_slugs = list(Favori.objects.filter(
        user=request.user).values_list("exploitant__slug", flat=True))
    if est_pro:
        # Les espaces déjà commandés sont classés « client pro »
        deja = list(deja_commandes)
        fournisseurs = [f.exploitant for f in favoris
                        if f.nature == Favori.Nature.FOURNISSEUR]
        clients_pro = [f.exploitant for f in favoris
                       if f.nature != Favori.Nature.FOURNISSEUR]
        _horaires_exploitants(fournisseurs + clients_pro + deja)
        return render(request, "portal/mes_producteurs.html", {
            "est_pro": True,
            "favoris_fournisseurs": fournisseurs,
            "favoris_clients": clients_pro,
            "deja_commandes": deja,
            "favoris_slugs": favoris_slugs,
        })
    favoris_clients = [f.exploitant for f in favoris]
    deja = list(deja_commandes)
    _horaires_exploitants(favoris_clients + deja)
    return render(request, "portal/mes_producteurs.html", {
        "est_pro": False,
        "favoris": favoris_clients,
        "deja_commandes": deja,
        "favoris_slugs": favoris_slugs,
    })


def _enregistrer_image_externe(produit, url):
    """Photo externe (drive, cloud, réseau) : stockée dans attributs
    JSONB, aucun fichier sur le serveur. Vide = lien retiré."""
    url = (url or "").strip()
    attributs = dict(produit.attributs or {})
    if url:
        attributs["image_url"] = url
    else:
        attributs.pop("image_url", None)
    produit.attributs = attributs

def register_exploitant(request):
    """Inscription pro : formulaire complet (compte + espace) pour un
    visiteur — ou « espace seul » pour un compte DÉJÀ connecté (cas
    « Continuer avec Google » : le Localien crée son espace pro sans
    retaper prénom, nom, e-mail ni photo)."""
    if request.user.is_authenticated:
        if exploitant_actif(request) is not None:
            # Déjà pro : rien à recréer ici.
            return redirect("portal:dashboard")
        if request.method == "POST":
            form = InscriptionFermeSeuleForm(request.POST)
            if form.is_valid():
                form.save(request.user)
                messages.success(
                    request, "Bienvenue ! Votre espace producteur est "
                    "prêt. Complétez votre fiche (SIRET, logo, "
                    "description, points de livraison) depuis la page "
                    "⚙️ Paramètres, puis importez vos produits depuis le "
                    "catalogue de votre activité.")
                return redirect("portal:dashboard")
        else:
            form = InscriptionFermeSeuleForm()
        return render(request, "portal/registration/register_producer.html",
                      {"form": form})
    if request.method == "POST":
        form = InscriptionExploitantForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            _envoyer_verification_courriel(request, user)
            messages.success(
                request, "Bienvenue ! Votre espace producteur est prêt. "
                "Complétez votre fiche (SIRET, logo, description, points de "
                "livraison) depuis la page ⚙️ Paramètres, puis importez vos "
                "produits depuis le catalogue de votre activité.")
            return redirect("portal:dashboard")
    else:
        form = InscriptionExploitantForm()
    return render(request, "portal/registration/register_producer.html",
                  {"form": form})


def _envoyer_verification_courriel(request, user):
    """Mode doux : envoie l'e-mail de vérification de l'adresse du
    compte si un serveur SMTP est configuré (sans EMAIL_HOST, le backend
    console ne réalise aucun envoi réel : le compte reste utilisable,
    le bandeau n'apparaît pas — jamais bloquant)."""
    if getattr(settings, "EMAIL_HOST", ""):
        try:
            # API stable d'allauth (toutes versions récentes) : crée
            # l'entrée EmailAddress et envoie le lien de confirmation.
            from allauth.account.models import EmailAddress
            EmailAddress.objects.add_email(
                request, user, user.email, confirm=True, signup=True)
            return True
        except Exception:
            pass
    return False


def register_client(request):
    if request.user.is_authenticated:
        # Déjà connecté (ex : retour via Google) : pas de second compte.
        return redirect("portal:apres_connexion")
    if request.method == "POST":
        form = InscriptionClientForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if _envoyer_verification_courriel(request, user):
                messages.info(
                    request, "📬 Un e-mail de vérification vous attend : "
                    "un clic sur le lien confirme votre adresse (utile "
                    "pour la récupération de mot de passe et pour la "
                    "connexion Google).")
            messages.success(request, "Compte client créé. À vous de commander !")
            return redirect("portal:apres_connexion")
    else:
        form = InscriptionClientForm()
    return render(request, "portal/registration/register_client.html",
                  {"form": form})


@login_required
def renvoyer_verification_courriel(request):
    """Bandeau « Vérifiez votre e-mail » : renvoie l'e-mail de
    vérification à la demande (mode doux, non bloquant)."""
    if request.method == "POST" and _envoyer_verification_courriel(
            request, request.user):
        messages.success(
            request, "📬 E-mail de vérification renvoyé : regardez "
            "votre boîte de réception (et vos spams).")
    elif request.method == "POST":
        messages.error(
            request, "Envoi impossible pour le moment : réessayez "
            "plus tard.")
    suivant = request.POST.get("suivant") or ""
    # Redirection interne uniquement : jamais de renvoi vers un site
    # externe, même si la valeur vient du client.
    if suivant.startswith("/") and not suivant.startswith("//"):
        return redirect(suivant)
    return redirect("portal:home")


def est_exploitant(user):
    # Propriétaire de l'exploitation OU membre rattaché (équipe).
    return exploitant_pour(user) is not None


exploitant_requis = user_passes_test(est_exploitant, login_url="portal:login")


def proprietaire_requis(fonction):
    """Réservé au gestionnaire principal (compte propriétaire de
    l'exploitation) : fiche espace/SIRET, équipe, catalogue et catégories.
    Les membres de l'équipe n'ont accès qu'à la gestion courante :
    récoltes, commandes, paniers, points de livraison."""
    def wrapper(request, *args, **kwargs):
        exploitant_courant = exploitant_actif(request)
        if (exploitant_courant is None
                or exploitant_courant.user_id != request.user.id):
            messages.error(
                request, "Action réservée au gestionnaire principal de "
                "l'exploitation (fiche espace, SIRET, équipe, catalogue).")
            return redirect("portal:dashboard")
        return fonction(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- espace pro

JOURS_NOMS = {1: "lundi", 2: "mardi", 3: "mercredi", 4: "jeudi",
              5: "vendredi", 6: "samedi", 7: "dimanche"}


def _heure_courte(t):
    """18:30 -> « 18h30 », 08:00 -> « 8h »."""
    return t.strftime("%Hh%M").replace("h00", "h").lstrip("0")


def _phrase_jours(jours):
    """[1..5] -> « du lundi au vendredi » ; [4] -> « le jeudi » ;
    [2, 4] -> « le mardi et le jeudi »."""
    jours = sorted(jours)
    if not jours:
        return ""
    if len(jours) == 1:
        return "le " + JOURS_NOMS[jours[0]]
    if jours == list(range(jours[0], jours[-1] + 1)):
        return (f"du {JOURS_NOMS[jours[0]]} au "
                f"{JOURS_NOMS[jours[-1]]}")
    return ("le " + ", ".join(JOURS_NOMS[j] for j in jours[:-1])
            + " et le " + JOURS_NOMS[jours[-1]])


def _phrase_jours_pluriel(jours):
    """Variante « marché » : [4] -> « tous les jeudis »,
    [2, 4] -> « les mardis et les jeudis »."""
    jours = sorted(jours)
    if len(jours) == 1:
        return "tous les " + JOURS_NOMS[jours[0]] + "s"
    if jours == list(range(jours[0], jours[-1] + 1)):
        return (f"du {JOURS_NOMS[jours[0]]} au "
                f"{JOURS_NOMS[jours[-1]]}")
    return ("les " + "s, les ".join(JOURS_NOMS[j] for j in jours[:-1])
            + "s et les " + JOURS_NOMS[jours[-1]] + "s")


def _phrases_point(point, creneaux):
    """Une phrase naturelle par point, à partir de ses créneaux :
    « Boutique X ouverte du lundi au vendredi de 8h à 12h et de 14h à
    16h30, le samedi de 8h à 11h », « Marché Y tous les jeudis de 8h à
    12h », « Retirez vos colis Place Z le vendredi soir de 18h30 à 20h ».
    Les jours partageant les mêmes plages horaires sont regroupés."""
    # Par jour : plages (début, fin) triées ; signature = plages du jour
    par_jour = {}
    for c in creneaux:
        par_jour.setdefault(c.jour, []).append(
            (c.heure_debut, c.heure_fin, c.frequence))
    groupes = {}
    for jour, plages in par_jour.items():
        signature = tuple(sorted((d, f) for d, f, _ in plages))
        groupes.setdefault(signature, {"jours": [], "freqs": []})
        groupes[signature]["jours"].append(jour)
        groupes[signature]["freqs"].extend(
            f for *_, f in plages)
    est_marche = (point is not None
                  and point.type_point == PointLivraison.Type.MARCHE)
    parties = []
    for signature, groupe in groupes.items():
        texte = (_phrase_jours_pluriel(groupe["jours"]) if est_marche
                 else _phrase_jours(groupe["jours"]))
        # « soir » si toutes les plages commencent à 17h ou plus tard
        if all(d.hour >= 17 for d, _ in signature):
            texte += " soir"
        plages_txt = " et ".join(
            f"de {_heure_courte(d)} à {_heure_courte(f)}"
            for d, f in signature)
        partie = f"{texte} {plages_txt}"
        freqs = set(groupe["freqs"])
        if freqs and freqs != {CreneauLivraison.Frequence.HEBDO}:
            libelles = [dict(CreneauLivraison.Frequence.choices)[fr]
                        .lower() for fr in freqs]
            partie += " (" + ", ".join(libelles) + ")"
        parties.append(partie)
    horaires = ", ".join(parties)
    if point is None:
        return f"📍 Retirez vos colis sur place {horaires}"
    if point.type_point == PointLivraison.Type.BOUTIQUE:
        return (f"🏪 {point.nom} ({point.ville}) : ouverte {horaires}")
    if est_marche:
        return f"🎪 {point.nom} ({point.ville}) : {horaires}"
    if (point.type_point
            == PointLivraison.Type.EMPLACEMENT):
        return (f"🚚 Emplacement « {point.nom} » ({point.ville}) : "
                f"installé {horaires}")
    return f"📍 Retirez vos colis à « {point.nom} » ({point.ville}) {horaires}"


def _phrases_livraison(exploitant):
    """Bandeau des livraisons du dashboard : un message par point
    (boutique, marché, point de livraison), créneaux regroupés."""
    phrases = []
    points = exploitant.points_livraison.prefetch_related("creneaux") \
        .order_by("ville", "nom")
    for point in points:
        creneaux = list(point.creneaux.all())
        if creneaux:
            phrases.append(_phrases_point(point, creneaux))
    sans_point = list(exploitant.creneaux
                      .filter(point_livraison__isnull=True))
    if sans_point:
        phrases.append(_phrases_point(None, sans_point))
    return phrases


def _calendrier_recoltes(exploitant):
    """Vue calendaire hebdomadaire des récoltes (dashboard) : les 8
    prochaines semaines, chacune reliée à sa semaine de récolte si elle
    existe (publiée ou brouillon), sinon à la création."""
    aujourd_hui = timezone.localdate()
    lundi_courant = aujourd_hui - datetime.timedelta(
        days=aujourd_hui.weekday())
    semaines = (SemaineRecolte.objects
                .filter(exploitant=exploitant,
                        lundi__gte=lundi_courant
                        - datetime.timedelta(days=7))
                .annotate(nb_lignes=Count("lignes")))
    par_lundi = {s.lundi: s for s in semaines}
    calendrier = []
    for i in range(8):
        lundi = lundi_courant + datetime.timedelta(weeks=i)
        s = par_lundi.get(lundi)
        calendrier.append({
            "lundi": lundi,
            "dimanche": lundi + datetime.timedelta(days=6),
            "semaine": s,
            "nb_lignes": s.nb_lignes if s else 0,
            "passe": lundi < lundi_courant,
            # Code couleur calendrier : bleu passé, vert semaine
            # courante, orange à venir (dashboard + vitrine publique).
            "etat": ("passe" if lundi < lundi_courant
                     else "courante" if lundi == lundi_courant
                     else "avenir"),
        })
    return calendrier


@login_required
@exploitant_requis
def dashboard(request):
    """Page centrale du maraîcher : rubriques à gauche, aperçu de la
    vitrine publique en direct à droite, hero météo et bandeau des
    créneaux de livraison (jour + horaires). Produits rangés par
    catégorie, éditables sur place (libellé, unité, prix)."""
    exploitant = exploitant_actif(request)
    if espace_actif(request) is None and exploitant is not None:
        # Accès direct au dashboard depuis le mode Localien : on
        # repasse en mode espace pro pour la cohérence des menus.
        request.session["mppl_espace_actif"] = exploitant.pk
    produits = (exploitant.produits.filter(actif=True)
                .select_related("categorie", "origine_standard")
                .order_by("categorie__position", "categorie__nom",
                          "position", "nom"))
    groupes, ordre = {}, []
    for p in produits:
        cat = p.categorie
        if cat not in groupes:
            groupes[cat] = []
            ordre.append(cat)
        groupes[cat].append(p)
    paires = [(cat, groupes[cat]) for cat in ordre]
    return render(request, "portal/pro/dashboard.html", {
        "exploitant": exploitant,
        "est_proprietaire": hasattr(request.user, "exploitant"),
        "paires": paires,
        "nb_produits": len(produits),
        "categories": list(Categorie.objects.filter(exploitant=exploitant)
                           .order_by("position", "nom")),
        "unite_choices": Produit.Unite.choices,
        "meteo": meteo_synthese(exploitant),
        "semaine": SemaineRecolte.objects.filter(exploitant=exploitant)
                   .order_by("-lundi").first(),
        "semaines": list(SemaineRecolte.objects
                         .filter(exploitant=exploitant)
                         .annotate(nb_lignes=Count("lignes"))
                         .order_by("-lundi")[:6]),
        "calendrier": _calendrier_recoltes(exploitant),
        "points": exploitant.points_livraison.all(),
        "creneaux": exploitant.creneaux.select_related("point_livraison"),
        "phrases_livraison": _phrases_livraison(exploitant),
        "commandes_attente": exploitant.commandes
                             .filter(statut=Commande.Statut.NOUVELLE)
                             .order_by("-creee_le")[:10],
        "paniers_en_cours": exploitant.paniers
                            .exclude(statut=Panier.Statut.RECU).count(),
    })


@login_required
@exploitant_requis
@proprietaire_requis
def product_list(request):
    """Page « Produits » dédiée (bandeau pro → Gestion → Produits) :
    édition complète du catalogue — libellé, unité, prix, ordre,
    catégories, ajout/retrait en lot — pendant que le dashboard ne
    garde que la gestion des catégories et le déplacement des
    produits entre catégories."""
    exploitant = exploitant_actif(request)
    produits = (exploitant.produits.filter(actif=True)
                .select_related("categorie", "origine_standard")
                .order_by("categorie__position", "categorie__nom",
                          "position", "nom"))
    groupes, ordre = {}, []
    for p in produits:
        cat = p.categorie
        if cat not in groupes:
            groupes[cat] = []
            ordre.append(cat)
        groupes[cat].append(p)
    paires = [(cat, groupes[cat]) for cat in ordre]
    return render(request, "portal/pro/produits.html", {
        "exploitant": exploitant,
        "paires": paires,
        "categories": list(Categorie.objects.filter(exploitant=exploitant)
                           .order_by("position", "nom")),
        "unite_choices": Produit.Unite.choices,
    })


@login_required
@exploitant_requis
@proprietaire_requis
def produit_creer(request):
    exploitant = exploitant_actif(request)
    if request.method == "POST":
        form = ProduitForm(request.POST, request.FILES, exploitant=exploitant)
        if form.is_valid():
            produit = form.save(commit=False)
            produit.exploitant = exploitant
            produit.emoji = produit.emoji or emoji_pour_nom(produit.nom)
            _enregistrer_image_externe(produit,
                                        request.POST.get("image_externe", ""))
            produit.save()
            messages.success(request, f"Produit « {produit.nom} » ajouté.")
            return redirect("portal:product_list")
    else:
        form = ProduitForm(exploitant=exploitant)
    return render(request, "portal/pro/product_form.html",
                  {"form": form, "titre": "Ajouter un produit",
                   "categories_url": "portal:categories_manage"})


@login_required
@exploitant_requis
@proprietaire_requis
def produit_modifier(request, pk):
    produit = get_object_or_404(Produit, pk=pk,
                                exploitant=exploitant_actif(request))
    if request.method == "POST":
        form = ProduitForm(request.POST, request.FILES, instance=produit,
                           exploitant=exploitant_actif(request))
        if form.is_valid():
            produit = form.save(commit=False)
            _enregistrer_image_externe(produit,
                                        request.POST.get("image_externe", ""))
            produit.save()
            messages.success(request, "Produit mis à jour.")
            return redirect("portal:product_list")
    else:
        form = ProduitForm(instance=produit,
                           exploitant=exploitant_actif(request))
    return render(request, "portal/pro/product_form.html",
                  {"form": form, "titre": "Modifier le produit",
                   "categories_url": "portal:categories_manage"})


@login_required
@exploitant_requis
def produit_edition_rapide(request):
    """Mode édition du dashboard « Mes produits » : libellé, unité et prix
    modifiés en place, ET ergonomie complète — ajout de produit, ajout
    de catégorie, reclassement des produits (▲▼, changement de
    catégorie) et des catégories, sans quitter la page."""
    exploitant = exploitant_actif(request)

    def _produits_de_la_categorie(categorie):
        qs = exploitant.produits.filter(actif=True)
        if categorie:
            qs = qs.filter(categorie=categorie)
        else:
            qs = qs.filter(categorie__isnull=True)
        return list(qs.order_by("position", "nom"))

    # Page de retour après l'action : la page « Produits » dédiée
    # (retour=produits) ou le dashboard (défaut).
    destination = ("portal:product_list"
                   if request.POST.get("retour", "") == "produits"
                   else "portal:dashboard")

    def _voisin(liste, produit, sens):
        """Produit à échanger avec `produit` dans l'ordre affiché."""
        index = next((i for i, p in enumerate(liste) if p.pk == produit.pk),
                     None)
        if index is None:
            return None
        voisin = index - 1 if sens == "haut" else index + 1
        if 0 <= voisin < len(liste):
            return liste[voisin]
        return None

    if request.method == "POST":
        # Actions de gestion : renommer/supprimer une catégorie,
        # retirer un ou plusieurs produits du catalogue. Le pk est
        # porté par la valeur du bouton (« action:pk »).
        action = request.POST.get("action", "")
        nature_action, _, cible_pk = action.partition(":")

        def _cible_categorie():
            try:
                pk = int(cible_pk)
            except ValueError:
                return None
            return Categorie.objects.filter(pk=pk,
                                            exploitant=exploitant).first()

        if nature_action == "categorie_renommer":
            cat = _cible_categorie()
            if cat is None:
                messages.error(request, "Catégorie introuvable.")
                return redirect(destination)
            nom = request.POST.get(f"nom_cat_{cat.pk}", "").strip()
            if nom:
                cat.nom = nom[:80]
                cat.save()
                messages.success(request, f"Catégorie renommée « {cat.nom} ».")
            else:
                messages.error(request, "Nom de catégorie vide.")
            return redirect(destination)
        if nature_action == "categorie_supprimer":
            cat = _cible_categorie()
            if cat is None:
                messages.error(request, "Catégorie introuvable.")
                return redirect(destination)
            nb = cat.produits.count()
            Produit.objects.filter(categorie=cat).update(categorie=None,
                                                         position=0)
            cat.delete()
            message = f"Catégorie « {cat.nom} » supprimée"
            if nb:
                message += (f" — {nb} produit(s) désormais sans catégorie "
                            "(reclassez-les dans la colonne Catégorie).")
            messages.info(request, message + ".")
            return redirect(destination)
        if nature_action == "categorie_ajouter":
            nom = request.POST.get("nouvelle_categorie", "").strip()
            if not nom:
                messages.error(request, "Nom de catégorie vide.")
                return redirect(destination)
            categorie = (Categorie.objects.filter(
                exploitant=exploitant, nom__iexact=nom).first())
            if categorie:
                messages.info(request, f"La catégorie « {categorie.nom} » "
                              "existe déjà.")
                return redirect(destination)
            position = (Categorie.objects.filter(exploitant=exploitant)
                        .aggregate(m=Max("position"))["m"] or 0)
            categorie = Categorie.objects.create(
                exploitant=exploitant, nom=nom[:80], position=position + 1)
            messages.success(request, f"Catégorie « {categorie.nom} » créée.")
            return redirect(destination)
        if nature_action == "produit_retirer":
            try:
                pk = int(cible_pk)
            except ValueError:
                pk = None
            produit = (Produit.objects.filter(pk=pk,
                                              exploitant=exploitant).first()
                       if pk else None)
            if produit is None:
                messages.error(request, "Produit introuvable.")
            else:
                produit.actif = False
                produit.save()
                messages.info(request, f"« {produit.nom} » retiré du "
                              "catalogue (l'historique des commandes "
                              "passées est conservé).")
            return redirect(destination)
        if nature_action == "produits_retirer":
            pks = request.POST.getlist("supprimer")
            concernes = Produit.objects.filter(pk__in=pks,
                                               exploitant=exploitant)
            nb = concernes.update(actif=False)
            if nb:
                messages.info(request, f"{nb} produit(s) retiré(s) du "
                              "catalogue (l'historique des commandes est "
                              "conservé).")
            else:
                messages.error(request, "Cochez d'abord les produits à "
                               "retirer.")
            return redirect(destination)

        # ▲▼ : déplacement d'un produit ou d'une catégorie
        mouvement = request.POST.get("mouvement", "")
        if mouvement:
            try:
                nature, pk, sens = mouvement.split(":")
                pk = int(pk)
            except ValueError:
                messages.error(request, "Requête de reclassement invalide.")
                return redirect(destination)
            if nature == "categorie":
                cat = get_object_or_404(Categorie, pk=pk,
                                        exploitant=exploitant)
                voisines = list(Categorie.objects.filter(
                    exploitant=exploitant).order_by("position", "nom"))
                autre = _voisin(voisines, cat, sens)
                if autre:
                    cat.position, autre.position = autre.position, cat.position
                    autre.save()
                    cat.save()
                    messages.success(request, "Catégorie déplacée.")
            else:
                produit = get_object_or_404(Produit, pk=pk,
                                           exploitant=exploitant)
                voisin = _voisin(_produits_de_la_categorie(produit.categorie),
                                 produit, sens)
                if voisin:
                    (produit.position,
                     voisin.position) = voisin.position, produit.position
                    voisin.save()
                    produit.save()
                    messages.success(
                        request, f"« {produit.nom} » déplacé.")
            return redirect(destination)

        # Changement de catégorie d'un produit
        cible = request.POST.get("appliquer_categorie", "")
        if cible:
            produit = get_object_or_404(Produit, pk=cible,
                                        exploitant=exploitant)
            cat_pk = request.POST.get(f"categorie_cible_{produit.pk}", "")
            if not cat_pk:
                produit.categorie = None
                produit.position = 0
                produit.save()
                messages.info(request, f"« {produit.nom} » placé hors "
                               "catégorie.")
            else:
                cat = get_object_or_404(Categorie, pk=cat_pk,
                                        exploitant=exploitant)
                produit.categorie = cat
                dernier = _produits_de_la_categorie(cat)
                produit.position = (max((p.position for p in dernier),
                                        default=0) + 1)
                produit.save()
                messages.success(request, f"« {produit.nom} » déplacé dans "
                                 f"« {cat.nom} ».")
            return redirect(destination)

        # ➕ Ajout d'un produit (avec catégorie nouvelle ou existante)
        if request.POST.get("action") == "produit_ajouter":
            nom = request.POST.get("nouveau_nom", "").strip()
            unite = request.POST.get("nouveau_unite", "").strip()
            cat_pk = request.POST.get("nouvelle_categorie", "").strip()
            nouvelle_cat = request.POST.get("nom_nouvelle_categorie",
                                           "").strip()
            brut_prix = request.POST.get("nouveau_prix", "").strip()
            erreurs = []
            prix = None
            if not nom:
                erreurs.append("Nom du produit requis.")
            if unite not in Produit.Unite.values:
                erreurs.append("Unité inconnue.")
            if brut_prix:
                try:
                    prix = Decimal(brut_prix)
                except InvalidOperation:
                    erreurs.append("Prix invalide.")
            categorie = None
            if nouvelle_cat:
                categorie = (Categorie.objects.filter(
                    exploitant=exploitant, nom__iexact=nouvelle_cat).first())
                if not categorie:
                    position = (Categorie.objects.filter(
                        exploitant=exploitant)
                        .aggregate(m=Max("position"))["m"] or 0)
                    categorie = Categorie.objects.create(
                        exploitant=exploitant, nom=nouvelle_cat[:80],
                        position=position + 1)
            elif cat_pk:
                categorie = get_object_or_404(Categorie, pk=cat_pk,
                                              exploitant=exploitant)
            if erreurs:
                messages.error(request, " ".join(erreurs))
            else:
                position = (max(
                    (p.position
                     for p in _produits_de_la_categorie(categorie)),
                    default=0) + 1)
                produit = Produit.objects.create(
                    exploitant=exploitant, nom=nom[:150], categorie=categorie,
                    unite_vente=unite, prix=prix, position=position,
                    emoji=emoji_pour_nom(nom[:150]))
                messages.success(request, f"Produit « {produit.nom} » "
                                 "ajouté.")
            return redirect(destination)

        # Enregistrement en masse : libellé, unité, prix
        erreurs, modifies = [], 0
        for produit in exploitant.produits.filter(actif=True):
            if f"nom_{produit.pk}" not in request.POST:
                continue
            nom = request.POST.get(f"nom_{produit.pk}", "").strip()
            unite = request.POST.get(f"unite_{produit.pk}", "").strip()
            brut_prix = request.POST.get(f"prix_{produit.pk}", "").strip()
            if not nom:
                erreurs.append(f"« {produit.nom} » : nom vide, non modifié.")
                continue
            if unite not in Produit.Unite.values:
                erreurs.append(f"« {nom} » : unité inconnue, non modifié.")
                continue
            prix_cible = None
            if brut_prix:
                try:
                    prix_cible = Decimal(brut_prix)
                except InvalidOperation:
                    erreurs.append(f"« {nom} » : prix invalide, non modifié.")
                    continue
            if (nom != produit.nom or unite != produit.unite_vente
                    or prix_cible != produit.prix):
                produit.nom = nom[:150]
                produit.unite_vente = unite
                produit.prix = prix_cible
                produit.save()
                modifies += 1
        if erreurs:
            messages.error(request, " ".join(erreurs))
        if modifies:
            messages.success(request, f"{modifies} produit(s) mis à jour.")
        elif not erreurs:
            messages.info(request, "Aucune modification à enregistrer.")
    return redirect(destination)


@login_required
@exploitant_requis
def harvest_list(request):
    """Toutes les récoltes de l'exploitant (fréquence libre : hebdo,
    moins souvent… c'est lui qui choisit). Publication / dépublication
    en un clic (impact immédiat sur la vitrine), suppression possible."""
    exploitant = exploitant_actif(request)
    today = timezone.localdate()
    lundi_courant = today - datetime.timedelta(days=today.weekday())

    if request.method == "POST":
        semaine = get_object_or_404(SemaineRecolte,
                                    pk=request.POST.get("pk"),
                                    exploitant=exploitant)
        action = request.POST.get("action")
        if action == "publier":
            semaine.publiee = True
            semaine.save()
            messages.success(request, "Récolte du "
                             + semaine.lundi.strftime("%d/%m/%Y")
                             + " publiée : visible sur la vitrine.")
        elif action == "depublier":
            semaine.publiee = False
            semaine.save()
            messages.info(request, "Récolte du "
                          + semaine.lundi.strftime("%d/%m/%Y")
                          + " masquée de la vitrine.")
        elif action == "supprimer":
            lundi_sup = semaine.lundi
            semaine.delete()
            messages.info(request, "Récolte du "
                          + lundi_sup.strftime("%d/%m/%Y") + " supprimée.")
        return redirect("portal:harvest_list")

    semaines = list(SemaineRecolte.objects
                    .filter(exploitant=exploitant)
                    .annotate(nb_lignes=Count("lignes"))
                    .order_by("-lundi"))
    courante, a_venir, passees = None, [], []
    for s in semaines:
        if s.lundi == lundi_courant:
            courante = s
        elif s.lundi > lundi_courant:
            a_venir.append(s)
        else:
            passees.append(s)
    return render(request, "portal/pro/harvest_list.html", {
        "exploitant": exploitant,
        "courante": courante,
        "a_venir": a_venir,
        "passees": passees,
        "lundi_courant": lundi_courant,
    })


@login_required
@exploitant_requis
def harvest_manage(request, semaine_id=None, nouvelle=False):
    """Saisie d'une récolte (ESTIMATIONS) : quantité estimée + prix, produits
    regroupés par catégorie.

    Ergonomie : les valeurs sont pré-remplies depuis la semaine précédente
    (ou la semaine source choisie) ; les lignes reprises sont signalées.
    Le PRIX DE RÉFÉRENCE du catalogue préremplit les prix manquants.
    La date (lundi) est modifiable : déplacer la récolte change la semaine
    affichée sur la vitrine (refus propre si déjà existante).
    """
    exploitant = exploitant_actif(request)
    today = timezone.localdate()
    lundi = today - datetime.timedelta(days=today.weekday())
    semaine = None
    if semaine_id:
        semaine = get_object_or_404(SemaineRecolte, pk=semaine_id,
                                   exploitant=exploitant)

    lundi_defaut = lundi
    if nouvelle and not semaine:
        derniere = (SemaineRecolte.objects.filter(exploitant=exploitant)
                   .order_by("-lundi").first())
        if derniere:
            lundi_defaut = derniere.lundi + datetime.timedelta(days=7)

    if request.method == "POST":
        try:
            lundi_saisi = datetime.date.fromisoformat(
                request.POST.get("lundi") or lundi.isoformat())
        except ValueError:
            lundi_saisi = lundi
        if semaine is not None and lundi_saisi != semaine.lundi:
            autre = (SemaineRecolte.objects
                     .filter(exploitant=exploitant, lundi=lundi_saisi)
                     .exclude(pk=semaine.pk).first())
            if autre:
                messages.error(
                    request, "Une récolte existe déjà pour la semaine du "
                    + lundi_saisi.strftime("%d/%m/%Y")
                    + " : elle a été ouverte à la place.")
                return redirect("portal:harvest_manage", autre.pk)
            semaine.lundi = lundi_saisi
            semaine.save()
        if semaine is None:
            semaine, _cree = SemaineRecolte.objects.get_or_create(
                exploitant=exploitant,
                lundi=lundi_saisi,
                defaults={"note": request.POST.get("note", "")})
        semaine.note = request.POST.get("note", "")
        semaine.publiee = bool(request.POST.get("publiee"))
        semaine.save()
        for produit in exploitant.produits.filter(actif=True):
            qty = request.POST.get(f"qty_{produit.pk}", "").strip()
            prix = request.POST.get(f"price_{produit.pk}", "").strip()
            if not qty or not prix:
                continue
            try:
                qty, prix = Decimal(qty), Decimal(prix)
            except InvalidOperation:
                continue
            LigneRecolte.objects.update_or_create(
                recolte=semaine, produit=produit,
                defaults={"quantite_estimee": qty, "prix_unitaire": prix})
        for ligne in semaine.lignes.all():
            if f"qty_{ligne.produit_id}" not in request.POST:
                ligne.delete()
        messages.success(request, "Récolte du "
                         + semaine.lundi.strftime("%d/%m/%Y")
                         + " enregistrée.")
        return redirect("portal:harvest_list")

    # ---- Pré-remplissage : semaine source des valeurs reprises ----
    source = None
    if request.method == "GET":
        copier = request.GET.get("copier", "").strip()
        if copier:
            source = (SemaineRecolte.objects
                      .filter(exploitant=exploitant, pk=copier).first())
        if source is None:
            reference = semaine.lundi if semaine else lundi_defaut
            source = (SemaineRecolte.objects
                      .filter(exploitant=exploitant, lundi__lt=reference)
                      .order_by("-lundi").first())
        if source is None:
            source = (SemaineRecolte.objects
                      .filter(exploitant=exploitant)
                      .exclude(pk=semaine.pk if semaine else -1)
                      .order_by("-lundi").first())

    valeurs = {}   # produit_id -> (quantite, prix, reprise)
    if semaine:
        for l in semaine.lignes.all():
            valeurs[l.produit_id] = (l.quantite_estimee, l.prix_unitaire,
                                     False)
    if source and source.pk != (semaine.pk if semaine else None):
        for l in source.lignes.all():
            if l.produit_id not in valeurs:
                valeurs[l.produit_id] = (l.quantite_estimee,
                                         l.prix_unitaire, True)

    # ---- Produits regroupés par catégorie (position de l'exploitant) ----
    produits = (exploitant.produits.filter(actif=True)
                .select_related("categorie", "origine_standard")
                .order_by("categorie__position", "categorie__nom", "nom"))
    groupes, ordre = {}, []
    for p in produits:
        nom_cat = p.categorie.nom if p.categorie else "Sans catégorie"
        if nom_cat not in groupes:
            groupes[nom_cat] = []
            ordre.append(nom_cat)
        v = valeurs.get(p.pk)
        # Prix de la ligne de récolte, sinon prix de RÉFÉRENCE du
        # catalogue (saisi à l'import/création) : préremplit la colonne
        # prix, reste éditable à cet endroit.
        prix_affiche = (v[1] if v and v[1] is not None else None) or p.prix
        groupes[nom_cat].append({
            "produit": p,
            "qty": v[0] if v else None,
            "price": prix_affiche,
            "reprise": bool(v and v[2]),
            "step": "0.01" if p.unite_vente == "KG" else "1",
        })
    paires = [(nom, groupes[nom]) for nom in ordre]

    if semaine:
        lundi_defaut = semaine.lundi
    autres = (SemaineRecolte.objects.filter(exploitant=exploitant)
              .exclude(pk=semaine.pk if semaine else -1)
              .order_by("-lundi"))
    return render(request, "portal/pro/harvest_form.html", {
        "semaine": semaine,
        "source": source if source and not semaine else None,
        "autres": autres,
        "paires": paires,
        "lundi_defaut": lundi_defaut,
    })


def _groupes_lignes(lignes):
    """Lignes de commande (ou de panier) triées et regroupées par
    catégorie du produit — même présentation que la vitrine :
    [(nom_categorie, [lignes…]), …]."""
    lignes = sorted(lignes, key=lambda l: (
        (l.produit.categorie.position
         if l.produit.categorie else 9999) or 9999,
        l.produit.categorie.nom if l.produit.categorie else "zz",
        l.produit.nom))
    groupes = []
    for ligne in lignes:
        nom = (ligne.produit.categorie.nom
               if ligne.produit.categorie else "Sans catégorie")
        if not groupes or groupes[-1][0] != nom:
            groupes.append((nom, []))
        groupes[-1][1].append(ligne)
    return groupes


def _profils_clients(user_ids):
    """Photos et téléphones des clients concernés, SANS lever l'erreur
    « profil client inexistant » (un compte pro qui commande chez un
    confrère n'a pas de ProfilClient : c'est ce qui provoquait les
    erreurs 500 sur les listes commandes/paniers)."""
    profils = {p.user_id: p for p in ProfilClient.objects.filter(
        user_id__in=user_ids)}
    return ({i: profils[i].photo_url for i in profils
             if profils[i].photo_url},
            {i: profils[i].telephone for i in profils
             if profils[i].telephone})


def _badges_par_jour(objets, champ_statut, statuts):
    """Pour l'en-tête de chaque jour (commandes, paniers) : comptage par
    statut, ordonné, avec libellé — [(statut, nombre, libellé), …]."""
    comptes = {}
    for objet in objets:
        statut = getattr(objet, champ_statut)
        par_statut = comptes.setdefault(getattr(objet, "date_livraison"), {})
        par_statut[statut] = par_statut.get(statut, 0) + 1
    libelles = dict(statuts)
    return {jour: [(statut, par[statut], libelles[statut])
                  for statut, _libelle in statuts if statut in par]
            for jour, par in comptes.items()}


def _notifier_sans_echec(request, panier, type_msg):
    """Notification client qui ne peut JAMAIS faire échouer l'action en
    cours (validation, changement de statut, annulation) : tout échec
    devient un simple message informatif — la commande/le panier sont
    déjà créés à ce stade."""
    try:
        return notifier_client(request, panier, type_msg)
    except Exception as err:
        messages.info(request, "ℹ️ Notification client non envoyée ("
                      + str(err) + "). L'action, elle, est bien "
                      "enregistrée — rien n'est perdu.")
        return False


@login_required
@exploitant_requis
def order_list(request, statut=None):
    exploitant = exploitant_actif(request)
    contexte = _contexte_commandes(
        exploitant, statut, request.GET.get("annulation", "").strip())
    # Vue alternative « calendrier » (?vue=calendrier)
    contexte.update(_contexte_calendrier(request, contexte["commandes"]))
    return render(request, "portal/pro/orders.html", contexte)


def _contexte_calendrier(request, commandes):
    """Vue alternative « calendrier » de la semaine (7 cases), côté
    pro comme côté client : construite à partir des commandes triées
    par date de livraison. Retourne {} si la vue demandée n'est pas
    le calendrier — la page retombe alors sur la liste par jour."""
    if request.GET.get("vue", "liste").strip() != "calendrier":
        return {}
    try:
        ref = datetime.date.fromisoformat(
            request.GET.get("sem", "").strip())
    except ValueError:
        ref = timezone.localdate()
    lundi = ref - datetime.timedelta(days=ref.weekday())
    jours_cal = []
    for i in range(7):
        jour = lundi + datetime.timedelta(days=i)
        jours_cal.append({
            "date": jour,
            "commandes": [c for c in commandes
                          if c.date_livraison == jour],
        })
    return {
        "vue": "calendrier",
        "jours_cal": jours_cal,
        "semaine_debut": lundi,
        "semaine_fin": lundi + datetime.timedelta(days=6),
        "sem_prec": (lundi - datetime.timedelta(days=7)).isoformat(),
        "sem_suiv": (lundi + datetime.timedelta(days=7)).isoformat(),
    }


def _contexte_commandes(exploitant, statut=None, annulation=""):
    """Commandes reçues, avec contact client (e-mail, téléphone, canal
    préféré si le client en a exprimé un). Produits rangés par
    catégorie ; pour les commandes validées, les ajustements faits à
    la validation (contenu du panier) sont affichés. Partagé par la
    page « Commandes » et la rubrique de la page Ventes."""
    # Une commande VALIDÉE vit désormais côté « Paniers » : ici ne
    # restent que les commandes à traiter, refusées et annulées.
    commandes = exploitant.commandes.exclude(
        statut=Commande.Statut.VALIDEE).order_by(
        "-date_livraison", "-creee_le")
    if statut:
        commandes = commandes.filter(statut=statut)
    if annulation in (Commande.AnnulationPar.CLIENT,
                      Commande.AnnulationPar.PRODUCTEUR):
        commandes = commandes.filter(annulee_par=annulation)
    canaux = {p.client_id: p.get_canal_display()
              for p in PreferenceContact.objects.filter(exploitant=exploitant)}
    commandes = list(commandes.prefetch_related(
        "lignes__produit__categorie", "lignes__produit__origine_standard"))
    # Ajustements de la validation : quantités retenues dans le panier
    paniers_valides = {p.commande_id: p for p in Panier.objects.filter(
        commande_id__in=[c.pk for c in commandes],
        exploitant=exploitant).prefetch_related("lignes")}
    ajustements = {cid: {ligne.produit_id: ligne.quantite
                         for ligne in panier.lignes.all()}
                   for cid, panier in paniers_valides.items()}
    photos, telephones = _profils_clients(
        {c.client_id for c in commandes if c.client_id})
    for c in commandes:
        # Panier suivi de la commande (créé à la validation) : horaire
        # du créneau retenu + itinéraire dès que le panier est livré.
        c.panier_suivi = paniers_valides.get(c.pk)
        c.motif_annul = (c.motif_annulation
                         or (c.panier_suivi.motif_annulation
                             if c.panier_suivi else ""))
        c.canal_pref = canaux.get(c.client_id) if c.client_id else None
        c.photo_client = photos.get(c.client_id, "")
        c.tel_client = telephones.get(c.client_id, "")
        c.groupes_lignes = _groupes_lignes(list(c.lignes.all()))
        c.ajustements = ajustements.get(c.pk)
        if c.statut == Commande.Statut.NOUVELLE:
            c.dispos = _dispos_lignes(c, c.lignes.all())
    return {
        "commandes": commandes, "filtre_statut": statut,
        "filtre_annulation": annulation,
        "points": exploitant.points_livraison.all(),
        "today": timezone.localdate(),
        "jours_badges": _badges_par_jour(commandes, "statut",
                                         Commande.Statut.choices),
    }


def _quantite_ajustee(brut, quantite_commandee, produit):
    """Valide une quantité ajustée : Decimal, positive, entière si l'unité
    se vend à la pièce. Retourne (quantite, erreur_ou_None)."""
    if brut == "":
        qty = quantite_commandee
    else:
        try:
            qty = Decimal(brut)
        except InvalidOperation:
            return None, f"« {produit.nom} » : quantité invalide."
    if qty <= 0:
        return None, None  # ligne retirée volontairement
    if (produit.unite_vente in UNITES_ENTIERES
            and qty != qty.to_integral_value()):
        return None, (f"« {produit.nom} » se vend à la pièce : "
                      "quantité entière requise.")
    return qty, None


@login_required
@exploitant_requis
def order_direct_create(request):
    """Saisie directe d'une commande par l'exploitant (issue #2) : au
    téléphone, au marché… La commande est immédiatement validée et le
    panier numéroté créé (contenu ajustable ensuite). Les prix de
    référence du catalogue s'appliquent."""
    exploitant = exploitant_actif(request)
    produits = list(exploitant.produits.filter(actif=True)
                    .select_related("categorie", "origine_standard")
                    .order_by("categorie__position", "nom"))
    points = exploitant.points_livraison.all()
    creneaux = exploitant.creneaux.select_related("point_livraison")

    # Estimations de la récolte publiée la plus récente (mêmes règles
    # que la vitrine) : guide la saisie, l'exploitant reste libre de
    # enregistrer plus (il ajustera à la préparation).
    jour = timezone.localdate()
    lundi_courant = jour - datetime.timedelta(days=jour.weekday())
    semaine = (SemaineRecolte.objects.filter(exploitant=exploitant,
                                             publiee=True,
                                             lundi__lte=lundi_courant)
               .order_by("-lundi").first())
    restes, mode = {}, "catalogue"
    if semaine:
        offres_semaine, mode = _offres_commande(exploitant, semaine)
        restes = {o["produit"].pk: (o["estime"], o["reste"])
                  for o in offres_semaine}
    # Produits regroupés par catégorie (même présentation que la
    # vitrine et la page de commande client).
    groupes_produits, ordre_cats = {}, []
    for p in produits:
        cat = p.categorie
        if cat not in groupes_produits:
            groupes_produits[cat] = []
            ordre_cats.append(cat)
        groupes_produits[cat].append(p)
    paires = [(cat, groupes_produits[cat]) for cat in ordre_cats]

    if request.method == "POST":
        nom_client = request.POST.get("nom_client", "").strip()
        email_client = request.POST.get("email_client", "").strip()
        telephone_client = request.POST.get("telephone_client", "").strip()
        point = exploitant.points_livraison.filter(
            pk=request.POST.get("point_livraison")).first()
        creneau = exploitant.creneaux.filter(
            pk=request.POST.get("creneau")).first()
        try:
            date_livraison = datetime.date.fromisoformat(
                request.POST["date_livraison"])
        except (KeyError, ValueError):
            date_livraison = None
        note = request.POST.get("note", "").strip()

        erreurs = []
        if not nom_client:
            erreurs.append("Nom du client requis.")
        if not email_client and not telephone_client:
            erreurs.append("E-mail ou téléphone requis (identité contact).")
        if (date_livraison is None
                or date_livraison < timezone.localdate()):
            erreurs.append("Date de livraison invalide "
                           "(aujourd'hui ou plus tard).")
        # Un point de livraison est obligatoire pour numéroter le panier :
        # soit celui choisi, soit — s'il n'en existe aucun — un message
        # invitant à en créer un d'abord (menu « Livraison »).
        if point is None:
            if points:
                erreurs.append("Point de livraison requis : "
                               "choisissez un point pour cette commande.")
            else:
                erreurs.append("Aucun point de livraison : créez-en un "
                               "d'abord dans « Livraison » "
                               "(Points & créneaux).")

        lignes, total = [], Decimal("0")
        for produit in produits:
            brut = request.POST.get(f"qty_{produit.pk}", "").strip()
            if not brut:
                continue
            try:
                qty = Decimal(brut)
            except InvalidOperation:
                erreurs.append(f"« {produit.nom} » : quantité invalide.")
                continue
            if qty <= 0:
                continue
            if (produit.unite_vente in UNITES_ENTIERES
                    and qty != qty.to_integral_value()):
                erreurs.append(f"« {produit.nom} » se vend à la pièce : "
                               "quantité entière requise.")
                continue
            if produit.prix is None:
                erreurs.append(f"« {produit.nom} » : aucun prix de "
                               "référence dans le catalogue.")
                continue
            lignes.append((produit, qty, produit.prix))
            total += qty * produit.prix
        if not lignes:
            erreurs.append("Aucun produit commandé.")

        if erreurs:
            messages.error(request, " ".join(erreurs))
        else:
            client = None
            if email_client:
                client = User.objects.filter(
                    email__iexact=email_client).first()
            with transaction.atomic():
                commande = Commande.objects.create(
                    exploitant=exploitant, client=client,
                    nom_client=nom_client[:150],
                    email_client=email_client,
                    telephone_client=telephone_client,
                    point_livraison=point,
                    date_livraison=date_livraison,
                    statut=Commande.Statut.VALIDEE,
                    validee_le=timezone.now(),
                    total=total, saisie_exploitant=True, note=note)
                panier = Panier.objects.create(
                    exploitant=exploitant, client=client,
                    nom_client=nom_client[:150],
                    email_client=email_client,
                    telephone_client=telephone_client,
                    numero=Panier.prochain_numero(
                        exploitant, date_livraison,
                        point_livraison=point),
                    date_livraison=date_livraison, creneau=creneau,
                    point_livraison=point, commande=commande,
                    statut=Panier.Statut.PREPARATION,
                    total=total, note=note)
                for produit, qty, prix in lignes:
                    LigneCommande.objects.create(
                        commande=commande, produit=produit,
                        quantite=qty, prix_unitaire=prix)
                    LignePanier.objects.create(
                        panier=panier, produit=produit,
                        quantite=qty, prix_unitaire=prix)
            messages.success(request, "Commande de " + nom_client
                             + " enregistrée → panier n°"
                             + str(panier.numero) + " créé.")
            _notifier_sans_echec(request, panier, "CONFIRMATION_COMMANDE")
            return redirect("portal:panier_detail", panier.pk)

    return render(request, "portal/pro/order_direct.html", {
        "produits": produits,
        "paires": paires,
        "restes": restes,
        "mode": mode,
        "semaine": semaine,
        "points": points,
        "creneaux": creneaux,
        "date_defaut": timezone.localdate().isoformat(),
    })


@login_required
@exploitant_requis
def order_validate(request, commande_id):
    """Validation / refus d'une commande.

    L'exploitant peut AJUSTER les quantités au moment de valider (0 ou vide =
    retirer la ligne) et laisser un commentaire visible par le client.
    Le panier numéroté est créé avec le contenu ajusté : point de départ
    du contenu livré (DATA_MODEL v0.3). Le client est notifié.
    """
    exploitant = exploitant_actif(request)
    commande = get_object_or_404(Commande, pk=commande_id, exploitant=exploitant)
    if (request.method == "POST"
            and commande.statut == Commande.Statut.NOUVELLE):
        action = request.POST.get("action")
        if action == "validate":
            # Point de livraison obligatoire pour créer le panier numéroté :
            # par défaut celui de la commande, sinon celui choisi au moment
            # de la validation.
            point = commande.point_livraison
            if point is None:
                point = exploitant.points_livraison.filter(
                    pk=request.POST.get("point_livraison")).first()
            if point is None and exploitant.points_livraison.exists():
                messages.error(
                    request, "Un point de livraison est requis pour "
                    "valider : choisissez-en un puis validez à nouveau.")
                return redirect("portal:order_list")
            if point is None:
                messages.error(
                    request, "Aucun point de livraison : créez-en un "
                    "d'abord dans « Livraison » (Points & créneaux).")
                return redirect("portal:order_list")
            ajustees, erreurs, total = [], [], Decimal("0")
            for ligne in commande.lignes.select_related("produit"):
                brut = request.POST.get(f"qty_{ligne.pk}", "").strip()
                qty, erreur = _quantite_ajustee(brut, ligne.quantite,
                                                ligne.produit)
                if erreur:
                    erreurs.append(erreur)
                    continue
                if qty is None:
                    continue  # ligne retirée
                ajustees.append((ligne, qty))
                total += qty * ligne.prix_unitaire
            if erreurs:
                messages.error(request, " ".join(erreurs))
                return redirect("portal:order_list")
            if not ajustees:
                messages.error(
                    request, "Impossible de valider : toutes les lignes "
                    "auraient été retirées.")
                return redirect("portal:order_list")
            with transaction.atomic():
                commande.statut = Commande.Statut.VALIDEE
                commande.validee_le = timezone.now()
                commande.point_livraison = point
                commande.save()
                panier = Panier.objects.create(
                    exploitant=exploitant,
                    client=commande.client,
                    nom_client=commande.nom_client,
                    email_client=commande.email_client,
                    telephone_client=commande.telephone_client,
                    numero=Panier.prochain_numero(
                        exploitant, commande.date_livraison,
                        point_livraison=point),
                    date_livraison=commande.date_livraison,
                    point_livraison=point,
                    commande=commande,
                    statut=Panier.Statut.PREPARATION,
                    total=total,
                    note=request.POST.get("note", "").strip())
                for ligne, qty in ajustees:
                    LignePanier.objects.create(
                        panier=panier, produit=ligne.produit,
                        quantite=qty,
                        prix_unitaire=ligne.prix_unitaire)
            messages.success(
                request, f"Commande #{commande.pk} validée → "
                f"panier n°{panier.numero} créé pour "
                f"{panier.nom_client}.")
            _notifier_sans_echec(request, panier, "CONFIRMATION_COMMANDE")
        elif action == "refuse":
            # Motif de refus proposé à l'exploitant (phrase au choix ou
            # motif libre) : visible par le client, il l'incite à
            # recomposer sa commande pour une autre semaine.
            motif = request.POST.get("motif_refus", "").strip()
            libre = request.POST.get("motif_refus_libre", "").strip()
            if motif == "__libre__":
                motif = libre
            if not motif and libre:
                motif = libre
            if not motif:
                messages.error(
                    request, "Indiquez un motif de refus (phrase proposée "
                    "ou motif libre) : il est visible par le client.")
                return redirect("portal:order_list")
            commande.statut = Commande.Statut.REFUSEE
            commande.motif_refus = motif
            commande.save()
            messages.info(request, f"Commande #{commande.pk} refusée.")
    return redirect("portal:order_list")


@login_required
@exploitant_requis
def panier_list(request):
    exploitant = exploitant_actif(request)
    contexte = _contexte_paniers(
        exploitant,
        request.GET.get("statut", "").strip(),
        request.GET.get("point", "").strip())
    # Vue alternative « calendrier » (?vue=calendrier) : même
    # mécanique que la page Commandes — le choix Liste/Calendrier
    # s'applique aux deux rubriques, filtres conservés.
    contexte.update(_contexte_calendrier(request, contexte["paniers"]))
    return render(request, "portal/pro/paniers.html", contexte)


def _contexte_paniers(exploitant, statut="", point_id=""):
    """Liste des paniers, regroupés visuellement par jour de livraison
    (en-tête du jour : comptage par statut, code couleur associé).
    Partagé par la page « Paniers » et la rubrique de la page Ventes."""
    paniers = (exploitant.paniers
               .select_related("client", "point_livraison", "creneau")
               .prefetch_related("lignes__produit__categorie",
                                 "lignes__produit__origine_standard"))
    if statut in Panier.Statut.values:
        paniers = paniers.filter(statut=statut)
    if point_id:
        paniers = paniers.filter(point_livraison_id=point_id)
    paniers = paniers.order_by("-date_livraison", "numero")
    paniers = list(paniers)
    photos, telephones = _profils_clients(
        {p.client_id for p in paniers if p.client_id})
    for panier in paniers:
        panier.photo_client = photos.get(panier.client_id, "")
        panier.tel_client = telephones.get(panier.client_id, "")
        panier.groupes_lignes = _groupes_lignes(list(panier.lignes.all()))
        panier.dispos = _dispos_lignes(panier, panier.lignes.all())
    return {
        "paniers": paniers,
        "filtre_statut": statut,
        "filtre_point": point_id,
        "points": exploitant.points_livraison.all(),
        "today": timezone.localdate(),
        "jours_badges": _badges_par_jour(paniers, "statut",
                                         Panier.Statut.choices),
    }


@login_required
@exploitant_requis
def ventes(request):
    """🧾 Ventes : UNE page, DEUX rubriques — commandes reçues puis
    paniers, avec les mêmes contenus que les deux pages historiques
    (les filtres détaillés restent sur celles-ci)."""
    exploitant = exploitant_actif(request)
    commandes = _contexte_commandes(exploitant)
    paniers = _contexte_paniers(exploitant)
    contexte = {
        "commandes": commandes["commandes"],
        "jours_badges_commandes": commandes["jours_badges"],
        "filtre_statut_commandes": commandes["filtre_statut"],
        "paniers": paniers["paniers"],
        "jours_badges_paniers": paniers["jours_badges"],
        "filtre_statut_paniers": paniers["filtre_statut"],
        "filtre_point_paniers": paniers["filtre_point"],
        "points": paniers["points"],
        "today": commandes["today"],
    }
    # Vue alternative « calendrier » des commandes (?vue=calendrier) :
    # les paniers restent en liste dessous.
    contexte.update(_contexte_calendrier(request, commandes["commandes"]))
    return render(request, "portal/pro/ventes.html", contexte)


@login_required
@exploitant_requis
def panier_export_csv(request):
    """Export CSV (issue #8). Deux modes :
    - detail (défaut) : ligne par ligne, chaque panier avec son client ;
    - production : récapitulatif par produit des paniers LIVRÉS/REÇUS
      (seule source du décompte de production). Filtre date optionnel."""
    exploitant = exploitant_actif(request)
    date_filter = request.GET.get("date", "").strip()
    mode = request.GET.get("mode", "detail")
    paniers = (exploitant.paniers.select_related("client", "point_livraison")
               .prefetch_related("lignes__produit")
               .order_by("date_livraison", "numero"))
    if date_filter:
        try:
            date_filter = datetime.date.fromisoformat(date_filter).isoformat()
        except ValueError:
            date_filter = ""
        else:
            paniers = paniers.filter(date_livraison=date_filter)
    paniers = list(paniers)

    tampon = io.StringIO()
    writer = csv.writer(tampon, delimiter=";")
    if mode == "production":
        writer.writerow(["Produit", "Unite", "Quantite livree",
                         "Total (EUR)", "Nb paniers"])
        agg = {}
        for panier in paniers:
            if panier.statut not in (Panier.Statut.LIVRE,
                                     Panier.Statut.RECU):
                continue
            for ligne in panier.lignes.all():
                e = agg.setdefault(ligne.produit_id,
                                   {"produit": ligne.produit,
                                    "qte": Decimal("0"),
                                    "total": Decimal("0"),
                                    "paniers": set()})
                e["qte"] += ligne.quantite
                e["total"] += ligne.quantite * ligne.prix_unitaire
                e["paniers"].add(panier.pk)
        for e in sorted(agg.values(), key=lambda x: x["produit"].nom):
            writer.writerow([
                e["produit"].nom, e["produit"].unite_courte,
                str(e["qte"]).replace(".", ","),
                str(e["total"]).replace(".", ","),
                len(e["paniers"])])
    else:
        writer.writerow(["Panier", "Date", "Statut", "Client", "E-mail",
                         "Telephone", "Point de livraison",
                         "Produit", "Unite", "Quantite livree",
                         "Prix unitaire (EUR)", "Total ligne (EUR)",
                         "Total panier (EUR)"])
        for panier in paniers:
            lignes = list(panier.lignes.all())
            if not lignes:
                writer.writerow([f"n°{panier.numero}",
                                 panier.date_livraison.strftime("%d/%m/%Y"),
                                 panier.get_statut_display(),
                                 panier.nom_client, panier.email_client,
                                 panier.telephone_client,
                                 panier.point_livraison.nom
                                 if panier.point_livraison else "",
                                 "", "", "", "", "",
                                 str(panier.total).replace(".", ",")])
            for ligne in lignes:
                writer.writerow([
                    f"n°{panier.numero}",
                    panier.date_livraison.strftime("%d/%m/%Y"),
                    panier.get_statut_display(),
                    panier.nom_client, panier.email_client,
                    panier.telephone_client,
                    panier.point_livraison.nom
                    if panier.point_livraison else "",
                    ligne.produit.nom,
                    ligne.produit.unite_courte,
                    str(ligne.quantite).replace(".", ","),
                    str(ligne.prix_unitaire).replace(".", ","),
                    str(ligne.total_ligne()).replace(".", ","),
                    str(panier.total).replace(".", ",")])

    nom = "paniers_" + (date_filter or "tous") + "_" + mode + ".csv"
    reponse = HttpResponse("\ufeff" + tampon.getvalue(),
                           content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="{nom}"'
    return reponse


@login_required
@exploitant_requis
def panier_detail(request, panier_id):
    """Préparation du panier : ajustement du contenu EFFECTIVEMENT livré,
    comparé côte à côte aux quantités souhaitées par le client, avec
    commentaire visible par le client. Chaque changement de statut notifie
    le client (panier prêt, livraison faite) selon son canal préféré."""
    exploitant = exploitant_actif(request)
    panier = get_object_or_404(Panier, pk=panier_id, exploitant=exploitant)
    verrouille = panier.statut in (Panier.Statut.LIVRE,
                                   Panier.Statut.RECU,
                                   Panier.Statut.ANNULE)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "lignes":
            if verrouille:
                messages.warning(
                    request, "🔒 Panier n°%d livré : le contenu livré est "
                    "verrouillé (lecture seule). Repassez le statut à "
                    "« Prêt » ou « En préparation » pour le modifier."
                    % panier.numero)
                return redirect("portal:panier_detail", panier.pk)
            ajustes, erreurs, total = {}, [], Decimal("0")
            for ligne in panier.lignes.select_related("produit"):
                brut = request.POST.get(f"qty_{ligne.pk}", "").strip()
                if brut == "":
                    ajustes[ligne.pk] = ligne.quantite  # vide = conserver
                    continue
                try:
                    qty = Decimal(brut)
                except InvalidOperation:
                    erreurs.append(f"« {ligne.produit.nom} » : quantité invalide.")
                    continue
                if qty <= 0:
                    ajustes[ligne.pk] = None
                    continue
                if (ligne.produit.unite_vente in UNITES_ENTIERES
                        and qty != qty.to_integral_value()):
                    erreurs.append(f"« {ligne.produit.nom} » se vend à la "
                                   "pièce : quantité entière requise.")
                    continue
                ajustes[ligne.pk] = qty
            pid = request.POST.get("produit_ajout", "").strip()
            qadd = request.POST.get("qty_ajout", "").strip()
            ajout = None
            if pid and qadd:
                produit = exploitant.produits.filter(
                    pk=pid, actif=True).first()
                try:
                    qadd = Decimal(qadd)
                except InvalidOperation:
                    produit = None
                if produit and qadd > 0:
                    if (produit.unite_vente in UNITES_ENTIERES
                            and qadd != qadd.to_integral_value()):
                        erreurs.append(f"« {produit.nom} » se vend à la "
                                       "pièce : quantité entière requise.")
                    else:
                        ajout = (produit, qadd)
            if erreurs:
                messages.error(request, " ".join(erreurs))
                return redirect("portal:panier_detail", panier.pk)
            with transaction.atomic():
                for ligne in panier.lignes.select_related("produit"):
                    qty = ajustes.get(ligne.pk, ligne.quantite)
                    if qty is None:
                        ligne.delete()
                        continue
                    ligne.quantite = qty
                    ligne.save()
                    total += qty * ligne.prix_unitaire
                if ajout:
                    produit, qadd = ajout
                    prix = produit.prix or Decimal("0")
                    LignePanier.objects.create(
                        panier=panier, produit=produit,
                        quantite=qadd, prix_unitaire=prix)
                    total += qadd * prix
                panier.total = total
                panier.note = request.POST.get("note", "").strip()
                panier.save()
            messages.success(
                request, f"Panier n°{panier.numero} mis à jour "
                f"({panier.total} €).")

        elif action == "statut":
            nouveau = request.POST.get("statut", "")
            if nouveau in Panier.Statut.values:
                panier.statut = nouveau
                panier.save()
                messages.success(
                    request, f"Panier n°{panier.numero} : "
                    f"{panier.get_statut_display()}.")
                if panier.statut == Panier.Statut.PRET:
                    _notifier_sans_echec(request, panier, "PANIER_PRET")
                elif panier.statut in (Panier.Statut.LIVRE,
                                       Panier.Statut.RECU):
                    _notifier_sans_echec(request, panier, "LIVRAISON_FAITE")

        elif action == "annuler":
            if panier.statut != Panier.Statut.PREPARATION:
                messages.error(
                    request, "Seul un panier en préparation peut être "
                    "annulé.")
            else:
                panier.statut = Panier.Statut.ANNULE
                panier.motif_annulation = (request.POST.get(
                    "motif", "").strip() or "Annulé par le producteur.")
                panier.save()
                if panier.commande_id:
                    panier.commande.statut = Commande.Statut.ANNULEE
                    panier.commande.annulee_par = (
                        Commande.AnnulationPar.PRODUCTEUR)
                    panier.commande.save()
                    messages.info(
                        request, f"Panier n°{panier.numero} annulé : la "
                        "commande repasse « Annulée » — le client peut la "
                        "recommander depuis « Mes commandes » (quantités, "
                        "date et point de livraison repris).")
                else:
                    messages.info(
                        request, f"Panier n°{panier.numero} annulé "
                        "(commande saisie directement, sans compte client).")
                _notifier_sans_echec(request, panier, "PANIER_ANNULE")

        return redirect("portal:panier_detail", panier.pk)

    # Comparatif souhaité (client) / livré, ligne par ligne
    souhaitees = {}
    if panier.commande_id:
        souhaitees = {lc.produit_id: lc.quantite
                     for lc in panier.commande.lignes.all()}
    lignes = list(panier.lignes.select_related(
        "produit__categorie", "produit__origine_standard"))
    lignes.sort(key=lambda l: (
        (l.produit.categorie.position
         if l.produit.categorie else 9999) or 9999,
        l.produit.categorie.nom if l.produit.categorie else "zz",
        l.produit.nom))
    rows = []
    dispos = _dispos_lignes(panier, lignes)
    for ligne in lignes:
        souh = souhaitees.get(ligne.produit_id)
        dispo = dispos.get(ligne.pk)
        rows.append({
            "ligne": ligne,
            "souhaite": souh,
            "ajuste": souh is not None and souh != ligne.quantite,
            "step": "0.01" if ligne.produit.unite_vente == "KG" else "1",
            "dispo": dispo["dispo"] if dispo else None,
            "depasse": bool(dispo and dispo["depasse"]),
        })
    if panier.client_id:
        photos, telephones = _profils_clients([panier.client_id])
    else:
        photos, telephones = {}, {}
    return render(request, "portal/pro/panier_detail.html", {
        "panier": panier,
        "rows": rows,
        "photo_client": photos.get(panier.client_id, ""),
        "tel_client": telephones.get(panier.client_id, ""),
        "verrouille": verrouille,
        "produits": (exploitant.produits.filter(actif=True)
                     .select_related("origine_standard")),
    })


@login_required
@exploitant_requis
def clients_suivi(request):
    """Suivi « Mes clients » : regroupement par identité contact (compte
    client ou nom + e-mail/téléphone), cumul des commandes, paniers et
    chiffre d'affaires, canal de contact préféré."""
    exploitant = exploitant_actif(request)
    q = request.GET.get("q", "").strip().lower()
    registre = {}

    def enregistrer(client_id, nom, email, tel):
        cle = ("u%d" % client_id if client_id
               else "c:%s|%s" % ((nom or "").lower(), (email or "").lower()))
        if cle not in registre:
            registre[cle] = {
                "nom": nom, "email": email or "", "telephone": tel or "",
                "client_id": client_id,
                "nb_commandes": 0, "nb_paniers": 0,
                "total": Decimal("0"), "derniere": None,
            }
        return registre[cle]

    for c in exploitant.commandes.all():
        e = enregistrer(c.client_id, c.nom_client, c.email_client,
                        c.telephone_client)
        e["nb_commandes"] += 1
        if not e["derniere"] or c.date_livraison > e["derniere"]:
            e["derniere"] = c.date_livraison
    for p in exploitant.paniers.all():
        e = enregistrer(p.client_id, p.nom_client, p.email_client,
                        p.telephone_client)
        e["nb_paniers"] += 1
        e["total"] += p.total
        if not e["derniere"] or p.date_livraison > e["derniere"]:
            e["derniere"] = p.date_livraison

    canaux = {pc.client_id: pc for pc in
              PreferenceContact.objects.filter(exploitant=exploitant)}
    rows = []
    for e in registre.values():
        pref = canaux.get(e["client_id"]) if e["client_id"] else None
        e["canal"] = pref.get_canal_display() if pref else "E-mail"
        rows.append(e)
    rows.sort(key=lambda e: (-e["total"], e["nom"].lower()))
    if q:
        rows = [e for e in rows
                if q in e["nom"].lower() or q in e["email"].lower()
                or q in e["telephone"].lower()]
    return render(request, "portal/pro/clients.html",
                  {"rows": rows, "q": request.GET.get("q", "")})


def _latlon(brut):
    """Latitude/longitude saisie ou reçue du widget carte : None si vide
    ou invalide (la position reste optionnelle)."""
    try:
        valeur = float((brut or "").strip().replace(",", "."))
        return valeur if -180 <= valeur <= 180 else None
    except (TypeError, ValueError):
        return None


@login_required
@exploitant_requis
def cartes_manage(request):
    """Cartes / boutique stable : traiteurs, foodtrucks et producteurs
    en mode boutique (fromager, apiculteur, conserverie, micro-brasseur)
    composent des cartes versionnées — brouillons, archives
    republiables — dont UNE SEULE est active : la vitrine publique
    l'affiche en plus de l'encart de la semaine. Les lignes reprennent
    les produits du catalogue (de référence ou perso) ou restent
    libres (plat du jour, menu…)."""
    exploitant = exploitant_actif(request)
    if not exploitant.a_carte_boutique:
        messages.info(request, "Les cartes / boutiques concernent les "
                      "traiteurs, restaurants, foodtrucks et producteurs en mode "
                      "boutique (fromager, apiculteur, conserverie, "
                      "micro-brasseur, éleveur).")
        return redirect("portal:dashboard")

    if request.method == "POST":
        action = request.POST.get("action", "")
        carte = Carte.objects.filter(
            exploitant=exploitant,
            pk=request.POST.get("carte_id") or 0).first()
        if action == "creer":
            nom = request.POST.get("nom", "").strip()
            if nom:
                Carte.objects.create(exploitant=exploitant, nom=nom)
                messages.success(request, "Carte « " + nom + " » créée "
                                 "en brouillon : ajoutez vos lignes, "
                                 "puis publiez-la.")
            else:
                messages.error(request, "Donnez un nom à la carte.")
        elif carte is None:
            messages.error(request, "Carte introuvable.")
        elif action == "activer":
            carte.activer()
            messages.success(request, "Carte « " + carte.nom + " » "
                             "publiée : elle s'affiche sur votre "
                             "vitrine (la précédente est archivée).")
        elif action == "archiver":
            carte.statut = Carte.Statut.ARCHIVEE
            carte.save(update_fields=["statut", "maj_le"])
            messages.info(request, "Carte « " + carte.nom + " » "
                          "archivée — republiez-la quand vous voulez.")
        elif action == "dupliquer":
            copie = Carte.objects.create(exploitant=exploitant,
                                         nom=carte.nom + " (copie)")
            for ligne in carte.lignes.all():
                ligne.pk = None
                ligne.carte_id = copie.pk
                ligne.save()
            messages.success(request, "Copie créée en brouillon : "
                             "modifiez-la puis publiez-la.")
        elif action == "supprimer":
            nom = carte.nom
            carte.delete()
            messages.info(request, "Carte « " + nom + " » supprimée.")
        elif action == "ajouter_ligne":
            produit = Produit.objects.filter(
                exploitant=exploitant,
                pk=request.POST.get("produit_id") or 0).first()
            nom_libre = request.POST.get("nom_libre", "").strip()
            if not produit and not nom_libre:
                messages.error(request, "Choisissez un produit du "
                               "catalogue OU saisissez un nom libre.")
            else:
                brut = request.POST.get("prix", "").strip().replace(",", ".")
                prix = None
                if brut:
                    try:
                        prix = Decimal(brut)
                    except InvalidOperation:
                        prix = None
                brut_stock = (request.POST.get("stock", "")
                              .strip().replace(",", "."))
                stock = None
                if brut_stock:
                    try:
                        stock = Decimal(brut_stock)
                    except InvalidOperation:
                        stock = None
                LigneCarte.objects.create(
                    carte=carte,
                    produit=produit,
                    nom_libre="" if produit else nom_libre,
                    section=request.POST.get("section", "").strip(),
                    description=request.POST.get("description", "").strip(),
                    unite_vente=(produit.unite_vente if produit
                                 else Produit.Unite.PIECE),
                    prix=prix,
                    stock=stock,
                    position=(carte.lignes.aggregate(
                        Max("position"))["position__max"] or 0) + 1)
                messages.success(request, "Ligne ajoutée à la carte « "
                                 + carte.nom + " ».")
        elif action == "supprimer_ligne":
            ligne = LigneCarte.objects.filter(
                pk=request.POST.get("ligne_id") or 0, carte=carte).first()
            if ligne:
                ligne.delete()
                messages.info(request, "Ligne retirée de la carte.")
        elif action in ("monter", "descendre"):
            ligne = LigneCarte.objects.filter(
                pk=request.POST.get("ligne_id") or 0, carte=carte).first()
            if ligne:
                voisines = list(carte.lignes.order_by("position", "id"))
                i = voisines.index(ligne)
                j = (max(0, i - 1) if action == "monter"
                     else min(len(voisines) - 1, i + 1))
                voisines[i], voisines[j] = voisines[j], voisines[i]
                for n, l in enumerate(voisines, 1):
                    l.position = n
                    l.save(update_fields=["position"])
        elif action == "maj_stock":
            ligne = LigneCarte.objects.filter(
                pk=request.POST.get("ligne_id") or 0, carte=carte).first()
            if ligne is None:
                messages.error(request, "Ligne introuvable.")
            else:
                brut = (request.POST.get("stock", "")
                        .strip().replace(",", "."))
                if not brut:
                    ligne.stock = None
                    ligne.save(update_fields=["stock"])
                    messages.info(request, "Stock retiré : « "
                                  + ligne.nom + " » est vendu sans limite.")
                else:
                    try:
                        ligne.stock = Decimal(brut)
                        ligne.save(update_fields=["stock"])
                        messages.success(request, "Stock de « "
                                         + ligne.nom + " » mis à jour : "
                                         + brut + ".")
                    except InvalidOperation:
                        messages.error(request, "Stock invalide : "
                                       + brut + ".")
        return redirect("portal:cartes_manage")

    ordre = {Carte.Statut.ACTIVE: 0, Carte.Statut.BROUILLON: 1,
             Carte.Statut.ARCHIVEE: 2}
    cartes = sorted(
        exploitant.cartes.prefetch_related("lignes__produit"),
        key=lambda c: (ordre.get(c.statut, 3), -c.pk))
    return render(request, "portal/pro/cartes.html", {
        "exploitant": exploitant,
        "cartes": cartes,
        "produits": exploitant.produits.filter(actif=True)
                       .order_by("categorie__nom", "nom"),
    })


@login_required
@exploitant_requis
def points_manage(request):
    """Points de livraison & créneaux (issue #9) : création, suppression,
    créneaux récurrents (jour, horaires, fréquence, capacité)."""
    exploitant = exploitant_actif(request)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "point_creer":
            nom = request.POST.get("nom", "").strip()
            adresse = request.POST.get("adresse", "").strip()
            ville = request.POST.get("ville", "").strip()
            code_postal = request.POST.get("code_postal", "").strip()
            note = request.POST.get("note", "").strip()
            latitude = _latlon(request.POST.get("latitude"))
            longitude = _latlon(request.POST.get("longitude"))
            type_point = request.POST.get("type_point", "")
            if type_point not in PointLivraison.Type.values:
                type_point = (
                    PointLivraison.Type.BOUTIQUE
                    if exploitant.en_mode_boutique
                    else PointLivraison.Type.LIVRAISON)
            if not nom or not ville:
                messages.error(request, "Nom et ville du point requis.")
            else:
                PointLivraison.objects.create(
                    exploitant=exploitant, nom=nom[:150],
                    adresse=adresse[:255], ville=ville[:100],
                    code_postal=code_postal[:10], note=note,
                    latitude=latitude, longitude=longitude,
                    type_point=type_point)
                libelle_type = dict(
                    PointLivraison.Type.choices).get(type_point, "")
                messages.success(request,
                                 f"{libelle_type} « {nom} » créé.")
        elif action == "point_geo":
            # Position du point : géocodée (Nominatim) ou posée sur la
            # carte par le maraîcher — transmise au client au moment de
            # la mise en prêt/livré du panier.
            point = get_object_or_404(PointLivraison,
                                      pk=request.POST.get("pk"),
                                      exploitant=exploitant)
            point.latitude = _latlon(request.POST.get("latitude"))
            point.longitude = _latlon(request.POST.get("longitude"))
            point.save()
            messages.success(request,
                             f"Position de « {point.nom} » enregistrée.")
        elif action == "point_modifier":
            # Modifier un point existant (nom, adresse, position) SANS
            # toucher à l'historique : les paniers déjà livrés portent
            # un instantané figé du nom et de la localisation transmis
            # aux clients à l'époque.
            point = get_object_or_404(PointLivraison,
                                      pk=request.POST.get("pk"),
                                      exploitant=exploitant)
            nom = request.POST.get("nom", "").strip()
            if not nom:
                messages.error(request, "Le nom du point est requis.")
            else:
                point.nom = nom[:150]
                for champ, limite in (("adresse", 255),
                                      ("ville", 100),
                                      ("code_postal", 10)):
                    valeur = (request.POST.get(champ, "") or "").strip()
                    setattr(point, champ, valeur[:limite])
                nouvelle_lat = _latlon(request.POST.get("latitude"))
                nouvelle_lon = _latlon(request.POST.get("longitude"))
                if nouvelle_lat is not None:
                    point.latitude = nouvelle_lat
                if nouvelle_lon is not None:
                    point.longitude = nouvelle_lon
                point.save()
                messages.success(request,
                                 f"Point « {point.nom} » mis à jour "
                                 "(les paniers déjà livrés conservent "
                                 "les infos transmises aux clients).")
        elif action == "point_supprimer":
            point = get_object_or_404(PointLivraison,
                                     pk=request.POST.get("pk"),
                                     exploitant=exploitant)
            nb = point.creneaux.count()
            point.delete()
            message = f"Point « {point.nom} » supprimé"
            if nb:
                message += f" (et {nb} créneau(x) rattaché(s))"
            messages.info(request, message + ".")
        elif action == "creneau_ajouter":
            brut_point = request.POST.get("point", "").strip()
            point = (exploitant.points_livraison
                     .filter(pk=brut_point).first() if brut_point else None)
            try:
                jours_choisis = [int(j) for j in
                                 request.POST.getlist("jours")
                                 if j.strip().isdigit()]
                capacite = int(request.POST.get("capacite") or 10)
                heure_debut = datetime.time.fromisoformat(
                    request.POST.get("heure_debut", ""))
                heure_fin = datetime.time.fromisoformat(
                    request.POST.get("heure_fin", ""))
            except (TypeError, ValueError):
                messages.error(request, "Créneau invalide "
                               "(jours, horaires ou capacité).")
                return redirect("portal:points_manage")
            # La capacité (nombre de paniers) n'a de sens que pour les
            # points de livraison : sur une boutique ou un marché, le
            # créneau décrit seulement une présence récurrente.
            if point and point.type_point in (
                    PointLivraison.Type.BOUTIQUE,
                    PointLivraison.Type.MARCHE):
                capacite = 0
            frequence = request.POST.get("frequence", "")
            if not jours_choisis:
                messages.error(request, "Cochez au moins un jour de la "
                               "semaine pour ce créneau.")
            elif any(not (1 <= j <= 7) for j in jours_choisis):
                messages.error(request, "Créneau invalide : jour entre "
                               "lundi et dimanche.")
            elif heure_debut >= heure_fin:
                messages.error(request, "Créneau invalide : la fin doit "
                               "arriver après le début.")
            elif frequence not in CreneauLivraison.Frequence.values:
                messages.error(request, "Fréquence inconnue.")
            else:
                for jour in jours_choisis:
                    CreneauLivraison.objects.create(
                        exploitant=exploitant, point_livraison=point,
                        jour=jour, heure_debut=heure_debut,
                        heure_fin=heure_fin, frequence=frequence,
                        capacite=capacite)
                messages.success(
                    request, "Créneau ajouté : "
                    + ", ".join(dict(CreneauLivraison._meta
                                     .get_field("jour").choices)[j]
                                for j in jours_choisis)
                    + f" {heure_debut}–{heure_fin}.")
        elif action == "creneau_modifier":
            creneau = get_object_or_404(CreneauLivraison,
                                        pk=request.POST.get("pk"),
                                        exploitant=exploitant)
            try:
                heure_debut = datetime.time.fromisoformat(
                    request.POST.get("heure_debut", ""))
                heure_fin = datetime.time.fromisoformat(
                    request.POST.get("heure_fin", ""))
                jour = int(request.POST.get("jour"))
                capacite = int(request.POST.get("capacite")
                                or creneau.capacite)
            except (TypeError, ValueError):
                messages.error(request, "Créneau invalide "
                               "(jour, horaires ou capacité).")
                return redirect("portal:points_manage")
            frequence = request.POST.get("frequence", "")
            if not (1 <= jour <= 7):
                messages.error(request, "Jour inconnu.")
            elif heure_debut >= heure_fin:
                messages.error(request, "Créneau invalide : la fin doit "
                               "arriver après le début.")
            elif frequence not in CreneauLivraison.Frequence.values:
                messages.error(request, "Fréquence inconnue.")
            else:
                creneau.jour = jour
                creneau.heure_debut = heure_debut
                creneau.heure_fin = heure_fin
                creneau.frequence = frequence
                # La capacité ne concerne que les points de livraison
                if (creneau.point_livraison is None
                        or creneau.point_livraison.type_point
                        == PointLivraison.Type.LIVRAISON):
                    creneau.capacite = capacite
                creneau.save()
                messages.success(request, "Créneau mis à jour : "
                                 + creneau.get_jour_display()
                                 + f" {heure_debut}–{heure_fin}.")
        elif action == "creneau_supprimer":
            creneau = get_object_or_404(CreneauLivraison,
                                        pk=request.POST.get("pk"),
                                        exploitant=exploitant)
            creneau.delete()
            messages.info(request, "Créneau supprimé.")
        return redirect("portal:points_manage")

    points = (exploitant.points_livraison
              .prefetch_related("creneaux").order_by("ville", "nom"))
    return render(request, "portal/pro/points.html", {
        "exploitant": exploitant,
        "points": points,
        "jours": CreneauLivraison._meta.get_field("jour").choices,
        "frequences": CreneauLivraison.Frequence.choices,
        "types_points": PointLivraison.Type.choices,
        "creneaux": exploitant.creneaux.select_related("point_livraison"),
        "creneaux_sans_point": exploitant.creneaux
                              .filter(point_livraison__isnull=True),
        # Points localisés : affichés sur la carte de création avec
        # leur symbole propre, cadrage automatique sur leur emprise.
        "points_geo": [{
            "nom": p.nom, "latitude": p.latitude,
            "longitude": p.longitude, "type": p.type_point,
        } for p in points
            if p.latitude is not None and p.longitude is not None],
    })


# ------------------------------------------------- catalogue & catégories

@login_required
@exploitant_requis
@proprietaire_requis
def catalogue_standard(request):
    """Catalogues embarqués de produits types (issue #1), un par
    activité : par défaut celui de l'activité de l'exploitant, tous les
    autres restant accessibles (onglets)."""
    exploitant = exploitant_actif(request)
    activite_courante = (request.GET.get("activite", "")
                         or exploitant.activite)
    if activite_courante not in Exploitant.Activite.values:
        activite_courante = Exploitant.Activite.MARAICHER
    standards = (ProduitStandard.objects.filter(activite=activite_courante)
                 .order_by("categorie", "nom"))
    deja_copies = set(Produit.objects.filter(
        exploitant=exploitant,
        origine_standard__isnull=False
    ).values_list("origine_standard_id", flat=True))
    groupes, ordre = {}, []
    for std in standards:
        if std.categorie not in groupes:
            groupes[std.categorie] = []
            ordre.append(std.categorie)
        groupes[std.categorie].append({
            "std": std,
            "deja": std.pk in deja_copies,
        })
    paires = [(cat, groupes[cat]) for cat in ordre]
    return render(request, "portal/pro/catalogue_standard.html",
                  {"paires": paires,
                   "activite_courante": activite_courante,
                   "activites": Exploitant.Activite.choices,
                   "emoji_activite": Exploitant.ACTIVITE_EMOJIS})


@login_required
@exploitant_requis
@proprietaire_requis
def catalogue_copier(request):
    """Copie les produits types sélectionnés dans le catalogue de
    l'exploitant : catégorie créée si besoin, prix optionnel, traçabilité
    origine_standard (issue #1)."""
    exploitant = exploitant_actif(request)
    if request.method == "POST":
        ids = request.POST.getlist("std")
        copies = 0
        for std in ProduitStandard.objects.filter(pk__in=ids):
            if Produit.objects.filter(exploitant=exploitant,
                                      origine_standard=std).exists():
                continue
            cat, _cree = Categorie.objects.get_or_create(
                exploitant=exploitant, nom=std.categorie)
            if _cree:
                cat.position = exploitant.categories.count()
                cat.save()
            prix = None
            brut = request.POST.get(f"prix_{std.pk}", "").strip()
            if brut:
                try:
                    prix = Decimal(brut)
                except InvalidOperation:
                    prix = None
            if prix is None and std.prix_indicatif is not None:
                prix = std.prix_indicatif
            Produit.objects.create(
                exploitant=exploitant, nom=std.nom, categorie=cat,
                description="", unite_vente=std.unite_vente,
                attributs={"saisons": std.saisons},
                origine_standard=std, prix=prix, actif=True,
                emoji=std.emoji or emoji_pour_nom(std.nom))
            copies += 1
        if copies:
            messages.success(request, f"{copies} produit(s) copié(s) dans "
                             "votre catalogue — complétez les prix si besoin.")
        else:
            messages.info(request, "Aucun nouveau produit copié.")
        activite = request.POST.get("activite", "") or ""
        if activite in Exploitant.Activite.values:
            return redirect(f"{reverse('portal:catalogue_standard')}"
                            f"?activite={activite}")
    return redirect("portal:catalogue_standard")


@login_required
@exploitant_requis
@proprietaire_requis
def categories_manage(request):
    """Gestion des catégories de l'exploitant (issue #5) : créer,
    renommer, réordonner, supprimer. Supprimer ne touche pas les produits
    (ils passent « sans catégorie»)."""
    exploitant = exploitant_actif(request)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "creer":
            nom = request.POST.get("nom", "").strip()
            if nom:
                cat, cree = Categorie.objects.get_or_create(
                    exploitant=exploitant, nom=nom[:80])
                if cree:
                    cat.position = exploitant.categories.count()
                    cat.save()
                    messages.success(request,
                                     f"Catégorie « {cat.nom} » créée.")
                else:
                    messages.info(request, "Cette catégorie existe déjà.")
        elif action == "renommer":
            cat = get_object_or_404(Categorie, pk=request.POST.get("pk"),
                                   exploitant=exploitant)
            nom = request.POST.get("nom", "").strip()
            if nom:
                cat.nom = nom[:80]
                cat.save()
                messages.success(request, "Catégorie renommée.")
        elif action == "supprimer":
            cat = get_object_or_404(Categorie, pk=request.POST.get("pk"),
                                   exploitant=exploitant)
            nb = cat.produits.count()
            nom = cat.nom
            cat.delete()
            message = f"Catégorie « {nom} » supprimée"
            if nb:
                message += (f" — {nb} produit(s) désormais sans catégorie "
                            "(reclassez-les en les modifiant).")
            messages.info(request, message + ".")
        elif action in ("monter", "descendre"):
            cat = get_object_or_404(Categorie, pk=request.POST.get("pk"),
                                    exploitant=exploitant)
            voisines = list(exploitant.categories.order_by("position", "nom"))
            i = voisines.index(cat)
            j = i - 1 if action == "monter" else i + 1
            if 0 <= j < len(voisines):
                voisines[i], voisines[j] = voisines[j], voisines[i]
                for k, c in enumerate(voisines):
                    c.position = k
                    c.save()
        return redirect("portal:categories_manage")
    categories = exploitant.categories.order_by("position", "nom")
    return render(request, "portal/pro/categories.html",
                  {"categories": categories})


# ---------------------------------------------------------------- client

# Téléphone français : 0X XX XX XX XX, +33 ou 0033, séparateurs tolérés.
RE_TEL = re.compile(
    r"^(?:\+33|0033|0)[\s.-]*[1-9]"
    r"(?:[\s.-]*\d{2}){4}$")


def _tel_valide(numero):
    """Numéro français fixe ou mobile, avec ou sans préfixe international."""
    return bool(RE_TEL.match((numero or "").strip()))


def _stocks_carte(exploitant):
    """Stocks publiés par produit sur la carte ACTIVE (boutique,
    carte, menus) : retourne {produit_id: (stock, restant)} où
    restant = stock − quantités des commandes VALIDÉES — la commande
    n'est décomptée qu'une fois validée par l'exploitant, après son
    ajustement éventuel. Les lignes sans stock (illimitées) et les
    lignes libres (sans produit lié) sont absentes du résultat."""
    lignes = list(LigneCarte.objects
                  .filter(carte__exploitant=exploitant,
                          carte__statut=Carte.Statut.ACTIVE,
                          stock__isnull=False,
                          produit__isnull=False)
                  .values_list("produit_id", "stock"))
    if not lignes:
        return {}
    consomme = {}
    qs = (LigneCommande.objects
          .filter(commande__exploitant=exploitant,
                  commande__statut=Commande.Statut.VALIDEE,
                  produit_id__in=[l[0] for l in lignes]))
    for ligne in qs:
        consomme[ligne.produit_id] = (
            consomme.get(ligne.produit_id, Decimal("0")) + ligne.quantite)
    return {p: (s, s - consomme.get(p, Decimal("0")))
            for p, s in lignes}


def _offres_carte_active(exploitant):
    """Produits commandables de la carte ACTIVE (« carte du moment » :
    boutiques, cartes, menus des métiers non récolte) : lignes liées
    à un produit actif du catalogue, au prix de la ligne (ou du
    produit), avec le stock publié éventuel et son restant (stock −
    commandes VALIDÉES). Les lignes libres (sans produit lié : plat
    du jour…) ne sont pas commandables en ligne — à demander sur
    place. Retour trié par catégorie puis position de la carte."""
    stocks = _stocks_carte(exploitant)
    offres = []
    for l in (LigneCarte.objects
              .filter(carte__exploitant=exploitant,
                      carte__statut=Carte.Statut.ACTIVE,
                      produit__isnull=False,
                      produit__actif=True)
              .select_related("produit__categorie",
                              "produit__origine_standard")
              .order_by("position", "id")):
        prix = l.prix if l.prix is not None else l.produit.prix
        if prix is None:
            continue
        stock, reste = stocks.get(l.produit_id, (None, None))
        offres.append({"cle": f"carte_{l.pk}", "produit": l.produit,
                       "prix": prix, "estime": stock, "reste": reste})
    offres.sort(key=lambda o: (
        (o["produit"].categorie.position
         if o["produit"].categorie else 9999) or 9999,
        o["produit"].categorie.nom
        if o["produit"].categorie else "zz",
        o["produit"].nom))
    return offres


JOURS_COURTS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def _position_dynamique_foodtruck(exploitant):
    """Position d'un foodtruck AU MOMENT DE LA REQUÊTE : emplacement du
    créneau en cours s'il y en a un, sinon celui du prochain arrêt
    hebdomadaire (7 jours à venir), sinon adresse déclarée (None si le
    camion n'est ni géolocalisé ni programmé). Les fréquences
    bisomadaire/mensuelle ne sont pas projetées dans le futur (aucun
    repère absolu en base) : seul leur créneau en cours compte.
    Retourne (latitude, longitude, libellé) ou None."""
    maintenant = timezone.localtime()
    aujourdhui = maintenant.date()
    creneaux = list(
        CreneauLivraison.objects
        .filter(exploitant=exploitant,
                point_livraison__latitude__isnull=False,
                point_livraison__longitude__isnull=False)
        .select_related("point_livraison"))
    heure = maintenant.time()
    for c in creneaux:
        if (c.jour == aujourdhui.isoweekday()
                and c.heure_debut <= heure <= c.heure_fin):
            p = c.point_livraison
            return (p.latitude, p.longitude,
                    "Maintenant : " + p.nom + " (" + p.ville
                    + ") jusqu'à " + c.heure_fin.strftime("%H:%M"))
    futurs = []
    for c in creneaux:
        if c.frequence != CreneauLivraison.Frequence.HEBDO:
            continue
        ecart = (c.jour - aujourdhui.isoweekday()) % 7
        date_c = aujourdhui + datetime.timedelta(days=ecart)
        if date_c == aujourdhui and c.heure_debut <= heure:
            continue  # déjà passé aujourd'hui
        debut = datetime.datetime.combine(date_c, c.heure_debut)
        if timezone.is_naive(debut):
            debut = timezone.make_aware(debut)
        if debut >= maintenant:
            futurs.append((debut, date_c, c))
    if futurs:
        debut, date_c, c = min(futurs, key=lambda x: x[0])
        p = c.point_livraison
        return (p.latitude, p.longitude,
                "Prochain arrêt : " + JOURS_COURTS[date_c.weekday()]
                + " " + date_c.strftime("%d/%m") + " "
                + c.heure_debut.strftime("%H:%M")
                + " — " + p.nom + " (" + p.ville + ")")
    return None


def _offres_commande(exploitant, semaine):
    """Offre proposée sur la page de commande :
    - avec une récolte publiée : ses lignes (prix de la récolte) et la
      disponibilité restante = volume estimé − quantités déjà
      commandées sur la semaine (commandes VALIDÉES uniquement,
      après ajustement éventuel de l'exploitant) ;
    - sans récolte : les produits actifs au prix de référence, la
      disponibilité n'étant pas publiée (quantités soumises à la
      validation et aux disponibilités réelles du cultivateur).
    Retourne (offres, mode) — mode : "recolte" ou "catalogue"."""
    offres = []
    if semaine:
        dimanche = semaine.lundi + datetime.timedelta(days=6)
        consomme = {}
        commandes_semaine = LigneCommande.objects.filter(
            commande__exploitant=exploitant,
            commande__statut=Commande.Statut.VALIDEE,
            commande__date_livraison__gte=semaine.lundi,
            commande__date_livraison__lte=dimanche)
        for produit_id, quantite in commandes_semaine.values_list(
                "produit_id", "quantite"):
            consomme[produit_id] = (consomme.get(produit_id, Decimal("0"))
                                    + quantite)
        for ligne in semaine.lignes.select_related("produit__categorie"):
            reste = (ligne.quantite_estimee
                     - consomme.get(ligne.produit_id, Decimal("0")))
            offres.append({"cle": f"qty_{ligne.pk}",
                           "produit": ligne.produit,
                           "prix": ligne.prix_unitaire,
                           "estime": ligne.quantite_estimee,
                           "reste": reste})
        # Regroupement par catégorie à l'affichage : tri identique au
        # catalogue (position et nom de catégorie, puis nom du produit).
        offres.sort(key=lambda o: (
            (o["produit"].categorie.position
             if o["produit"].categorie else 9999) or 9999,
            o["produit"].categorie.nom
            if o["produit"].categorie else "zz",
            o["produit"].nom))
        # Carte « du moment » publiée : ses produits s'ajoutent à
        # l'offre de la semaine (les produits déjà proposés par la
        # récolte ne sont pas dupliqués).
        deja = {o["produit"].pk for o in offres}
        offres += [o for o in _offres_carte_active(exploitant)
                   if o["produit"].pk not in deja]
        return offres, "recolte"
    # Carte « du moment » publiée : l'offre de commande reprend ses
    # produits liés (prix de la ligne, stock publié, restant sur
    # commandes VALIDÉES). Sans carte publiée : catalogue complet.
    offres_carte = _offres_carte_active(exploitant)
    if offres_carte:
        return offres_carte, "carte"
    stocks = _stocks_carte(exploitant)
    for produit in (exploitant.produits.filter(actif=True)
                    .select_related("categorie", "origine_standard")
                    .order_by("categorie__position", "categorie__nom",
                              "position", "nom")):
        if produit.prix is None:
            continue  # sans prix de référence : non commandable
        stock, reste = stocks.get(produit.pk, (None, None))
        offres.append({"cle": f"qty_{produit.pk}", "produit": produit,
                       "prix": produit.prix, "estime": stock, "reste": reste})
    return offres, "catalogue"


def _groupes_offres(offres):
    """Offres regroupées par catégorie (les produits sans catégorie
    forment le groupe « Autres produits » en fin de liste)."""
    groupes = []
    for offre in offres:
        cat = offre["produit"].categorie
        if not groupes or groupes[-1][0] != cat:
            groupes.append((cat, []))
        groupes[-1][1].append(offre)
    sans = [g for g in groupes if g[0] is None]
    groupes = [g for g in groupes if g[0] is not None] + sans
    return groupes


def _valeurs_prefill(request, offres, exploitant):
    """Quantités pré-remplies : saisies sur la vitrine du producteur
    (q_<produit>) ou reprise d'une commande (annulée, ou nouvelle) du
    client connecté — sans repartir de zéro."""
    valeurs = {}
    par_produit = {}
    for offre in offres:
        par_produit[offre["produit"].pk] = offre["cle"]
    for key, brut in request.GET.items():
        if not key.startswith("q_"):
            continue
        try:
            pk = int(key[2:])
        except ValueError:
            continue
        brut = (brut or "").strip()
        if brut and pk in par_produit:
            valeurs[par_produit[pk]] = brut
    reprise = request.GET.get("reprise", "")
    if reprise and request.user.is_authenticated:
        commande = (Commande.objects.filter(
            pk=reprise, client=request.user,
            exploitant=exploitant)
            .prefetch_related("lignes__produit").first())
        if commande is not None:
            for ligne in commande.lignes.all():
                cle = par_produit.get(ligne.produit_id)
                if cle:
                    valeurs[cle] = str(ligne.quantite)
            valeurs["__date"] = commande.date_livraison.isoformat()
            valeurs["__point"] = str(commande.point_livraison_id or "")
    return valeurs


def order_create(request, slug):
    """Le client choisit produits/quantités/date et soumet sa commande.

    Produits regroupés par catégorie. Avec une récolte publiée : les
    quantités affichées sont les disponibilités restantes (estimation
    − commandes de la semaine). Sans récolte : le catalogue au prix de
    référence, quantités soumises à validation et disponibilité.
    Un exploitant ne peut pas se commander à lui-même via la vitrine.

    En cas d'erreur, le formulaire est ré-affiché avec les valeurs
    saisies (rien n'est perdu). La reprise d'une commande annulée
    pré-remplit quantités, date et point de livraison.
    """
    exploitant = get_object_or_404(Exploitant, slug=slug, visible=True)
    if (exploitant_actif(request) is not None
            and exploitant_actif(request).pk == exploitant.pk):
        messages.info(request, "Vous êtes le producteur de cet espace : "
                     "utilisez « Saisir une commande » dans votre espace "
                     "pro pour enregistrer une commande (la vôtre par "
                     "exemple).")
        return redirect("portal:producer_detail", slug=slug)
    today = timezone.localdate()
    lundi = today - datetime.timedelta(days=today.weekday())
    semaine = (SemaineRecolte.objects.filter(exploitant=exploitant,
                                             publiee=True,
                                             lundi__lte=lundi)
               .order_by("-lundi").first())
    offres, mode = _offres_commande(exploitant, semaine)
    carte_active = (Carte.objects.filter(
        exploitant=exploitant, statut=Carte.Statut.ACTIVE).first())
    dates = _dates_livraison(exploitant, today)
    # Jour (lundi=1…dimanche=7) de chaque date proposée + jours de
    # créneau de chaque point : le formulaire client filtre les dates
    # selon le point de livraison choisi.
    dates_aff = [(d, d.isoweekday()) for d in dates]
    points_jours = {
        p.pk: ",".join(str(c.jour)
                       for c in p.creneaux.all())
        for p in exploitant.points_livraison.all()
        if p.creneaux.exists()}

    def _afficher(soumis=None):
        valeurs = dict(_valeurs_prefill(request, offres, exploitant))
        date_pre = valeurs.pop("__date", "")
        point_pre = valeurs.pop("__point", "")
        contexte = {"exploitant": exploitant, "semaine": semaine,
                    "offres": offres, "groupes": _groupes_offres(offres),
                    "mode": mode,
                    "carte_active": carte_active,
                    "points_livraison": exploitant.points_livraison.all(),
                    "dates": dates_aff, "points_jours": points_jours}
        contexte["valeurs"] = (soumis or {}).get("valeurs", valeurs)
        contexte["date_choisie"] = ((soumis or {}).get("date_livraison", "")
                                    or date_pre)
        contexte["point_choisi"] = ((soumis or {}).get("point", "")
                                    or point_pre)
        contexte["invit"] = (soumis or {}).get("invit", "")
        for cle in ("nom_client", "email_client", "telephone_client",
                    "note"):
            contexte[cle] = (soumis or {}).get(cle, "")
        return render(request, "portal/order_create.html", contexte)

    if request.method == "POST":
        lignes_souhaitees, total = [], Decimal("0")
        for offre in offres:
            brut = request.POST.get(offre["cle"], "").strip()
            if not brut:
                continue
            try:
                qty = Decimal(brut)
            except InvalidOperation:
                continue
            if qty <= 0:
                continue
            produit = offre["produit"]
            if (produit.unite_vente in UNITES_ENTIERES
                    and qty != qty.to_integral_value()):
                messages.error(
                    request, f"« {produit.nom} » se vend à la pièce : "
                    "merci de commander un nombre entier.")
                return _afficher(_soumis(request, offres))
            # Récolte publiée : au-delà de la dispo restante, la ligne
            # passe en orange côté client ; la commande reste possible
            # (estimation indicative), le producteur ajustera en
            # validant.
            lignes_souhaitees.append((produit, offre["prix"], qty))
            total += qty * offre["prix"]
        point = exploitant.points_livraison.filter(
            pk=request.POST.get("point_livraison")).first()
        if point is None and exploitant.points_livraison.exists():
            messages.error(request, "Merci de choisir un point de "
                           "livraison pour votre commande.")
            return _afficher(_soumis(request, offres))
        try:
            date_livraison = datetime.date.fromisoformat(
                request.POST["date_livraison"])
        except (KeyError, ValueError):
            date_livraison = None
        if (not lignes_souhaitees or date_livraison is None
                or date_livraison < today):
            messages.error(request,
                           "Commande invalide : vérifiez les quantités et la date.")
            return _afficher(_soumis(request, offres))
        if request.user.is_authenticated:
            client = request.user
            actif = espace_actif(request)
            if actif is not None:
                # Mode espace pro : la commande est passée au nom de
                # la structure, avec les coordonnées de la fiche pro.
                nom_client = actif.nom_espace
                email_client = actif.user.email
                telephone_client = actif.telephone
            else:
                # Mode client : nom propre ou alias, coordonnées perso.
                nom_client = nom_affiche(request.user)
                email_client = request.user.email
                profil_courant = getattr(request.user, "profil_client",
                                         None)
                telephone_client = (profil_courant.telephone
                                    if profil_courant else "")
        else:
            client = None
            nom_client = request.POST.get("nom_client", "").strip()
            email_client = request.POST.get("email_client", "").strip()
            telephone_client = request.POST.get(
                "telephone_client", "").strip()
            # Sans compte, le téléphone est le canal de contact du
            # producteur : obligatoire et au format français (fixe/mobile).
            if not nom_client:
                messages.error(request, "Merci d'indiquer votre nom.")
                return _afficher(_soumis(request, offres))
            if not _tel_valide(telephone_client):
                messages.error(
                    request, "Merci d'indiquer un numéro de téléphone "
                    "valide (ex : 06 12 34 56 78) : c'est le moyen de "
                    "contact du producteur pour valider votre commande.")
                return _afficher(_soumis(request, offres))
        with transaction.atomic():
            commande = Commande.objects.create(
                exploitant=exploitant, client=client,
                nom_client=nom_client[:150], email_client=email_client,
                telephone_client=telephone_client,
                point_livraison=point, date_livraison=date_livraison,
                note=request.POST.get("note", ""), total=total)
            for produit, prix, qty in lignes_souhaitees:
                LigneCommande.objects.create(
                    commande=commande, produit=produit,
                    quantite=qty, prix_unitaire=prix)
        if client:
            messages.success(
                request, "Commande envoyée ! Le producteur va la valider, "
                "vous la retrouverez dans « Mes commandes ».")
            return redirect("portal:my_orders")
        contact = email_client or telephone_client
        messages.success(
            request, "Commande envoyée ! Le producteur vous recontactera "
            f"via {contact} pour valider votre commande.")
        return redirect("portal:producer_detail", slug=slug)

    return _afficher()


def _soumis(request, offres):
    """Capture des valeurs saisies (POST) pour ré-afficher le
    formulaire sans rien perdre en cas d'erreur."""
    valeurs = {}
    for offre in offres:
        brut = (request.POST.get(offre["cle"], "") or "").strip()
        if brut:
            valeurs[offre["cle"]] = brut
    return {
        "valeurs": valeurs,
        "date_livraison": request.POST.get("date_livraison", ""),
        "point": request.POST.get("point_livraison", ""),
        "nom_client": request.POST.get("nom_client", ""),
        "email_client": request.POST.get("email_client", ""),
        "telephone_client": request.POST.get("telephone_client", ""),
        "note": request.POST.get("note", ""),
        "invit": "",
    }


def _dates_livraison(exploitant, today):
    """Dates futures correspondant aux jours de créneaux (28 jours)."""
    jours = {c.jour for c in exploitant.creneaux.all()}
    dates = []
    for i in range(0, 29):
        d = today + datetime.timedelta(days=i)
        if d.isoweekday() in jours or not jours:
            dates.append(d)
    return dates


def _restes_semaine(objet):
    """Disponibilités restantes de la semaine de livraison d'une
    commande OU d'un panier (par produit) : estimation de la récolte
    publiée − quantités déjà commandées sur la semaine. Dict vide si
    aucune récolte publiée ne couvre cette semaine."""
    lundi = (objet.date_livraison
             - datetime.timedelta(days=objet.date_livraison.weekday()))
    semaine = (SemaineRecolte.objects.filter(
        exploitant=objet.exploitant, publiee=True, lundi=lundi).first())
    if not semaine:
        return {}
    offres, mode = _offres_commande(objet.exploitant, semaine)
    if mode != "recolte":
        return {}
    return {o["produit"].pk: o["reste"] for o in offres
            if o["reste"] is not None}


def _marges_ajustement(commande):
    """Marge de manœuvre du client sur SA commande non validée :
    pour chaque ligne, dispo restante de la semaine + sa propre
    quantité (elle se libère en baissant sa commande). None = pas de
    récolte publiée (pas de contrainte de disponibilité)."""
    restes = _restes_semaine(commande)
    return {ligne.pk: (restes[ligne.produit_id] + ligne.quantite
                      if ligne.produit_id in restes else None)
            for ligne in commande.lignes.all()}


def _dispos_lignes(objet, lignes):
    """Pour l'affichage pro (validation, paniers) : dispo estimée à côté
    de chaque ligne — la marge incluant la quantité de la ligne elle-
    même — et drapeau « dépassé » quand la semaine est sur-commandée
    (reste < 0 : toutes commandes confondues, on dépasse l'estimé)."""
    restes = _restes_semaine(objet)
    dispos = {}
    for ligne in lignes:
        reste = restes.get(ligne.produit_id)
        if reste is not None:
            dispos[ligne.pk] = {"dispo": reste + ligne.quantite,
                                 "depasse": reste < 0}
    return dispos


@login_required
def my_orders(request):
    """Commandes du client ; les paniers validés montrent le contenu
    livré côte à côte du souhaité, avec le commentaire du producteur.
    Tant que la commande n'est pas validée, le client peut ajuster ses
    quantités dans la marge des disponibilités restantes. Filtres :
    statut de la commande (refusées et annulées regroupées en rouge),
    paniers prêts / retirés, et vue alternative « calendrier » de la
    semaine."""
    filtre = request.GET.get("filtre", "").strip()
    vue = request.GET.get("vue", "liste").strip()

    # Modes « paniers » : ne montrer QUE les paniers, dépliés, avec
    # validation de la réception quand le panier est prêt.
    if filtre in ("panier_pret", "panier_recu"):
        statut_panier = (Panier.Statut.PRET if filtre == "panier_pret"
                         else Panier.Statut.RECU)
        paniers = list((request.user.paniers
                        .select_related("exploitant", "point_livraison")
                        .filter(statut=statut_panier)
                        .prefetch_related("lignes__produit")
                        .order_by("-date_livraison", "numero")))
        for panier in paniers:
            panier.groupes_lignes = _groupes_lignes(list(panier.lignes.all()))
        return render(request, "portal/my_orders.html", {
            "mode": "paniers", "filtre": filtre,
            "today": timezone.localdate(), "paniers": paniers})

    commandes = (request.user.commandes.select_related("exploitant")
                 .prefetch_related("lignes__produit")
                 .order_by("-date_livraison", "-creee_le"))
    if filtre in (Commande.Statut.NOUVELLE, Commande.Statut.VALIDEE):
        commandes = commandes.filter(statut=filtre)
    elif filtre == "cloturees":
        # Refus producteur et annulation client regroupés (rouge).
        commandes = commandes.filter(
            statut__in=[Commande.Statut.REFUSEE, Commande.Statut.ANNULEE])
    commandes = list(commandes)

    if vue == "calendrier":
        try:
            ref = datetime.date.fromisoformat(
                request.GET.get("sem", "").strip())
        except ValueError:
            ref = timezone.localdate()
        lundi = ref - datetime.timedelta(days=ref.weekday())
        jours_cal = []
        for i in range(7):
            jour = lundi + datetime.timedelta(days=i)
            jours_cal.append({
                "date": jour,
                "commandes": [c for c in commandes
                              if c.date_livraison == jour],
            })
        return render(request, "portal/my_orders.html", {
            "mode": "calendrier", "filtre": filtre, "vue": "calendrier",
            "today": timezone.localdate(),
            "jours_cal": jours_cal,
            "semaine_debut": lundi,
            "semaine_fin": lundi + datetime.timedelta(days=6),
            "sem_prec": (lundi - datetime.timedelta(days=7)).isoformat(),
            "sem_suiv": (lundi + datetime.timedelta(days=7)).isoformat(),
        })

    resultats = []
    for commande in commandes:
        panier = (Panier.objects.filter(commande=commande)
                  .prefetch_related("lignes__produit").first())
        lignes_panier = []
        if panier:
            souhaitees = {lc.produit_id: lc.quantite
                          for lc in commande.lignes.all()}
            for lp in panier.lignes.all():
                souh = souhaitees.get(lp.produit_id)
                lignes_panier.append({
                    "ligne": lp,
                    "souhaite": souh,
                    "ajuste": souh is not None and souh != lp.quantite,
                })
        marges = (_marges_ajustement(commande)
                  if commande.statut == Commande.Statut.NOUVELLE else {})
        commande.groupes_lignes = _groupes_lignes(
            list(commande.lignes.all()))
        if panier:
            panier.groupes_lignes = _groupes_lignes(list(panier.lignes.all()))
            # Mêmes lignes que groupes_lignes, mais enrichies des
            # quantités souhaitées / ajustées pour l'affichage client.
            par_cat = {}
            for row in lignes_panier:
                cat = (row["ligne"].produit.categorie.nom
                       if row["ligne"].produit.categorie
                       else "Sans catégorie")
                par_cat.setdefault(cat, []).append(row)
            ordre = [nom for nom, _ in panier.groupes_lignes]
            panier.groupes_contenu = [(nom, par_cat.get(nom, []))
                                      for nom in ordre]
            panier.groupes_contenu += [(nom, rows)
                                       for nom, rows in par_cat.items()
                                       if nom not in ordre]
        resultats.append({"commande": commande, "panier": panier,
                          "lignes_panier": lignes_panier,
                          "marges": marges})
    # En-têtes de jour : comptage par statut (« à traiter » plutôt que
    # « nouvelle » côté client) — même habillage que l'espace pro.
    statuts_client = [
        (code, "à traiter" if code == Commande.Statut.NOUVELLE
         else libelle.lower())
        for code, libelle in Commande.Statut.choices]
    # Deux rubriques : commandes et paniers EN COURS (à traiter,
    # en préparation ou prêts) vs HISTORIQUE (livrés, retirés,
    # refusés, annulés).
    en_cours, historique = [], []
    for resultat in resultats:
        commande = resultat["commande"]
        panier = resultat["panier"]
        active = (commande.statut in (Commande.Statut.NOUVELLE,
                                     Commande.Statut.VALIDEE)
                  and (panier is None
                       or panier.statut in (Panier.Statut.PREPARATION,
                                            Panier.Statut.PRET)))
        (en_cours if active else historique).append(resultat)
    sections = [
        {"titre": "🔄 Commandes et paniers en cours",
         "resultats": en_cours,
         "vide": "Aucune commande en cours : trouvez un producteur "
                 "et passez votre première commande !"},
        {"titre": "🗄️ Historique des commandes et paniers",
         "resultats": historique,
         "vide": "Pas encore d'historique : vos commandes livrées, "
                 "paniers retirés et commandes clôturées "
                 "apparaîtront ici."},
    ]
    return render(request, "portal/my_orders.html", {
        "mode": "liste", "filtre": filtre,
        "today": timezone.localdate(),
        "resultats": resultats,
        "sections": sections,
        "jours_badges": _badges_par_jour(commandes, "statut", statuts_client),
    })


@login_required
def order_cancel(request, commande_id):
    commande = get_object_or_404(Commande, pk=commande_id, client=request.user)
    if (request.method == "POST"
            and commande.statut == Commande.Statut.NOUVELLE):
        commande.statut = Commande.Statut.ANNULEE
        commande.annulee_par = Commande.AnnulationPar.CLIENT
        commande.motif_annulation = request.POST.get("motif", "").strip()
        commande.save()
        messages.info(request, f"Commande #{commande.pk} annulée.")
    return redirect("portal:my_orders")


@login_required
def panier_recu(request, panier_id):
    """Le client confirme avoir retiré son panier « Prêt » : dernier
    statut du processus (Reçu / retiré), verrouillé en lecture seule
    côté producteur et compté dans l'export production."""
    panier = get_object_or_404(Panier, pk=panier_id, client=request.user)
    # Un panier « Prêt » OU « Livré » (marqué livré par le producteur)
    # peut être confirmé reçu/retiré par le client : dernier statut du
    # processus, il notifie le producteur et verrouille la fiche en
    # lecture seule côté pro.
    if (request.method == "POST"
            and panier.statut in (Panier.Statut.PRET,
                                  Panier.Statut.LIVRE)):
        panier.statut = Panier.Statut.RECU
        panier.save()
        messages.success(
            request, f"Panier n°{panier.numero} marqué comme reçu — "
            f"merci, et bon appétit ! 🧺")
    return redirect("portal:my_orders")


@login_required
def order_ajuster(request, commande_id):
    """Le client ajuste les quantités de SA commande tant que le
    producteur ne l'a pas validée (statut NOUVELLE) : dans la marge des
    disponibilités restantes (dispo de la semaine + sa quantité
    actuelle, qui se libère en baissant). Dès la validation, la
    commande devient un panier et n'est plus modifiable ici."""
    commande = get_object_or_404(Commande, pk=commande_id,
                                  client=request.user)
    if commande.statut != Commande.Statut.NOUVELLE:
        messages.error(
            request, "Cette commande a déjà été traitée par le "
            "producteur : elle n'est plus modifiable. Utilisez "
            "« 🔁 Recommander » si besoin.")
        return redirect("portal:my_orders")
    marges = _marges_ajustement(commande)
    if request.method == "POST":
        lignes = list(commande.lignes.select_related("produit"))
        ajustees, total, erreurs = [], Decimal("0"), []
        for ligne in lignes:
            brut = request.POST.get(f"qaj_{ligne.pk}", "").strip()
            if not brut:
                qty = ligne.quantite  # champ vide = quantité inchangée
            else:
                try:
                    qty = Decimal(brut)
                except InvalidOperation:
                    erreurs.append(
                        f"« {ligne.produit.nom} » : quantité invalide.")
                    continue
                if qty < 0:
                    qty = Decimal("0")
                if (ligne.produit.unite_vente in UNITES_ENTIERES
                        and qty != qty.to_integral_value()):
                    erreurs.append(
                        f"« {ligne.produit.nom} » se vend à la pièce : "
                        "nombre entier attendu.")
                    continue
                marge = marges.get(ligne.pk)
                if marge is not None and qty > marge:
                    erreurs.append(
                        f"« {ligne.produit.nom} » : disponibilité "
                        f"limitée à {marge} "
                        f"{ligne.produit.unite_courte} pour cette "
                        "semaine (votre commande incluse).")
                    continue
            if qty > 0:
                ajustees.append((ligne, qty))
                total += qty * ligne.prix_unitaire
        if erreurs:
            messages.error(request, " ".join(erreurs))
            return redirect("portal:my_orders")
        if not ajustees:
            messages.error(
                request, "Impossible : toutes les lignes seraient "
                "supprimées (utilisez plutôt « Annuler »).")
            return redirect("portal:my_orders")
        with transaction.atomic():
            conservees = {ligne.pk: qty for ligne, qty in ajustees}
            for ligne in lignes:
                if ligne.pk not in conservees:
                    ligne.delete()
                elif conservees[ligne.pk] != ligne.quantite:
                    ligne.quantite = conservees[ligne.pk]
                    ligne.save()
            commande.total = total
            commande.save()
        messages.success(request,
                         f"Commande #{commande.pk} mise à jour : le "
                         "producteur validera les quantités finales.")
        return redirect("portal:my_orders")
    return redirect("portal:my_orders")


# ----------------------------------------------------------- editions profil

def _enregistrer_infos_perso(request, redirect_vers, **redirect_kwargs):
    """Enregistre prenom / nom du compte courant, et son telephone dans
    ProfilClient (commun clients et maraichers) — l'e-mail, sensible
    (récupération de compte), se gère dans la section Sécurité."""
    profil, _cree = ProfilClient.objects.get_or_create(user=request.user)
    form = ProfilPersonnelForm(request.POST)
    if form.is_valid():
        user = request.user
        username = (form.cleaned_data.get("username") or "").strip()
        if username and username.lower() != user.username.lower():
            if User.objects.exclude(pk=user.pk).filter(
                    username__iexact=username).exists():
                form.add_error("username",
                               "Cet identifiant est déjà utilisé par "
                               "un autre compte.")
                return form
            user.username = username
        user.first_name = form.cleaned_data["prenom"]
        user.last_name = form.cleaned_data["nom"]
        user.save()
        profil.telephone = form.cleaned_data["telephone"]
        profil.alias = (form.cleaned_data.get("alias", "") or "").strip()
        profil.photo_url = form.cleaned_data.get("photo_externe", "")
        profil.save()
        # Propager l'identité aux commandes et paniers déjà enregistrés
        # (y compris validés) : les snapshots nom/e-mail/téléphone suivent
        # le profil, pour l'affichage comme pour les contacts producteur.
        nom_complet = nom_affiche(user)[:150]
        maj = {"nom_client": nom_complet, "email_client": user.email}
        telephone = (form.cleaned_data.get("telephone") or "")[:20]
        if telephone:
            maj["telephone_client"] = telephone
        # Les commandes passées au nom d'une structure (mode espace
        # pro) gardent leur identité : seules celles au nom propre
        # suivent l'alias / le nom du compte.
        noms_structure = [ex.nom_espace
                          for ex, _role in espaces_pro(user)]
        hors_structure = (Q(nom_client__in=noms_structure)
                          if noms_structure else Q())
        Commande.objects.filter(client=user).exclude(
            hors_structure).update(**maj)
        Panier.objects.filter(client=user).exclude(
            hors_structure).update(**maj)
        messages.success(request, "Vos informations personnelles ont été "
                         "mises à jour (commandes et paniers inclus).")
        return redirect(redirect_vers, **redirect_kwargs)
    return form


def _libelles_mot_de_passe(form):
    """Libellés français du formulaire de changement de mot de passe."""
    form.fields["old_password"].label = "Mot de passe actuel"
    form.fields["new_password1"].label = "Nouveau mot de passe"
    form.fields["new_password1"].help_text = (
        "Au moins 8 caractères. Évitez les mots de passe trop courants.")
    form.fields["new_password2"].label = "Nouveau mot de passe (retapez-le)"
    return form


def _form_motdepasse(user):
    """Section « Sécurité » : formulaire vierge de changement de mot
    de passe, libellé en français."""
    return _libelles_mot_de_passe(PasswordChangeForm(user))


def _enregistrer_mot_de_passe(request, redirect_vers, **redirect_kwargs):
    """Section « Sécurité » des pages Mon profil : change le mot de
    passe du compte courant — et enregistre l'e-mail si le champ a
    été modifié (donnée sensible : elle sert à la récupération du
    compte en cas de mot de passe perdu). La session reste ouverte
    (mise à jour du hachage de session après enregistrement).
    Retourne la redirection, ou le formulaire en erreur à
    re-présenter."""
    form = _libelles_mot_de_passe(
        PasswordChangeForm(request.user, request.POST))
    email = (request.POST.get("email") or "").strip().lower()
    email_change = bool(email) and email != request.user.email.lower()
    if email_change:
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "E-mail non enregistré : adresse "
                           "invalide.")
            return form
        if User.objects.exclude(pk=request.user.pk).filter(
                Q(email__iexact=email)
                | Q(username__iexact=email)).exists():
            messages.error(request, "E-mail non enregistré : un autre "
                           "compte utilise déjà cette adresse.")
            return form
    if form.is_valid():
        if email_change:
            request.user.email = email
            request.user.save(update_fields=["email"])
            # Les snapshots e-mail des commandes et paniers suivent le
            # compte (contacts producteur), comme sur le profil.
            Commande.objects.filter(client=request.user).update(
                email_client=email)
            Panier.objects.filter(client=request.user).update(
                email_client=email)
        form.save()
        update_session_auth_hash(request, form.user)
        messages.success(
            request, "Votre mot de passe a été modifié."
            + (" E-mail mis à jour." if email_change else ""))
        return redirect(redirect_vers, **redirect_kwargs)
    return form


@login_required
def profil_client(request):
    """Le client édite ses informations : prenom, nom, e-mail,
    telephone — et son mot de passe (section Sécurité)."""
    profil, _cree = ProfilClient.objects.get_or_create(user=request.user)
    form = None
    form_motdepasse = None
    if request.method == "POST":
        if request.POST.get("section") == "motdepasse":
            resultat = _enregistrer_mot_de_passe(
                request, "portal:profil_client")
            if not hasattr(resultat, "is_valid"):
                return resultat  # redirection déjà émise
            form_motdepasse = resultat
        else:
            form = _enregistrer_infos_perso(request, "portal:my_orders")
            if not hasattr(form, "is_valid"):
                return form  # redirection déjà émise
    if form is None:
        form = ProfilPersonnelForm(initial={
            "prenom": request.user.first_name,
            "nom": request.user.last_name,
            "username": request.user.username,
            "alias": profil.alias,
            "telephone": profil.telephone,
            "photo_externe": profil.photo_url,
        })
    if form_motdepasse is None:
        form_motdepasse = _form_motdepasse(request.user)
    return render(request, "portal/profil_client.html",
                  {"form": form, "form_motdepasse": form_motdepasse})


@login_required
@exploitant_requis
@proprietaire_requis
def equipe_manage(request):
    """Gestion de l'équipe de l'exploitation : page dédiée du menu
    « Gestion » (ajout / retrait des comptes rattachés)."""
    exploitant = exploitant_actif(request)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "ajouter":
            cle = request.POST.get("membre", "").strip()
            if not cle:
                messages.error(request, "Renseignez l'e-mail ou "
                               "l'identifiant du compte à rattacher.")
            else:
                user = (User.objects.filter(email__iexact=cle).first()
                        or User.objects.filter(
                            username__iexact=cle).first())
                if user is None:
                    messages.error(request, f"Aucun compte « {cle} » : la "
                                   "personne doit d'abord créer un compte "
                                   "sur le portail.")
                elif MembreExploitation.objects.filter(
                        user=user, exploitant=exploitant).exists():
                    messages.error(request, f"« {cle} » est déjà membre "
                                   "de cette exploitation.")
                else:
                    MembreExploitation.objects.create(
                        user=user, exploitant=exploitant,
                        telephone=request.POST.get(
                            "telephone", "").strip())
                    messages.success(
                        request, f"{user.get_full_name() or user.username} "
                        "rattaché(e) à l'exploitation.")
        elif action == "retirer":
            membre = exploitant.membres.filter(
                pk=request.POST.get("membre_id")).first()
            if membre:
                nom = (membre.user.get_full_name()
                       or membre.user.username)
                membre.delete()
                messages.info(request, f"{nom} n'est plus membre de "
                               "l'exploitation.")
        return redirect("portal:equipe_manage")
    return render(request, "portal/pro/equipe.html", {
        "exploitant": exploitant,
        "membres": exploitant.membres.select_related("user"),
        "est_proprietaire": True,
    })


@login_required
@exploitant_requis
def parametres(request):
    """Ancienne page unique de paramètres : redirige vers la rubrique
    « Mon profil » du menu déroulant Paramètres."""
    return redirect("portal:param_rubrique", rubrique="profil")


@login_required
@exploitant_requis
def param_rubrique(request, rubrique):
    """Rubriques indépendantes du menu Paramètres : « Mon profil »
    (compte individuel), « Mon espace » (vitrine publique) et
    « Messagerie » (propriétaire seulement — SMTP d'envoi des e-mails
    et passerelle SMS). Chaque page s'enregistre séparément."""
    if rubrique not in ("profil", "espace", "messagerie"):
        return redirect("portal:param_rubrique", rubrique="profil")
    exploitant = exploitant_actif(request)
    vitrine, _cree = ParametresVitrine.objects.get_or_create(
        exploitant=exploitant)
    est_proprietaire = exploitant.user_id == request.user.id
    if rubrique == "messagerie" and not est_proprietaire:
        return redirect("portal:param_rubrique", rubrique="profil")
    messagerie = vitrine.messagerie or {}
    form_motdepasse = None

    if request.method == "POST":
        section = request.POST.get("section", "")

        if section == "espace" and rubrique == "espace":
            form_espace = ProfilExploitantForm(request.POST, request.FILES,
                                             instance=exploitant)
            if form_espace.is_valid():
                form_espace.save()
                reseaux = dict(vitrine.reseaux or {})
                url = form_espace.cleaned_data.get("logo_externe", "").strip()
                if url:
                    reseaux["logo_url"] = url
                else:
                    reseaux.pop("logo_url", None)
                for cle in ("site_web", "facebook", "instagram"):
                    valeur = form_espace.cleaned_data.get(cle, "").strip()
                    if valeur:
                        reseaux[cle] = valeur
                    else:
                        reseaux.pop(cle, None)
                vitrine.reseaux = reseaux
                rythme = request.POST.get("rythme_publication", "")
                vitrine.rythme_publication = (
                    rythme if rythme
                    in ParametresVitrine.Rythme.values else "")
                vitrine.save()
                if exploitant.siret and not exploitant.siret_valide:
                    messages.warning(
                        request, "Fiche enregistrée, mais le numéro SIRET "
                        "n'est pas valide (14 chiffres attendus) : votre "
                        "vitrine affichera « Producteur particulier ».")
                else:
                    messages.success(request,
                                     "Votre fiche a été mise à jour.")
                return redirect("portal:param_rubrique", rubrique="espace")

        elif section == "profil" and rubrique == "profil":
            resultat = _enregistrer_infos_perso(
                request, "portal:param_rubrique", rubrique="profil")
            if not hasattr(resultat, "is_valid"):
                return resultat

        elif section == "motdepasse" and rubrique == "profil":
            resultat = _enregistrer_mot_de_passe(
                request, "portal:param_rubrique", rubrique="profil")
            if not hasattr(resultat, "is_valid"):
                return resultat
            form_motdepasse = resultat

        elif section == "messagerie" and rubrique == "messagerie":
            form_messagerie = MessagerieForm(request.POST)
            if form_messagerie.is_valid():
                # On ne conserve que les valeurs renseignées (les champs
                # vides retirent le paramètre correspondant).
                vitrine.messagerie = {
                    cle: valeur for cle, valeur in
                    form_messagerie.cleaned_data.items() if valeur}
                vitrine.save()
                messages.success(
                    request, "Paramètres de messagerie enregistrés."
                    if vitrine.messagerie.get("email_host")
                    else "Paramètres de messagerie effacés.")
                return redirect("portal:param_rubrique",
                                rubrique="messagerie")

        elif section == "test_email" and rubrique == "messagerie":
            destinataire = request.user.email
            if not destinataire:
                messages.error(request, "Votre compte n'a pas d'adresse "
                               "e-mail : renseignez-la d'abord dans « Mon "
                               "profil », puis revenez tester ici.")
            else:
                connexion = _connexion_email(vitrine)
                expediteur = ((vitrine.messagerie or {}).get("email_from")
                              or settings.DEFAULT_FROM_EMAIL)
                try:
                    django.core.mail.EmailMessage(
                        "[Test] Votre messagerie — "
                        + exploitant.nom_espace,
                        "Ceci est un e-mail de test envoyé depuis la page "
                        "Messagerie. Si vous le lisez, votre configuration "
                        "SMTP fonctionne : newsletters et annonces "
                        "partiront au nom de votre espace.",
                        expediteur, [destinataire],
                        connection=connexion).send()
                    messages.success(request, "✉️ E-mail de test envoyé à "
                                     + destinataire + " : vérifiez votre "
                                     "boîte de réception (et les "
                                     "indésirables).")
                except Exception as err:
                    messages.error(request, "❌ Échec de l'envoi de test : "
                                   + str(err))
            return redirect("portal:param_rubrique", rubrique="messagerie")

        elif section == "test_sms" and rubrique == "messagerie":
            ok, info = envoyer_sms(
                exploitant,
                "Test SMS " + exploitant.nom_espace
                + " : votre passerelle SMS fonctionne.")
            if ok:
                messages.success(request, "📱 SMS de test envoyé (" + info
                                 + ") : il part vers VOTRE numéro Free "
                                 "Mobile configuré dans l'admin.")
            else:
                messages.error(request, "❌ SMS de test non envoyé (" + info
                               + ").")
            return redirect("portal:param_rubrique", rubrique="messagerie")

        if form_motdepasse is None:
            return redirect("portal:param_rubrique", rubrique=rubrique)

    # Affichage de la rubrique (ou re-affichage après erreur de
    # formulaire : on reprend les valeurs initiales).
    if rubrique == "profil":
        profil, _cree = ProfilClient.objects.get_or_create(
            user=request.user)
        form_profil = ProfilPersonnelForm(initial={
            "prenom": request.user.first_name,
            "nom": request.user.last_name,
            "username": request.user.username,
            "alias": profil.alias,
            "telephone": profil.telephone,
            "photo_externe": profil.photo_url,
        })
        if form_motdepasse is None:
            form_motdepasse = _form_motdepasse(request.user)
        return render(request, "portal/pro/param_profil.html", {
            "exploitant": exploitant,
            "form_profil": form_profil,
            "form_motdepasse": form_motdepasse,
        })

    if rubrique == "espace":
        reseaux = dict(vitrine.reseaux or {})
        form_espace = ProfilExploitantForm(
            instance=exploitant,
            initial={"logo_externe": reseaux.get("logo_url", ""),
                     "site_web": reseaux.get("site_web", ""),
                     "facebook": reseaux.get("facebook", ""),
                     "instagram": reseaux.get("instagram", "")})
        return render(request, "portal/pro/param_ferme.html", {
            "exploitant": exploitant,
            "form_espace": form_espace,
            "vitrine": vitrine,
            "rythmes": ParametresVitrine.Rythme.choices,
            "rythme_actuel": vitrine.rythme_publication,
        })

    form_messagerie = MessagerieForm(initial=messagerie)
    return render(request, "portal/pro/param_messagerie.html", {
        "exploitant": exploitant,
        "form_messagerie": form_messagerie,
        "est_proprietaire": est_proprietaire,
    })


def _connexion_email(vitrine):
    """Connexion SMTP propre à l'exploitation (page Paramètres) :
    retourne None pour utiliser le backend par défaut du serveur
    (console si EMAIL_HOST n'est pas configuré)."""
    m = vitrine.messagerie or {}
    if not m.get("email_host"):
        return None
    try:
        port = int(m.get("email_port") or 25)
    except (TypeError, ValueError):
        port = 25
    return django.core.mail.get_connection(
        host=m["email_host"], port=port,
        username=m.get("email_user") or None,
        password=m.get("email_password") or None,
        use_tls=bool(m.get("email_tls")), fail_silently=False)


@login_required
@exploitant_requis
def publications_manage(request):
    """Ancienne page unique : redirige vers la rubrique Newsletter du
    menu déroulant Publications."""
    return redirect("portal:pub_rubrique", rubrique="newsletter")


@login_required
@exploitant_requis
def pub_rubrique(request, rubrique):
    """Rubriques indépendantes du menu Publications : « Newsletter »
    (bulletins de récolte) et « Annonces » ponctuelles — création,
    suppression et diffusion aux clients (e-mail des comptes clients
    ET des commandes sans compte qui en ont laissé un)."""
    if rubrique not in ("newsletter", "annonces"):
        return redirect("portal:pub_rubrique", rubrique="newsletter")
    exploitant = exploitant_actif(request)
    nb_destinataires = (exploitant.commandes.exclude(email_client="")
                        .values("email_client").distinct().count())

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "bulletin" and rubrique == "newsletter":
            form_b = BulletinForm(request.POST, exploitant=exploitant)
            if form_b.is_valid():
                bulletin = form_b.save(commit=False)
                bulletin.exploitant = exploitant
                bulletin.save()
                messages.success(request, "Newsletter « "
                                 + bulletin.objet + " » créée.")
                return redirect("portal:pub_rubrique",
                                rubrique="newsletter")
        elif action == "annonce" and rubrique == "annonces":
            form_a = AnnonceForm(request.POST)
            if form_a.is_valid():
                annonce = form_a.save(commit=False)
                annonce.exploitant = exploitant
                annonce.save()
                messages.success(request, "Annonce « " + annonce.objet
                                 + " » créée.")
                return redirect("portal:pub_rubrique", rubrique="annonces")
        elif action == "diffuser":
            modele = (Bulletin
                      if request.POST.get("type") == "bulletin"
                      else Annonce)
            publication = modele.objects.filter(
                exploitant=exploitant,
                pk=request.POST.get("publication_id"),
                envoye_le__isnull=True).first()
            if publication is None:
                messages.error(request, "Publication introuvable ou déjà "
                               "diffusée.")
            else:
                vitrine, _cree = ParametresVitrine.objects.get_or_create(
                    exploitant=exploitant)
                connexion = _connexion_email(vitrine)
                expediteur = ((vitrine.messagerie or {}).get("email_from")
                              or settings.DEFAULT_FROM_EMAIL)
                destinataires = list(
                    exploitant.commandes.exclude(email_client="")
                    .values_list("email_client", flat=True).distinct())
                envoyes, echecs = 0, []
                for email in destinataires:
                    try:
                        message = django.core.mail.EmailMessage(
                            f"[{exploitant.nom_espace}] {publication.objet}",
                            publication.corps, expediteur, [email],
                            connection=connexion)
                        message.send()
                        envoyes += 1
                    except Exception:
                        echecs.append(email)
                publication.envoye_le = timezone.now()
                publication.save()
                message = (f"Diffusion terminée : {envoyes} envoi(s) vers "
                           "les clients ayant un e-mail.")
                if echecs:
                    message += f" Échecs : {', '.join(echecs)}."
                messages.success(request, message)
        elif action == "supprimer":
            for modele in (Bulletin, Annonce):
                objet = modele.objects.filter(
                    exploitant=exploitant,
                    pk=request.POST.get("publication_id")).first()
                if objet:
                    objet.delete()
                    messages.info(request, "Publication supprimée.")
                    break
        return redirect("portal:pub_rubrique", rubrique=rubrique)

    if rubrique == "newsletter":
        return render(request, "portal/pro/pub_newsletter.html", {
            "exploitant": exploitant,
            "bulletins": (exploitant.bulletins.order_by(
                "-id").select_related("semaine")),
            "form_bulletin": BulletinForm(exploitant=exploitant),
            "nb_destinataires": nb_destinataires,
        })
    return render(request, "portal/pro/pub_annonces.html", {
        "exploitant": exploitant,
        "annonces": exploitant.annonces.order_by("-id"),
        "form_annonce": AnnonceForm(),
        "nb_destinataires": nb_destinataires,
    })


# ---- Fenêtre « Donner mon avis » (mentions légales, section retours) ----

from .forms import RetourUtilisateurForm  # noqa: E402
from .models import RetourUtilisateur  # noqa: E402


def _retour_form_initial(request):
    """Formulaire de retour pré-rempli d'après la session : gérant
    d'espace pro si le compte en gère un, client s'il est connecté,
    visiteur sinon."""
    if not request.user.is_authenticated:
        return RetourUtilisateurForm(
            initial={"profil": RetourUtilisateur.Profil.VISITEUR})
    if exploitant_pour(request.user) is not None:
        return RetourUtilisateurForm(
            initial={"profil": RetourUtilisateur.Profil.GERANT,
                     "email": request.user.email})
    return RetourUtilisateurForm(
        initial={"profil": RetourUtilisateur.Profil.CLIENT,
                 "email": request.user.email})


def retour_create(request):
    """Réception de la fenêtre « Donner mon avis » : enregistre le
    retour d'usage segmenté par profil — et par activité pour les
    gérants. Honeypot : un robot qui remplit le champ invisible
    repart avec un merci, sans rien écrire en base."""
    if request.method != "POST":
        return redirect("portal:mentions_legales")
    form = RetourUtilisateurForm(request.POST)
    if form.is_valid():
        if not form.cleaned_data.get("piege"):
            form.save()
        messages.success(request, "✅ Merci ! Votre retour est "
                          "enregistré — il oriente directement la "
                          "feuille de route.")
        return redirect("portal:mentions_legales")
    messages.warning(request, "Votre retour n'a pas pu être enregistré : "
                     "vérifiez les champs en rouge de la fenêtre.")
    return render(request, "portal/mentions.html",
                  {"retour_form": form, "retour_ouvert": True})
