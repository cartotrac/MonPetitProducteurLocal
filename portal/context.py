"""Processeur de contexte : l'exploitation gérée par le compte courant.

Un compte peut être propriétaire de son exploitation (Exploitant.user) ou
simple membre de l'équipe (MembreExploitation) : dans les deux cas les
menus et l'espace pro affichent la même ferme. `est_proprietaire`
distingue le gestionnaire principal (fiche ferme, SIRET, équipe,
catalogue) des membres limités à la gestion courante.
"""

from django.conf import settings
from django.utils import timezone

from django.contrib.auth.models import User

from .models import (Exploitant, Visiteur, espace_actif, espaces_pro,
                     exploitant_actif, exploitant_pour, nom_affiche)


def exploitant_contexte(request):
    try:
        # Mode espace pro : une sélection de session VALIDE. Sinon le
        # compte est « en Localien » : bandeau et menus côté client,
        # commandes au nom propre (alias) — l'espace par défaut reste
        # affiché en secours pour un accès direct aux pages pro.
        actif = espace_actif(request)
        courant = (actif if actif is not None
                   else exploitant_pour(request.user))
        nb_espaces = (len(espaces_pro(request.user))
                      if request.user.is_authenticated else 0)
        return {
            "exploitant_courant": courant,
            "mode_pro": actif is not None,
            "nb_espaces_pro": nb_espaces,
            "est_proprietaire": (
                actif is not None
                and actif.user_id == request.user.id),
        }
    except Exception:
        return {"exploitant_courant": None, "mode_pro": False,
                "nb_espaces_pro": 0, "est_proprietaire": False}


