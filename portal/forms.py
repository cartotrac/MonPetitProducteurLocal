from django import forms
from django.contrib.auth.forms import (AuthenticationForm,
                                       UserCreationForm)
from django.contrib.auth.models import User

from .models import (Annonce, Bulletin, Categorie, Exploitant, Produit,
                    ProfilClient, SemaineRecolte)


def _aide_mot_de_passe(form):
    """Aide courte et rassurante pour les mots de passe (au lieu du
    long texte par défaut de Django, anxiogène à l'inscription)."""
    form.fields["password1"].help_text = (
        "Au moins 8 caractères. Évitez les mots de passe trop courants.")
    form.fields["password2"].help_text = (
        "Retapez le mot de passe pour vérifier.")


class InscriptionExploitantForm(UserCreationForm):
    """Inscription exploitant simplifiée : compte + ferme minimale.
    Pas de nom d'utilisateur à inventer : l'e-mail sert d'identifiant.
    Nom de la ferme, activité et localisation à la création ; tout le
    reste (SIRET, mode de production, logo, description, téléphone,
    réseaux…) se complète ensuite dans la page ⚙️ Paramètres."""

    nom_ferme = forms.CharField(
        label="Nom de l'exploitation", max_length=150,
        help_text="Le nom affiché sur votre vitrine (modifiable ensuite).")
    est_demo = forms.BooleanField(
        label="Exploitation de démonstration", required=False,
        help_text="Cochez pour marquer cette exploitation comme fictive "
                  "(test, formation, démo) : un badge 🧪 DÉMO la distingue "
                  "sur le portail. ⚠️ Attention : une exploitation de "
                  "démonstration peut être supprimée sans préavis lors "
                  "des purges des jeux de démo.")
    activite = forms.ChoiceField(
        label="Activité", choices=Exploitant.Activite.choices,
        initial=Exploitant.Activite.MARAICHER,
        help_text="Le symbole de votre métier apparaît sur votre fiche "
                  "publique et les vignettes de recherche.")
    specialite = forms.ChoiceField(
        label="Spécialité (si foodtruck)", required=False,
        choices=[("", "— Précisez la spécialité —")]
        + list(Exploitant.Specialite.choices),
        help_text="Exigée pour un foodtruck : pizza, burger… "
                  "elle s'affiche sur les pages publiques.")
    adresse = forms.CharField(label="Adresse", max_length=255, required=False)
    ville = forms.CharField(label="Ville", max_length=100, required=False)
    code_postal = forms.CharField(
        label="Code postal", max_length=10, required=False,
        help_text="Positionne votre exploitation sur la carte et sert à "
                  "la recherche par département.")
    departement = forms.CharField(
        label="Département (auto si vide : 2 premiers chiffres du code "
              "postal)", max_length=3, required=False)
    latitude = forms.FloatField(
        label="Latitude (optionnel, pour la carte)", required=False,
        widget=forms.NumberInput(attrs={"step": "any"}),
        help_text="Position sur la carte (optionnel)")
    longitude = forms.FloatField(
        label="Longitude (optionnel, pour la carte)", required=False,
        widget=forms.NumberInput(attrs={"step": "any"}),
        help_text="Position sur la carte (optionnel)")
    telephone = forms.CharField(label="Téléphone", max_length=20,
                                required=False)
    photo_externe = forms.URLField(
        label="Photo de profil externe (drive, cloud, réseau — rien "
              "n'est hébergé sur le portail)", required=False)

    field_order = ["nom_ferme", "est_demo", "activite", "specialite",
                   "adresse", "ville", "code_postal", "departement",
                   "latitude", "longitude", "first_name", "last_name",
                   "email", "telephone", "photo_externe", "password1",
                   "password2"]

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Prénom", "last_name": "Nom",
                  "email": "E-mail"}
        help_texts = {"email": "Sert d'identifiant de connexion : "
                               "pas de nom d'utilisateur à inventer."}

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if (User.objects.filter(username__iexact=email).exists()
                or User.objects.filter(email__iexact=email).exists()):
            raise forms.ValidationError(
                "Un compte existe déjà avec cet e-mail. "
                "Essayez de vous connecter, ou demandez un nouveau "
                "mot de passe via « Mot de passe oublié ? ».")
        return email

    def clean(self):
        donnees = super().clean()
        if (donnees.get("activite") == Exploitant.Activite.FOODTRUCK
                and not donnees.get("specialite")):
            self.add_error(
                "specialite",
                "Précisez la spécialité de votre foodtruck (pizza, "
                "burger…) : elle apparaît sur les pages publiques et "
                "les vignettes.")
        elif donnees.get("activite") != Exploitant.Activite.FOODTRUCK:
            donnees["specialite"] = ""
        return donnees

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aide_mot_de_passe(self)
        # Symboles d'activité dans le choix (même visuel que les
        # vignettes et pages publiques) et emojis de spécialité.
        self.fields["activite"].choices = [
            (code, Exploitant.ACTIVITE_EMOJIS.get(code, "🌾") + " "
             + libelle)
            for code, libelle in Exploitant.Activite.choices]
        self.fields["specialite"].choices = [
            ("", "— Précisez la spécialité —")] + [
            (code, Exploitant.SPECIALITE_EMOJIS.get(code, "🚚") + " "
             + libelle)
            for code, libelle in Exploitant.Specialite.choices]

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"].lower().strip()
        user.username = email
        user.email = email
        user.last_name = self.cleaned_data.get("last_name", "") or ""
        if commit:
            user.save()
            code_postal = self.cleaned_data.get("code_postal", "") or ""
            Exploitant.objects.create(
                user=user,
                nom_ferme=self.cleaned_data["nom_ferme"],
                activite=self.cleaned_data.get(
                    "activite", Exploitant.Activite.MARAICHER),
                specialite=self.cleaned_data.get("specialite", "") or "",
                est_demo=bool(self.cleaned_data.get("est_demo")),
                adresse=self.cleaned_data.get("adresse", ""),
                ville=self.cleaned_data.get("ville", ""),
                code_postal=code_postal,
                departement=(self.cleaned_data.get("departement", "")
                             or (code_postal[:2]
                                 if len(code_postal) >= 2 else "")),
                latitude=self.cleaned_data.get("latitude"),
                longitude=self.cleaned_data.get("longitude"))
            ProfilClient.objects.create(
                user=user,
                telephone=self.cleaned_data.get("telephone", ""),
                photo_url=self.cleaned_data.get("photo_externe", "") or "")
        return user


