"""Processeur de contexte : l'exploitation gérée par le compte courant.

Un compte peut être propriétaire de son exploitation (Exploitant.user) ou
simple membre de l'équipe (MembreExploitation) : dans les deux cas les
menus et l'espace pro affichent la même ferme. `est_proprietaire`
distingue le gestionnaire principal (fiche ferme, SIRET, équipe,
catalogue) des membres limités à la gestion courante.
"""

import datetime

from django.conf import settings
from django.utils import timezone

from django.contrib.auth.models import User

from .marches import identifier_marches
from .models import (Exploitant, StatistiqueQuotidienne, Visiteur,
                     espace_actif, espaces_pro, exploitant_actif,
                     exploitant_pour, nom_affiche)


def exploitant_contexte(request):
    try:
        # Mode espace pro : une sélection de session VALIDE. Sinon le
        # compte est « en Localien » : bandeau et menus côté client,
        # commandes au nom propre (alias) — l'espace par défaut reste
        # affiché en secours pour un accès direct aux pages pro.
        actif = espace_actif(request)
        courant = (actif if actif is not None
                   else exploitant_pour(request.user))
        liste_espaces = (espaces_pro(request.user)
                         if request.user.is_authenticated else [])
        return {
            "exploitant_courant": courant,
            "mode_pro": actif is not None,
            "nb_espaces_pro": len(liste_espaces),
            "espaces_pro_liste": [
                {"pk": espace.pk, "nom": espace.nom_espace,
                 "emoji": espace.emoji_vitrine, "role": role}
                for espace, role in liste_espaces],
            "est_proprietaire": (
                actif is not None
                and (actif.user_id == request.user.id
                     or request.user.is_superuser)),
        }
    except Exception:
        return {"exploitant_courant": None, "mode_pro": False,
                "nb_espaces_pro": 0, "espaces_pro_liste": [],
                "est_proprietaire": False}


def _serie_communaute(champ, lignes):
    """Série 90 jours prête à dessiner (barres en %) + tendance ~7
    jours, pour les fenêtres 📈 des badges du bloc session — mêmes
    mini-graphes que la page Trouver et l'accueil."""
    valeurs = [getattr(ligne, champ) or 0 for ligne in lignes]
    if not valeurs:
        return {"points": [], "tendance": 0, "dernier": 0}
    maximum = max(valeurs) or 1
    points = [{
        "hauteur": round(100 * valeur / maximum),
        "valeur": valeur,
        "jour": ligne.date.strftime("%d/%m"),
        "titre": ligne.date.strftime("%d/%m") + " : " + str(valeur),
    } for ligne, valeur in zip(lignes, valeurs)]
    reference = valeurs[0] if len(valeurs) < 8 else valeurs[-8]
    return {"points": points, "tendance": valeurs[-1] - reference,
            "dernier": valeurs[-1]}


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
            # Badge Pro en navigation pro, badge Client en
            # navigation client (nom propre) — jamais l'inverse.
            if actif is not None and not actif.est_demo:
                rang = Exploitant.objects.filter(
                    activite=actif.activite, est_demo=False,
                    id__lte=actif.id).count()
                # Libellé complet du badge : l'activité et la
                # spécialité vivent dans le badge, plus dans le
                # titre du bloc (« Pro n°1 - 🏆 Restaurant :
                # Pizzeria ! »).
                detail = actif.get_activite_display()
                if actif.specialite:
                    detail += " : " + actif.get_specialite_display()
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
            elif (actif is None
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
        # anonymes distinctes) — mêmes décomptes que la page Trouver ;
        # séries 90 jours pour les fenêtres 📈 des badges.
        try:
            salutation["stats"] = {
                "clients": (User.objects
                            .filter(exploitant__isnull=True,
                                    membres_exploitation__isnull=True)
                            .count()),
                "visiteurs": Visiteur.objects.count(),
            }
            lignes_stats = list(StatistiqueQuotidienne.objects.filter(
                date__gte=timezone.localdate()
                - datetime.timedelta(days=89)).order_by("date"))
            salutation["stats"]["serie_clients"] = _serie_communaute(
                "nb_clients", lignes_stats)
            salutation["stats"]["serie_visiteurs"] = _serie_communaute(
                "nb_visiteurs", lignes_stats)
            # Communauté pro : vignettes 🤝 de la page Trouver
            # rapatriées dans le bloc session — pros inscrits, familles
            # de métiers et points de vente identifiés (marchés et
            # boutiques de producteurs). Bloc PROTÉGÉ : une erreur ici
            # ne doit jamais masquer les badges clients/visiteurs, et
            # la série des pros suit le champ nb_producteurs des
            # statistiques quotidiennes.
            try:
                tous_visibles = Exploitant.objects.filter(visible=True)
                actifs_restauration = (
                    Exploitant.Activite.FOODTRUCK,
                    Exploitant.Activite.TRAITEUR,
                    Exploitant.Activite.RESTAURANT)
                marches_tous = identifier_marches(inclure_demo=True)
                nb_marches = sum(
                    1 for m in marches_tous if m["est_marche"])
                salutation["stats"].update({
                    "pros": tous_visibles.count(),
                    "locaux": tous_visibles.exclude(
                        activite__in=actifs_restauration).count(),
                    "restauration": tous_visibles.filter(
                        activite__in=actifs_restauration).count(),
                    "marches": nb_marches,
                    "boutiques": len(marches_tous) - nb_marches,
                    "serie_pros": _serie_communaute(
                        "nb_producteurs", lignes_stats),
                })
            except Exception:
                pass
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
                # Le mode de NAVIGATION drive le profil du retour :
                # navigation pro = gérant de l'espace courant (avec
                # son activité), navigation publique = client — même
                # si le compte est aussi gérant d'un espace.
                espace = espace_actif(request)
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