def instance_contexte(request):
    """Identité de l'admin de l'instance (pied de page, mentions légales) :
    réglable via settings.INSTANCE_ADMIN sans toucher aux templates.
    Compte aussi les visiteurs : une ligne par session anonyme, sans
    donnée personnelle (RGPD)."""
    admin = getattr(settings, "INSTANCE_ADMIN", None) or {}
    try:
        cle = request.session.session_key
        if not cle:
            request.session.save()
            cle = request.session.session_key
        if cle:
            Visiteur.objects.update_or_create(
                session_key=cle,
                defaults={"derniere_visite": timezone.now()})
    except Exception:
        pass  # comptage d'audience : jamais bloquant pour l'affichage
    # Bandeau « Vérifiez votre e-mail » (mode doux, non bloquant) :
    # affiché pour un compte connecté dont l'adresse n'est pas encore
    # confirmée — seulement si un SMTP est configuré. Les comptes créés
    # via Google sont vérifiés d'office : pas de bandeau pour eux.
    courriel_a_verifier = False
    if (getattr(settings, "EMAIL_HOST", "")
            and request.user.is_authenticated):
        try:
            from allauth.account.models import EmailAddress
            courriel_a_verifier = not EmailAddress.objects.filter(
                user=request.user, verified=True).exists()
        except Exception:
            pass  # bandeau indicatif : jamais bloquant pour l'affichage
    # Salutation de tête de page (toutes les pages, comptes
    # connectés) : nom affiché (alias > prénom/nom > identifiant) et,
    # en mode espace pro, la structure gérée. Le bloc session est
    # repliable côté navigateur (choix mémorisé).
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
        # Badge Ambassadeur : les 10 premiers espaces pro réels de
        # chaque activité (🏆 grand format pour les 3 premiers, 🏅
        # ensuite) ; pour les clients inscrits, les 100 premiers
        # numérotés ⭐ puis des icônes plus discrètes par palier
        # (✨ 500, 🌟 1000). Comptes et espaces de DÉMONSTRATION
        # exclus du décompte (préfixe « demo. » ou espace démo).
        ambassadeur = None
        try:
            espace = (actif if actif is not None
                      else exploitant_pour(request.user))
            if espace is not None and not espace.est_demo:
                rang = Exploitant.objects.filter(
                    activite=espace.activite, est_demo=False,
                    id__lte=espace.id).count()
                # Libellé complet du badge : l'activité et la
                # spécialité vivent dans le badge, plus dans le
                # titre du bloc (« Pro n°1 - 🏆 Restaurant :
                # Pizzeria ! »).
                detail = espace.get_activite_display()
                if espace.specialite:
                    detail += " : " + espace.get_specialite_display()
                if rang <= 3:
                    ambassadeur = {"icone": "🏆", "rang": rang,
                                   "format": "grand",
                                   "libelle": "Pro n°" + str(rang)
                                              + " - 🏆 " + detail + " !"}
                elif rang <= 10:
                    ambassadeur = {"icone": "🏅", "rang": rang,
                                   "format": "normal",
                                   "libelle": "Pro n°" + str(rang)
                                              + " - 🏅 " + detail + " !"}
            elif (espace is None
                  and not request.user.username.startswith("demo.")
                  and not Exploitant.objects.filter(
                      user=request.user, est_demo=True).exists()):
                rang = (User.objects
                        .exclude(username__startswith="demo.")
                        .exclude(exploitant__est_demo=True)
                        .filter(date_joined__lt=request.user.date_joined)
                        .count() + 1)
                if rang <= 100:
                    ambassadeur = {"icone": "⭐", "rang": rang,
                                   "format": "normal",
                                   "libelle": "Client n°" + str(rang)
                                              + " - ⭐ !"}
                elif rang <= 500:
                    ambassadeur = {"icone": "✨", "rang": 0,
                                   "format": "petit",
                                   "libelle": "Client - ✨ !"}
                elif rang <= 1000:
                    ambassadeur = {"icone": "🌟", "rang": 0,
                                   "format": "mini",
                                   "libelle": "Client - 🌟 !"}
        except Exception:
            ambassadeur = None
        salutation["ambassadeur"] = ambassadeur
        # Rôle complet du badge du titre : « Gérant·e / propriétaire
        # (MonEspace) » ou « Compte rattaché (MonEspace) ».
        if salutation.get("role_libelle"):
            salutation["role_complet"] = (
                salutation["role_libelle"] + " ("
                + salutation["espace"] + ")")
        # Stats communautaires du bloc session (toutes les pages) :
        # clients inscrits (comptes non pro) et visiteurs (sessions
        # anonymes distinctes) — mêmes décomptes que la page Trouver.
        try:
            salutation["stats"] = {
                "clients": (User.objects
                            .filter(exploitant__isnull=True,
                                    membres_exploitation__isnull=True)
                            .count()),
                "visiteurs": Visiteur.objects.count(),
            }
        except Exception:
            salutation["stats"] = None
    # Fenêtre « Donner mon avis » : disponible sur toutes les
    # pages, pré-remplie au maximum d'après la session — profil réel
    # du compte (visiteur, Localien, gérant ou compte rattaché d'un
    # espace pro) et activité de l'espace géré. Après une erreur de
    # saisie, les valeurs tapées reprennent le temps d'un
    # ré-affichage (transitoire en session).
    retour_form = None
    try:
        from .forms import RetourUtilisateurForm
        from .models import RetourUtilisateur
        donnees = None
        try:
            donnees = request.session.pop("mppl_retour_form", None)
        except Exception:
            donnees = None
        if donnees:
            retour_form = RetourUtilisateurForm(donnees)
        else:
            initial = {}
            if request.user.is_authenticated:
                initial["email"] = request.user.email
                espace = espace_actif(request)
                if espace is None:
                    espace = exploitant_pour(request.user)
                if espace is not None:
                    initial["profil"] = RetourUtilisateur.Profil.GERANT
                    initial["activite"] = espace.activite
                else:
                    initial["profil"] = RetourUtilisateur.Profil.CLIENT
            else:
                initial["profil"] = RetourUtilisateur.Profil.VISITEUR
            retour_form = RetourUtilisateurForm(initial=initial)
    except Exception:
        retour_form = None
    return {
        "salutation": salutation,
        "retour_form": retour_form,
        "instance_admin_nom": admin.get("nom", ""),
        "instance_admin_url": admin.get("url", ""),
        "instance_admin_logo": admin.get("logo", ""),
        # « Continuer avec Google » : bouton affiché seulement si un
        # client OAuth est configuré (GOOGLE_CLIENT_ID dans .env).
        "google_connexion": bool(getattr(settings, "GOOGLE_CLIENT_ID", "")),
        "courriel_a_verifier": courriel_a_verifier,
    }
