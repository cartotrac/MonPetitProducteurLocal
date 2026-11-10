"""Envois e-mail / SMS aux clients (issue #3) — zéro dépendance externe.

E-mail : chaque exploitation peut configurer son propre serveur SMTP
(page Paramètres → Messagerie) ; sans configuration locale, on retombe
sur le SMTP global du serveur (variables d'environnement EMAIL_HOST…).
Sans aucun SMTP, Django journalise au lieu d'envoyer et l'interface
informe l'exploitant.

SMS : passerelle HTTP Free Mobile (notificationsAPI, identifiants dans
l'admin Django → Configuration messagerie). Les autres passerelles
(OVH, Twilio, HTTP perso) resteront à brancher en V2.

Modèles personnalisables par l'exploitant (ModeleMessage), avec défauts
embarqués et repli propre si le modèle personnalisé est cassé.
"""
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage, get_connection, send_mail

from .models import (ConfigMessagerie, ModeleMessage, ParametresVitrine,
                     PreferenceContact)

EMAILS_PAR_DEFAUT = {
    "CONFIRMATION_COMMANDE": {
        "objet": "Commande confirmée — {ferme}",
        "corps": ("Bonjour {client},\n\n"
                  "Votre commande est confirmée ! Elle sera préparée en "
                  "panier n°{numero} pour le {date}.\n\n"
                  "Total : {total} €\n\n"
                  "Merci de votre confiance,\n"
                  "{ferme}"),
    },
    "PANIER_PRET": {
        "objet": "Votre panier est prêt — {ferme}",
        "corps": ("Bonjour {client},\n\n"
                  "Votre panier n°{numero} est prêt ! Vous pouvez venir le "
                  "récupérer le {date}.\n\n"
                  "Total : {total} €\n\n"
                  "À bientôt,\n"
                  "{ferme}"),
    },
    "LIVRAISON_FAITE": {
        "objet": "Votre panier a été livré — {ferme}",
        "corps": ("Bonjour {client},\n\n"
                  "Votre panier n°{numero} du {date} a bien été livré. "
                  "Merci de votre confiance !\n\n"
                  "{ferme}"),
    },
    "PANIER_ANNULE": {
        "objet": "Panier annulé — {ferme}",
        "corps": ("Bonjour {client},\n\n"
                  "Votre panier n°{numero} du {date} a été annulé : "
                  "{motif}\n\n"
                  "Vous pouvez recommander depuis la page « Mes "
                  "commandes » (quantités, date et point de livraison "
                  "repris, tout reste modifiable).\n\n"
                  "{ferme}"),
    },
}

SMS_PAR_DEFAUT = {
    "CONFIRMATION_COMMANDE": "Commande confirmee : panier n°{numero} pour le {date} — {ferme}",
    "PANIER_PRET": "Panier n°{numero} pret a recuperer le {date} — {ferme}",
    "LIVRAISON_FAITE": "Panier n°{numero} livre le {date} — merci ! {ferme}",
    "PANIER_ANNULE": "Panier n°{numero} du {date} annule : {motif} — {ferme}",
}


def _contexte(panier):
    return {
        "client": panier.nom_client,
        "ferme": panier.exploitant.nom_espace,
        # Alias de compatibilité avec les placeholders
        # documentés de ModeleMessage : {{ espace }} et
        # {{ panier }} (numéro).
        "espace": panier.exploitant.nom_espace,
        "panier": panier.numero,
        "numero": panier.numero,
        "date": panier.date_livraison.strftime("%d/%m/%Y"),
        "total": str(panier.total).replace(".", ","),
        "creneau": str(panier.creneau) if panier.creneau else "",
        "point": (panier.point_affiche["nom"]
                  if panier.point_livraison else ""),
        "motif": panier.motif_annulation or "annulé par le producteur",
    }


def _modele(exploitant, type_msg, canal):
    """Modèle personnalisé actif s'il existe, sinon défaut embarqué."""
    perso = (ModeleMessage.objects
             .filter(exploitant=exploitant, type=type_msg, canal=canal,
                     actif=True).first())
    if canal == "SMS":
        defaut = SMS_PAR_DEFAUT.get(type_msg)
    else:
        defaut = EMAILS_PAR_DEFAUT.get(type_msg)
    if perso:
        return perso.objet or (defaut["objet"] if defaut else type_msg), perso.corps
    if defaut is None:
        return type_msg, ""
    return (defaut.get("objet", ""), defaut.get("corps", ""))


