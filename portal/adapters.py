"""Adaptateur socialaccount (django-allauth) : à la connexion Google,
le compte est créé/connecté avec les données du profil Google — et la
photo de profil Google (URL externe : rien n'est hébergé par le portail)
préremplit ProfilClient.photo_url, exactement comme une saisie manuelle
du champ « Photo de profil externe »."""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import ProfilClient


class PortailSocialAdapter(DefaultSocialAccountAdapter):
    """Connexion Google en 1 clic (inscription client « Devenir
    Localien », connexion, préremplissage de l'inscription pro)."""

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
