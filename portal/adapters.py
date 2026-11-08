"""Adaptateur socialaccount (django-allauth) : à la connexion Google,
le compte est créé/connecté avec les données du profil Google — et la
photo de profil Google (URL externe : rien n'est hébergé par le portail)
préremplit ProfilClient.photo_url, exactement comme une saisie manuelle
du champ « Photo de profil externe ».

pre_social_login rattache en outre un compte Google à un compte local
existant qui partage le même e-mail (comptes créés avant l'arrivée de
la connexion Google, inscription maison) : connexion directe au lieu
d'un échec d'unicité qui remontait en erreur serveur 500."""

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
        """Avant la connexion Google : si un compte local utilise déjà
        le même e-mail, on rattache le compte Google à ce compte et on
        connecte directement l'utilisateur. Plusieurs comptes avec le
        même e-mail (client ET producteur démo) : message explicite au
        lieu d'une erreur serveur."""
        if sociallogin.is_existing:
            return
        if request.user.is_authenticated:
            return
        email = (sociallogin.user.email or "").strip()
        if not email:
            return
        correspondants = list(User.objects.filter(email__iexact=email))
        if len(correspondants) == 1:
            sociallogin.connect(request, correspondants[0])
            perform_login(request, correspondants[0],
                          email_verification="none")
            raise ImmediateHttpResponse(
                redirect("portal:apres_connexion"))
        if len(correspondants) > 1:
            messages.error(request,
                           "Plusieurs comptes utilisent déjà cet e-mail "
                           "(client et producteur) : connectez-vous avec "
                           "votre mot de passe.")
            raise ImmediateHttpResponse(redirect("login"))

    def save_user(self, request, sociallogin, form=None, commit=True):
        user = super().save_user(request, sociallogin, form=form,
                                 commit=commit)
        photo = ((sociallogin.account.extra_data or {})
                 .get("picture") or "")
        if photo:
            profil, _cree = ProfilClient.objects.get_or_create(user=user)
            if not profil.photo_url:
                profil.photo_url = photo
                profil.save(update_fields=["photo_url"])
        return user