class InscriptionFermeSeuleForm(forms.Form):
    """Création de l'espace pro pour un compte DÉJÀ existant (cas
    « Continuer avec Google ») : seul le bloc « Ma ferme » est
    demandé — prénom, nom, e-mail et photo viennent du compte courant
    (profil Google ou inscription maison)."""

    nom_ferme = forms.CharField(
        label="Nom de l'exploitation", max_length=150,
        help_text="Le nom affiché sur votre vitrine (modifiable ensuite).")
    est_demo = forms.BooleanField(
        label="Exploitation de démonstration", required=False,
        help_text="Cochez pour marquer cette exploitation comme fictive "
                  "(test, formation, démo) : un badge 🧪 DÉMO la distingue "
                  "sur le portail. ⚠️ Attention : une exploitation de "
                  "démonstration peut être supprimée sans préavis lors "
                  "des purges des jeux de démo.")
    activite = forms.ChoiceField(
        label="Activité", choices=Exploitant.Activite.choices,
        initial=Exploitant.Activite.MARAICHER,
        help_text="Le symbole de votre métier apparaît sur votre fiche "
                  "publique et les vignettes de recherche.")
    specialite = forms.ChoiceField(
        label="Spécialité (si foodtruck)", required=False,
        choices=[("", "— Précisez la spécialité —")]
        + list(Exploitant.Specialite.choices),
        help_text="Exigée pour un foodtruck : pizza, burger… "
                  "elle s'affiche sur les pages publiques.")
    adresse = forms.CharField(label="Adresse", max_length=255, required=False)
    ville = forms.CharField(label="Ville", max_length=100, required=False)
    code_postal = forms.CharField(
        label="Code postal", max_length=10, required=False,
        help_text="Positionne votre exploitation sur la carte et sert à "
                  "la recherche par département.")
    departement = forms.CharField(
        label="Département (auto si vide : 2 premiers chiffres du code "
              "postal)", max_length=3, required=False)
    latitude = forms.FloatField(
        label="Latitude (optionnel, pour la carte)", required=False,
        widget=forms.NumberInput(attrs={"step": "any"}),
        help_text="Position sur la carte (optionnel)")
    longitude = forms.FloatField(
        label="Longitude (optionnel, pour la carte)", required=False,
        widget=forms.NumberInput(attrs={"step": "any"}),
        help_text="Position sur la carte (optionnel)")

    field_order = ["nom_ferme", "est_demo", "activite", "specialite",
                   "adresse", "ville", "code_postal", "departement",
                   "latitude", "longitude"]

    def clean(self):
        donnees = super().clean()
        if (donnees.get("activite") == Exploitant.Activite.FOODTRUCK
                and not donnees.get("specialite")):
            self.add_error(
                "specialite",
                "Précisez la spécialité de votre foodtruck (pizza, "
                "burger…) : elle apparaît sur les pages publiques et "
                "les vignettes.")
        elif donnees.get("activite") != Exploitant.Activite.FOODTRUCK:
            donnees["specialite"] = ""
        return donnees

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Symboles d'activité et de spécialité : même visuel que
        # l'inscription complète.
        self.fields["activite"].choices = [
            (code, Exploitant.ACTIVITE_EMOJIS.get(code, "🌾") + " "
             + libelle)
            for code, libelle in Exploitant.Activite.choices]
        self.fields["specialite"].choices = [
            ("", "— Précisez la spécialité —")] + [
            (code, Exploitant.SPECIALITE_EMOJIS.get(code, "🚚") + " "
             + libelle)
            for code, libelle in Exploitant.Specialite.choices]

    def save(self, utilisateur):
        """Rattache la nouvelle exploitation au compte existant : les
        informations personnelles (e-mail, nom, photo) restent celles
        du compte courant."""
        code_postal = self.cleaned_data.get("code_postal", "") or ""
        return Exploitant.objects.create(
            user=utilisateur,
            nom_ferme=self.cleaned_data["nom_ferme"],
            activite=self.cleaned_data.get(
                "activite", Exploitant.Activite.MARAICHER),
            specialite=self.cleaned_data.get("specialite", "") or "",
            est_demo=bool(self.cleaned_data.get("est_demo")),
            adresse=self.cleaned_data.get("adresse", ""),
            ville=self.cleaned_data.get("ville", ""),
            code_postal=code_postal,
            departement=(self.cleaned_data.get("departement", "")
                         or (code_postal[:2]
                             if len(code_postal) >= 2 else "")),
            latitude=self.cleaned_data.get("latitude"),
            longitude=self.cleaned_data.get("longitude"))