def envoyer_sms(exploitant, texte):
    """Envoi via la passerelle configurée par l'exploitant.
    Retourne (succes, message)."""
    cfg = ConfigMessagerie.objects.filter(exploitant=exploitant).first()
    if not cfg or not cfg.passerelle_sms or not cfg.config_sms:
        return False, ("non configuré (admin Django → Configuration "
                       "messagerie)")
    if cfg.passerelle_sms == ConfigMessagerie.PasserelleSMS.FREE:
        identifiant = str(cfg.config_sms.get("user", "")).strip()
        cle = str(cfg.config_sms.get("pass", "")).strip()
        if not identifiant or not cle:
            return False, "identifiants Free Mobile manquants"
        url = ("https://smsapi.free-mobile.fr/sendmsg?"
               + urllib.parse.urlencode(
                   {"user": identifiant, "pass": cle,
                    "msg": texte[:480]}))
        try:
            with urllib.request.urlopen(url, timeout=10) as reponse:
                if reponse.status == 200:
                    return True, "envoyé"
                return False, f"code HTTP {reponse.status}"
        except Exception as err:  # URLError, HTTPError, timeout
            return False, f"échec : {err}"
    return False, (f"passerelle {cfg.get_passerelle_sms_display()} "
                  "non implémentée en V1")


def _connexion_smtp_exploitant(exploitant):
    """Connexion SMTP propre à l'exploitation (page Paramètres →
    Messagerie) : None si l'exploitation n'en configure pas, auquel cas
    on retombe sur le backend global du serveur. Retourne
    (connexion, expediteur)."""
    vitrine = (ParametresVitrine.objects
               .filter(exploitant=exploitant).first())
    m = (vitrine.messagerie if vitrine else None) or {}
    expediteur = m.get("email_from") or settings.DEFAULT_FROM_EMAIL
    if not m.get("email_host"):
        return None, expediteur
    try:
        port = int(m.get("email_port") or 25)
    except (TypeError, ValueError):
        port = 25
    connexion = get_connection(
        host=m["email_host"], port=port,
        username=m.get("email_user") or None,
        password=m.get("email_password") or None,
        use_tls=bool(m.get("email_tls")), fail_silently=False)
    return connexion, expediteur


def notifier_client(request, panier, type_msg):
    """Notifie le client du panier selon son canal préféré (e-mail par
    défaut). L'e-mail part par le SMTP de l'exploitation s'il en a
    configuré un (Paramètres → Messagerie), sinon par celui du serveur.
    Feedback via messages Django — TOUJOURS informatif : une
    notification non envoyée n'invalide jamais la commande/le panier,
    qui sont déjà créés à ce stade. Retourne True si envoyé."""
    pref = None
    if panier.client_id:
        pref = (PreferenceContact.objects
                .filter(exploitant=panier.exploitant, client=panier.client)
                .first())
    canal = pref.canal if pref else PreferenceContact.Canal.EMAIL
    try:
        objet_modele, corps_modele = _modele(panier.exploitant, type_msg,
                                             canal)
        ctx = _contexte(panier)
        objet = objet_modele.format(**ctx)
        corps = corps_modele.format(**ctx)
    except (KeyError, IndexError, ValueError):
        objet, corps = type_msg, ("(Modèle de message personnalisé "
                                  "invalide — corrigez-le dans l'admin.)")
    except Exception as err:  # jamais bloquant pour la commande/le panier
        objet, corps = type_msg, ("(Erreur interne de notification : "
                                  + str(err) + ")")

    if canal == PreferenceContact.Canal.SMS:
        if not panier.telephone_client:
            messages.info(request, "ℹ️ SMS non envoyé : numéro de téléphone "
                          "absent. La commande, elle, est bien enregistrée.")
            return False
        ok, info = envoyer_sms(panier.exploitant, corps)
        if ok:
            messages.success(request, "📱 SMS " + info + ".")
        else:
            messages.info(request, "ℹ️ SMS non envoyé (" + info
                          + "). La commande, elle, est bien enregistrée.")
        return ok

    # Canal e-mail
    if not panier.email_client:
        messages.info(request, "ℹ️ Notification e-mail non envoyée : "
                      "adresse du client absente. La commande, elle, est "
                      "bien enregistrée.")
        return False
    connexion, expediteur = _connexion_smtp_exploitant(panier.exploitant)
    if connexion is None and not getattr(settings, "EMAIL_HOST", ""):
        messages.info(request, "ℹ️ Notification e-mail non envoyée : "
                      "aucun serveur SMTP configuré (ni pour l'espace dans "
                      "Paramètres → Messagerie, ni pour le serveur : "
                      "EMAIL_HOST dans le .env puis redémarrage). La "
                      "commande, elle, est bien enregistrée — rien n'est "
                      "perdu.")
        return False
    try:
        if connexion is not None:
            # SMTP propre à l'exploitation : les notifications partent au
            # nom de l'espace (bouton « test_email » de la même page).
            EmailMessage(objet, corps, expediteur, [panier.email_client],
                         connection=connexion).send()
        else:
            send_mail(objet, corps, expediteur, [panier.email_client],
                      fail_silently=False)
    except Exception as err:
        messages.info(request, "ℹ️ Notification e-mail non envoyée (échec "
                      "SMTP : " + str(err) + "). La commande, elle, est "
                      "bien enregistrée.")
        return False
    messages.success(request, "✉️ E-mail envoyé à " + panier.email_client
                     + ("" if connexion is None
                        else " (via le serveur de votre espace)") + ".")
    return True
