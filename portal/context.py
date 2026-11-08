"""Processeur de contexte : l'exploitation gérée par le compte courant.

Un compte peut être propriétaire de son exploitation (Exploitant.user) ou
simple membre de l'équipe (MembreExploitation) : dans les deux cas les
menus et l'espace pro affichent la même ferme. `est_proprietaire`
distingue le gestionnaire principal (fiche ferme, SIRET, équipe,
catalogue) des membres limités à la gestion courante.
"""

from django.conf import settings
from django.utils import timezone

from .models import Visiteur, exploitant_pour


def exploitant_contexte(request):
    try:
        return {
            "exploitant_courant": exploitant_pour(request.user),
            "est_proprietaire": hasattr(request.user, "exploitant"),
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