class InscriptionClientForm(UserCreationForm):
    """Inscription client : l'e-mail sert d'identifiant (pas de nom
    d'utilisateur à inventer)."""

    telephone = forms.CharField(
        label="Téléphone", max_length=20, required=False,
        help_text="Optionnel — utile pour être prévenu d'un souci de "
                  "livraison.")
    photo_externe = forms.URLField(
        label="Photo de profil externe (drive, cloud, réseau — rien "
              "n'est hébergé sur le portail)", required=False)

    field_order = ["first_name", "last_name", "email", "telephone",
                   "photo_externe", "password1", "password2"]

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Prénom", "last_name": "Nom",
                  "email": "E-mail"}
        help_texts = {"email": "Sert d'identifiant de connexion."}

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if (User.objects.filter(username__iexact=email).exists()
                or User.objects.filter(email__iexact=email).exists()):
            raise forms.ValidationError(
                "Un compte existe déjà avec cet e-mail. "
                "Essayez de vous connecter, ou demandez un nouveau "
                "mot de passe via « Mot de passe oublié ? ».")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aide_mot_de_passe(self)

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"].lower().strip()
        user.username = email
        user.email = email
        user.last_name = self.cleaned_data.get("last_name", "") or ""
        if commit:
            user.save()
            ProfilClient.objects.create(
                user=user,
                telephone=self.cleaned_data.get("telephone", ""),
                photo_url=self.cleaned_data.get("photo_externe", "") or "")
        return user


