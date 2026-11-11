"""Processeur de contexte : l'exploitation gérée par le compte courant.

Un compte peut être propriétaire de son exploitation (Exploitant.user) ou
simple membre de l'équipe (MembreExploitation) : dans les deux cas les
menus et l'espace pro affichent la même ferme. `est_proprietaire`
distingue le gestionnaire principal (fiche ferme, SIRET, équipe,
catalogue) des membres limités à la gestion courante.
"""

from django.conf import settings
from django.utils import timezone

from .models import (Visiteur, espace_actif, espaces_pro,
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
    return {
        "salutation": salutation,
        "instance_admin_nom": admin.get("nom", ""),
        "instance_admin_url": admin.get("url", ""),
        "instance_admin_logo": admin.get("logo", ""),
        # « Continuer avec Google » : bouton affiché seulement si un
        # client OAuth est configuré (GOOGLE_CLIENT_ID dans .env).
        "google_connexion": bool(getattr(settings, "GOOGLE_CLIENT_ID", "")),
        "courriel_a_verifier": courriel_a_verifier,
    }
