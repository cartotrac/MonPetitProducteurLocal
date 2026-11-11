"""Adaptateur socialaccount (django-allauth) : à la connexion Google,
le compte est créé/connecté avec les données du profil Google — et la
photo de profil Google (URL externe : rien n'est hébergé par le portail)
préremplit ProfilClient.photo_url, exactement comme une saisie manuelle
du champ « Photo de profil externe ».

pre_social_login rattache un compte Google à un compte local existant
uniquement si l'e-mail de ce compte est VÉRIFIÉ (EmailAddress vérifiée :
comptes créés par Google ou e-mails confirmés). Sans cette condition,
n'importe qui pourrait inscrire l'e-mail d'une victime et hériter de sa
connexion Google à sa première visite — prise de contrôle avant
inscription (audit sécurité)."""

from allauth.account.models import EmailAddress
from allauth.account.utils import perform_login
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import redirect

from .models import ProfilClient


class PortailSocialAdapter(DefaultSocialAccountAdapter):
    """Connexion Google en 1 clic (inscription client « Devenir
    Localien », connexion, préremplissage de l'inscription pro)."""

    def pre_social_login(self, request, sociallogin):
        """Avant la connexion Google : rattacher et connecter
        directement si UN compte local VÉRIFIÉ porte le même e-mail.
        Comptes locaux non vérifiés : jamais rattachés — message et
        retour au formulaire de connexion (mot de passe).

        Le contrôle tourne AUSSI pour un visiteur déjà connecté qui
        clique « Continuer avec Google » : sans lui, allauth créait
        un SECOND compte portant le même e-mail (l'e-mail local non
        vérifié n'arrête pas l'auto-signup), et la connexion par
        e-mail/identifiant devenait ambiguë — « mot de passe erroné »
        trompeur sur le mauvais compte."""
        if sociallogin.is_existing:
            return
        # Rattachement explicite (« connecter Google à MON compte ») :
        # allauth s'en charge seul — pas d'interférence.
        process = (sociallogin.state or {}).get("process")
        if request.user.is_authenticated and process == "connect":
            return
        email = (sociallogin.user.email or "").strip()
        if not email:
            return
        correspondants = list(User.objects.filter(email__iexact=email))
        if (len(correspondants) == 1
                and EmailAddress.objects.filter(
                    user=correspondants[0], verified=True).exists()):
            sociallogin.connect(request, correspondants[0])
            perform_login(request, correspondants[0],
                          email_verification="none")
            raise ImmediateHttpResponse(
                redirect("portal:apres_connexion"))
        if correspondants:
            messages.error(request,
                           "Un compte existe déjà avec cet e-mail : "
                           "connectez-vous avec votre mot de passe. (Le "
                           "rattachement Google ne se fait que sur un "
                           "e-mail vérifié.)")
            raise ImmediateHttpResponse(redirect("login"))

    def save_user(self, request, sociallogin, form=None):
        # allauth 65 appelle save_user sans « commit » : signature
        # strictement identique à DefaultSocialAccountAdapter.
        user = super().save_user(request, sociallogin, form=form)
        # Marqueur de session : ce compte vient d'être créé via Google —
        # l'atterrissage passe par la page de choix d'espace (client ou
        # pro), sauf si le parcours d'origine a déjà fixé l'intention.
        request.session["mppl_compte_neuf"] = True
        photo = ((sociallogin.account.extra_data or {})
                 .get("picture") or "")
        if photo:
            profil, _cree = ProfilClient.objects.get_or_create(user=user)
            if not profil.photo_url:
                profil.photo_url = photo
                profil.save(update_fields=["photo_url"])
        return user