class ConnexionForm(AuthenticationForm):
    """Connexion par nom d'utilisateur OU e-mail (les comptes créés
    via l'inscription utilisent l'e-mail comme identifiant)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nom d'utilisateur ou e-mail"

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username and not User.objects.filter(
                username__iexact=username).exists():
            autre = User.objects.filter(
                email__iexact=username).first()
            if autre:
                return autre.username
        return username


class ProduitForm(forms.ModelForm):
    image_externe = forms.URLField(
        label="Lien photo externe (drive, cloud, réseau — rien n'est "
              "hébergé sur le portail)", required=False)

    class Meta:
        model = Produit
        fields = ["nom", "categorie", "description", "illustration",
                  "unite_vente", "prix", "actif"]
        labels = {"nom": "Nom", "categorie": "Catégorie",
                  "description": "Description", "illustration": "Photo",
                  "unite_vente": "Unité de vente",
                  "prix": "Prix de référence (€)",
                  "actif": "Actif"}
        help_texts = {
            "nom": "Ex : « Tomates anciennes », « Œufs plein air »…",
            "description": "Quelques mots suffisent : variété, goût, "
                           "préparation…",
            "illustration": "2 Mo max — optionnelle.",
            "prix": "Prix indicatif affiché aux clients ; vous "
                    "l'ajustez chaque semaine dans la récolte si besoin.",
            "actif": "Décochez pour masquer le produit sans le supprimer.",
        }

    def __init__(self, *args, exploitant=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Les catégories sont propres à chaque exploitant (issue #5).
        if exploitant is not None:
            self.fields["categorie"].queryset = Categorie.objects.filter(
                exploitant=exploitant)
        else:
            self.fields["categorie"].queryset = Categorie.objects.none()
        if self.instance and self.instance.pk:
            self.fields["image_externe"].initial = (
                self.instance.attributs or {}).get("image_url", "")


class ProfilExploitantForm(forms.ModelForm):
    """Édition de sa fiche par un maraîcher (badge SIRET inclus)."""
    logo_externe = forms.URLField(
        label="Lien logo externe (drive, cloud, réseau — alternative au "
              "fichier : rien n'est hébergé sur le portail)", required=False)
    site_web = forms.URLField(
        label="Site web de l'exploitation", required=False)
    facebook = forms.URLField(label="Page Facebook", required=False)
    instagram = forms.URLField(label="Compte Instagram", required=False)
    field_order = ["nom_ferme", "activite", "specialite", "siret", "mode_production",
                   "logo", "logo_externe", "description", "adresse", "ville",
                   "code_postal", "departement", "telephone", "latitude",
                   "longitude", "est_demo", "mode_fonctionnement"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Symboles d'activité dans le choix (cohérents avec les
        # vignettes publiques) et emojis de spécialité foodtruck.
        self.fields["activite"].choices = [
            (code, Exploitant.ACTIVITE_EMOJIS.get(code, "🌾") + " "
             + libelle)
            for code, libelle in Exploitant.Activite.choices]
        self.fields["specialite"].choices = [
            (code, Exploitant.SPECIALITE_EMOJIS.get(code, "🚚") + " "
             + libelle)
            for code, libelle in Exploitant.Specialite.choices]

    class Meta:
        model = Exploitant
        fields = ["nom_ferme", "activite", "specialite", "siret", "mode_production",
                  "logo", "description", "adresse", "ville", "code_postal",
                  "departement", "telephone", "latitude", "longitude",
                  "est_demo", "mode_fonctionnement"]
        labels = {"nom_ferme": "Nom de l'exploitation",
                  "specialite": "Spécialité (foodtruck : sandwichs & "
                                "plats, pizza, burger, traiteur, "
                                "rôtisseur)",
                  "activite": "Activité",
                  "siret": "SIRET (14 chiffres)",
                  "mode_production": "Mode de production",
                  "logo": "Logo miniature (fichier)",
                  "description": "Présentation",
                  "departement": "Département (auto si vide : 2 premiers chiffres du code postal)",
                  "latitude": "Latitude (optionnel, pour la carte)",
                  "longitude": "Longitude (optionnel, pour la carte)",
                  "est_demo": "Exploitation de démonstration",
                  "mode_fonctionnement": "Mode de fonctionnement"}
        help_texts = {"est_demo": (
            "Cochez pour marquer cette exploitation comme fictive "
            "(test, formation, démo) : un badge 🧪 DÉMO la distingue "
            "sur le portail.")}

    def clean_specialite(self):
        """La spécialité n'a de sens que pour les foodtrucks : on la
        vide silencieusement pour toute autre activité."""
        specialite = self.cleaned_data.get("specialite")
        activite = self.cleaned_data.get("activite")
        if specialite and activite != Exploitant.Activite.FOODTRUCK:
            return ""
        return specialite


class ProfilPersonnelForm(forms.Form):
    """Informations personnelles du compte individuel (client, maraîcher
    propriétaire ou membre d'une équipe) : prénom, nom, téléphone, photo
    (lien externe). L'e-mail, donnée sensible (récupération du compte en
    cas de mot de passe perdu), se gère dans la section 🔐 Sécurité."""

    prenom = forms.CharField(label="Prénom", max_length=150, required=False)
    nom = forms.CharField(label="Nom", max_length=150, required=False)
    telephone = forms.CharField(label="Téléphone", max_length=20,
                                required=False)
    photo_externe = forms.URLField(
        label="Photo de profil externe (drive, cloud, réseau — rien "
              "n'est hébergé sur le portail)", required=False)


class BulletinForm(forms.ModelForm):
    """Newsletter / bulletin diffusé aux clients d'une exploitation."""

    class Meta:
        model = Bulletin
        fields = ["semaine", "objet", "corps"]
        labels = {"semaine": "Récolte liée (optionnel)",
                  "objet": "Objet du message",
                  "corps": "Message"}

    def __init__(self, *args, exploitant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if exploitant is not None:
            self.fields["semaine"].queryset = SemaineRecolte.objects.filter(
                exploitant=exploitant).order_by("-lundi")
        else:
            self.fields["semaine"].queryset = (
                SemaineRecolte.objects.none())


class AnnonceForm(forms.ModelForm):
    """Annonce ponctuelle (« paniers disponibles », …)."""

    class Meta:
        model = Annonce
        fields = ["objet", "corps"]
        labels = {"objet": "Objet de l'annonce", "corps": "Annonce"}


class MessagerieForm(forms.Form):
    """Serveur d'envoi d'e-mails et passerelle SMS de l'exploitation
    (page Paramètres, propriétaire). Le SMTP propre à l'exploitation
    est utilisé pour la diffusion des publications ; la passerelle SMS
    servira aux envois de disponibilité hebdo des produits. Tout champ
    laissé vide retire le paramètre correspondant."""

    email_host = forms.CharField(
        label="Serveur SMTP (ex : smtp.alwaysdata.com)", required=False)
    email_port = forms.IntegerField(
        label="Port SMTP (25 par défaut)", required=False,
        min_value=1, max_value=65535)
    email_user = forms.CharField(label="Utilisateur SMTP", required=False)
    email_password = forms.CharField(
        label="Mot de passe SMTP", required=False,
        widget=forms.PasswordInput(render_value=True))
    email_tls = forms.BooleanField(
        label="Connexion chiffrée (STARTTLS)", required=False)
    email_from = forms.EmailField(
        label="Adresse d'expédition (« From »)", required=False)
    sms_url = forms.URLField(
        label="Passerelle SMS — URL de l'API (ex : https://api…/messages)",
        required=False)
    sms_cle = forms.CharField(
        label="Passerelle SMS — clé / jeton d'API", required=False,
        widget=forms.PasswordInput(render_value=True))
    sms_expediteur = forms.CharField(
        label="Passerelle SMS — nom d'expéditeur (11 caractères max)",
        required=False, max_length=11)
    sms_dispo_hebdo = forms.BooleanField(
        label="Envoyer chaque semaine la disponibilité des produits par SMS",
        required=False)

