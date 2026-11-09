"""Processeur de contexte : l'exploitation gérée par le compte courant.

Un compte peut être propriétaire de son exploitation (Exploitant.user) ou
simple membre de l'équipe (MembreExploitation) : dans les deux cas les
menus et l'espace pro affichent la même ferme. `est_proprietaire`
distingue le gestionnaire principal (fiche ferme, SIRET, équipe,
catalogue) des membres limités à la gestion courante.
"""

from django.conf import settings
from django.utils import timezone

from .models import Visiteur, exploitant_actif


def exploitant_contexte(request):
    try:
        courant = exploitant_actif(request)
        return {
            # Espace pro sélectionné pour cette session (multi-espace :
            # choix à la connexion), sinon l'espace par défaut du compte.
            "exploitant_courant": courant,
            "est_proprietaire": (
                courant is not None
                and courant.user_id == request.user.id),
        }
    except Exception:
        return {"exploitant_courant": None, "est_proprietaire": False}


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
    return {
        "instance_admin_nom": admin.get("nom", ""),
        "instance_admin_url": admin.get("url", ""),
        "instance_admin_logo": admin.get("logo", ""),
        # « Continuer avec Google » : bouton affiché seulement si un
        # client OAuth est configuré (GOOGLE_CLIENT_ID dans .env).
        "google_connexion": bool(getattr(settings, "GOOGLE_CLIENT_ID", "")),
    }
