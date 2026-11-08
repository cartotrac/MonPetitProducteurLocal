from django.contrib.auth.models import User
from django.db import models, transaction
from django.urls import reverse


def logo_chemin(instance, filename):
    return f"exploitants/{instance.pk}/logo.png"


def banniere_chemin(instance, filename):
    return f"exploitants/{instance.pk}/banniere.jpg"


def illustration_produit_chemin(instance, filename):
    return f"exploitants/{instance.pk}/produits/{instance.slug}.jpg"


class Exploitant(models.Model):
    """Profil exploitant : un compte utilisateur = une exploitation.

    Nommage français sans accent, voir docs/DATA_MODEL.md.
    """

    class ModeProduction(models.TextChoices):
        AB = "AB", "Agriculture Biologique (AB)"
        PERMA = "PERMA", "Permaculture"
        PAYSAN = "PAYSAN", "Agriculture paysanne"
        RAISONNE = "RAISONNE", "Agriculture raisonnée"
        CONV = "CONV", "Conventionnelle"

    class Activite(models.TextChoices):
        """Segmentation des producteurs locaux : les pros existants sont
        des maraîchers ; d'autres activités (élevage, fromagerie,
        arboriculture…) arriveront, avec leurs propres listes de
        produits. La recherche publique filtre par activité et les
        vignettes l'affichent."""
        MARAICHER = "MARAICHER", "Maraîcher·ère"
        ARBORICULTEUR = "ARBORICULTEUR", "Arboriculteur·rice"
        ELEVEUR = "ELEVEUR", "Éleveur·euse"
        FROMAGER = "FROMAGER", "Fromager·ère"
        APICULTEUR = "APICULTEUR", "Apiculteur·rice"
        MICRO_BRASSEUR = "MICRO_BRASSEUR", "Micro-brasseur·euse"
        CONSERVERIE = "CONSERVERIE", "Conserverie"
        FOODTRUCK = "FOODTRUCK", "Foodtruck"
        TRAITEUR = "TRAITEUR", "Traiteur·e"
        AUTRE = "AUTRE", "Autre production locale"

    class Specialite(models.TextChoices):
        """Type précis au sein d'une activité. Réservé pour l'instant
        aux foodtrucks ; servira plus tard à préciser d'autres
        catégories de producteurs."""
        SANDWICHS = "SANDWICHS", "Sandwichs & Plats"
        PIZZA = "PIZZA", "Pizza"
        BURGER = "BURGER", "Burger"
        TRAITEUR = "TRAITEUR", "Traiteur"
        ROTISSEUR = "ROTISSEUR", "Rôtisseur"

    SPECIALITE_EMOJIS = {"SANDWICHS": "🥪", "PIZZA": "🍕", "BURGER": "🍔",
                         "TRAITEUR": "🍽️", "ROTISSEUR": "🍗"}

    class ModeFonctionnement(models.TextChoices):
        RECOLTE = "RECOLTE", "Récoltes hebdomadaires (paniers)"
        BOUTIQUE = "BOUTIQUE", "Boutique / stock à date"

    # Visuel de chaque activité (vignettes, badges, popups de carte)
    ACTIVITE_EMOJIS = {"MARAICHER": "🥬", "ARBORICULTEUR": "🍎",
                       "ELEVEUR": "🐄", "FROMAGER": "🧀",
                       "APICULTEUR": "🍯", "MICRO_BRASSEUR": "🍺",
                       "CONSERVERIE": "🥫", "FOODTRUCK": "🚚",
                       "TRAITEUR": "🥗", "AUTRE": "🌾"}

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name="exploitant")
    nom_ferme = models.CharField("Nom de l'exploitation", max_length=150)
    slug = models.SlugField("Adresse publique", max_length=160,
                            unique=True, blank=True)
    siret = models.CharField("SIRET", max_length=14, blank=True)
    mode_production = models.CharField(
        "Mode de production", max_length=10,
        choices=ModeProduction.choices, default=ModeProduction.CONV)
    activite = models.CharField(
        "Activité", max_length=15, choices=Activite.choices,
        default=Activite.MARAICHER,
        help_text="Les pros déjà enregistrés sont typés maraîcher ; "
                  "d'autres activités (élevage, fromagerie, arboriculture…)"
                  "arriveront avec leurs listes de produits dédiées.")
    specialite = models.CharField(
        "Spécialité", max_length=12, choices=Specialite.choices,
        blank=True, default="",
        help_text="Affine l'activité — réservé pour l'instant aux "
                  "foodtrucks (sandwichs & plats, pizza, burger, "
                  "traiteur, rôtisseur).")
    logo = models.ImageField("Logo miniature", upload_to=logo_chemin,
                             blank=True, null=True)
    description = models.TextField("Présentation de l'exploitation", blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    ville = models.CharField("Ville", max_length=100, blank=True)
    code_postal = models.CharField("Code postal", max_length=10, blank=True)
    departement = models.CharField("Département", max_length=3,
                                   db_index=True, blank=True)
    telephone = models.CharField("Téléphone", max_length=20, blank=True)
    latitude = models.FloatField("Latitude", blank=True, null=True,
                                 help_text="Position sur la carte (optionnel)")
    longitude = models.FloatField("Longitude", blank=True, null=True,
                                   help_text="Position sur la carte (optionnel)")
    visible = models.BooleanField("Visible publiquement", default=True)
    # Exploitation fictive créée par la commande peupler_demo : les
    # vignettes, la fiche et la carte l'affichent clairement comme DÉMO.
    est_demo = models.BooleanField("Exploitation de démonstration",
                                    default=False)
    # Mode de fonctionnement : les maraîchers et arboriculteurs publient
    # des récoltes hebdomadaires livrées en paniers ; les fromagers,
    # éleveurs et micro-brasseurs tiennent plutôt une boutique avec un
    # stock renouvelé à date, des points de vente et des horaires
    # d'ouverture. Les libellés du portail s'adaptent.
    mode_fonctionnement = models.CharField(
        "Mode de fonctionnement", max_length=10,
        choices=ModeFonctionnement.choices,
        blank=True,
        help_text=("Récoltes : la semaine se publie et se commande en "
                   "paniers. Boutique : un stock de produits à date est "
                   "vendu en direct aux points de vente."))
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Exploitant"
        verbose_name_plural = "Exploitants"
        ordering = ["nom_ferme"]

    def __str__(self):
        return self.nom_ferme

    @property
    def emoji_activite(self):
        return self.ACTIVITE_EMOJIS.get(self.activite, "🌾")

    @property
    def emoji_specialite(self):
        return self.SPECIALITE_EMOJIS.get(self.specialite, "")

    @property
    def emoji_vitrine(self):
        """Symbole complet affiché sur la carte, la légende et les
        vignettes : camion + spécialité pour les foodtrucks, symbole
        d'activité seul sinon."""
        if (self.activite == self.Activite.FOODTRUCK
                and self.emoji_specialite):
            return self.emoji_activite + self.emoji_specialite
        return self.emoji_activite

    @property
    def en_mode_boutique(self):
        return (self.mode_fonctionnement
                == self.ModeFonctionnement.BOUTIQUE)

    @property
    def vocab(self):
        """Libellés adaptés au mode de fonctionnement et à l'activité :
        « récoltes », « points de livraison » et « créneaux » pour le
        mode paniers hebdo des maraîchers et arboriculteurs ; « stock à
        date », « points de vente » et « horaires d'ouverture » pour les
        fromagers et éleveurs ; « productions » pour apiculteurs,
        micro-brasseurs et conserveries."""
        points_vente = {
            "point": "point de vente", "points": "Points de vente",
            "point_livraison": "Point de vente / retrait",
            "creneau": "horaire d'ouverture",
            "creneaux": "horaires d'ouverture",
        }
        if self.en_mode_boutique:
            if self.activite in (self.Activite.APICULTEUR,
                                 self.Activite.MICRO_BRASSEUR,
                                 self.Activite.CONSERVERIE,
                                 self.Activite.FOODTRUCK,
                                 self.Activite.TRAITEUR):
                return {
                    "recolte": "production", "recoltes": "productions",
                    "recoltes_titre": "Mes productions",
                    "nouvelle_recolte": "➕ Nouvelle production",
                    "recolte_hebdo": "production de la semaine",
                    **points_vente,
                }
            return {
                "recolte": "stock", "recoltes": "stocks à date",
                "recoltes_titre": "Mon stock à date",
                "nouvelle_recolte": "➕ Nouveau stock",
                "recolte_hebdo": "stock de la semaine",
                **points_vente,
            }
        return {
            "recolte": "récolte", "recoltes": "récoltes",
            "recoltes_titre": "Mes récoltes",
            "nouvelle_recolte": "➕ Nouvelle récolte",
            "recolte_hebdo": "récolte de la semaine",
            "point": "point de livraison", "points": "Points de livraison",
            "point_livraison": "Point de livraison / retrait",
            "creneau": "créneau de livraison",
            "creneaux": "créneaux de livraison",
        }

    # Libellé du bouton « Commander » des pages publiques (fiche
    # producteur et page de commande) : le verbe et l'emoji suivent le
    # métier — on ne « commande une récolte » que chez un producteur
    # de récoltes, on ne « commande chez un producteur » un camion.
    def libelle_commander(self):
        """Intitulé du bouton d'action public, adapté au métier."""
        activite = self.activite
        if activite in (self.Activite.MARAICHER,
                        self.Activite.ARBORICULTEUR):
            return "🧺 Commande direct récolte"
        if activite == self.Activite.FOODTRUCK:
            return "🚚 Commander au truck"
        return "🧺 Commander nos produits"

    # Libellé de la fiche pro adapté au métier : un foodtruck ou un
    # traiteur n'exploitent pas une « ferme » — la rubrique Paramètres,
    # le menu et le bouton d'enregistrement utilisent ce libellé.
    LIBELLES_FICHE = {
        "FOODTRUCK": ("🚚", "Mon foodtruck"),
        "TRAITEUR": ("🥗", "Ma boutique"),
    }

    @property
    def libelle_fiche(self):
        """« Ma ferme », « Mon foodtruck » ou « Ma boutique » selon
        l'activité du pro."""
        return self.LIBELLES_FICHE.get(self.activite, ("", "Ma ferme"))[1]

    @property
    def titre_fiche(self):
        """Libellé précédé de son emoji, prêt pour un titre de page ou
        une entrée de menu."""
        emoji, libelle = self.LIBELLES_FICHE.get(
            self.activite, ("🚜", "Ma ferme"))
        return f"{emoji} {libelle}"

    # Libellé « équipe » selon l'activité, page publique producteur :
    # « L'équipe d'éleveurs », « L'équipe de brasseurs »…
    EQUIPE_LIBELLES = {
        "MARAICHER": "L'équipe de maraîchers",
        "ARBORICULTEUR": "L'équipe d'arboriculteurs",
        "ELEVEUR": "L'équipe d'éleveurs",
        "FROMAGER": "L'équipe de fromagers",
        "APICULTEUR": "L'équipe d'apiculteurs",
        "MICRO_BRASSEUR": "L'équipe de brasseurs",
        "CONSERVERIE": "L'équipe de la conserverie",
        "FOODTRUCK": "L'équipe du foodtruck",
        "TRAITEUR": "L'équipe de traiteurs",
        "AUTRE": "L'équipe de la ferme",
    }

    @property
    def libelle_equipe(self):
        return self.EQUIPE_LIBELLES.get(self.activite,
                                        "L'équipe de la ferme")

    # Rythme de publication par défaut selon l'activité (utilisé
    # tant que l'exploitant n'a rien choisi dans Paramètres → Ma
    # ferme). Purement indicatif : le libellé de l'encart vitrine
    # s'adapte, le nombre de publications reste libre.
    RYTHMES_DEFAUT = {
        "MARAICHER": "SEMAINE", "ARBORICULTEUR": "MOIS",
        "FOODTRUCK": "SEMAINE", "TRAITEUR": "MOIS",
        "APICULTEUR": "MOIS", "MICRO_BRASSEUR": "MOIS",
        "CONSERVERIE": "MOIS", "FROMAGER": "MOIS",
        "ELEVEUR": "MOIS", "AUTRE": "SEMAINE",
    }
    RYTHME_LIBELLES = {"JOUR": "du jour", "SEMAINE": "de la semaine",
                        "MOIS": "du mois", "SAISON": "de la saison"}

    @property
    def rythme_publication(self):
        try:
            choix = (self.parametres_vitrine.rythme_publication or "")
        except Exception:
            choix = ""
        return choix or self.RYTHMES_DEFAUT.get(self.activite, "SEMAINE")

    @property
    def libelle_rythme(self):
        return self.RYTHME_LIBELLES.get(self.rythme_publication,
                                        "de la semaine")

    @property
    def titre_semaine(self):
        """Titre de l'encart vitrine, accordé à l'activité, à l'équipe
        (Mes/Notre) et au rythme choisi : « Récolte de la semaine »,
        « Ma carte de la semaine », « Nos plats du mois », « Mes
        produits de la semaine », « Mes productions du mois »…"""
        nous = self.membres.exists()
        rythme = self.libelle_rythme
        if self.activite in (self.Activite.MARAICHER,
                             self.Activite.ARBORICULTEUR):
            return f"Nos récoltes {rythme}" if nous \
                else f"Récolte {rythme}"
        if self.activite == self.Activite.FOODTRUCK:
            return f"Notre carte {rythme}" if nous \
                else f"Ma carte {rythme}"
        if self.activite == self.Activite.TRAITEUR:
            return f"Nos plats {rythme}" if nous \
                else f"Mes plats {rythme}"
        if self.activite in (self.Activite.APICULTEUR,
                             self.Activite.MICRO_BRASSEUR,
                             self.Activite.CONSERVERIE):
            return f"Nos productions {rythme}" if nous \
                else f"Mes productions {rythme}"
        return f"Nos produits {rythme}" if nous \
            else f"Mes produits {rythme}"

    @property
    def titres_avoir(self):
        """Titre de l'encart « à venir » de la vitrine publique,
         accordé à l'activité."""
        if self.activite in (self.Activite.MARAICHER,
                             self.Activite.ARBORICULTEUR):
            return "Récoltes à venir"
        if self.activite == self.Activite.FOODTRUCK:
            return "Arrêts & marchés à venir"
        if self.activite == self.Activite.TRAITEUR:
            return "Plats à venir"
        if self.activite in (self.Activite.APICULTEUR,
                             self.Activite.MICRO_BRASSEUR,
                             self.Activite.CONSERVERIE):
            return "Productions à venir"
        return "Produits à venir"

    # Activités disposant d'une CARTE / BOUTIQUE stable en vitrine (en
    # plus de l'encart de la semaine) : menus et plats pour traiteurs
    # et foodtrucks, boutique à date pour fromagers, apiculteurs,
    # conserveries et micro-brasseurs.
    @property
    def a_carte_boutique(self):
        return self.activite in (self.Activite.FOODTRUCK,
                                 self.Activite.TRAITEUR,
                                 self.Activite.FROMAGER,
                                 self.Activite.APICULTEUR,
                                 self.Activite.MICRO_BRASSEUR,
                                 self.Activite.CONSERVERIE)

    @property
    def titre_carte_boutique(self):
        """« Ma carte » (foodtruck), « Mes menus » (traiteur), « Ma
        boutique » (fromager, apiculteur, conserverie, brasseur) —
        « Notre » dès que l'équipe s'étoffe."""
        nous = self.membres.exists()
        if self.activite == self.Activite.FOODTRUCK:
            return "Notre carte" if nous else "Ma carte"
        if self.activite == self.Activite.TRAITEUR:
            return "Nos menus" if nous else "Mes menus"
        return "Notre boutique" if nous else "Ma boutique"

    @property
    def titre_points_vitrine(self):
        """Titre de la rubrique des points de la vitrine : les
        foodtrucks exposent des EMPLACEMENTS (qui peuvent être sur des
        marchés), les autres des points de retrait."""
        if self.activite == self.Activite.FOODTRUCK:
            return "Emplacements & marchés"
        if self.en_mode_boutique:
            return "Boutiques, marchés & points de vente"
        return "Boutiques, marchés & points de livraison"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.nom_ferme) or "exploitant"
            slug = base
            n = 2
            while Exploitant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        # Département déduit du code postal (2 premiers chiffres) s'il
        # n'est pas saisi : la recherche « 81 » / « Tarn » s'appuie dessus.
        if not self.departement and self.code_postal:
            self.departement = self.code_postal[:2]
        # Mode de fonctionnement par défaut selon l'activité : récoltes
        # hebdomadaires pour maraîchers et arboriculteurs, boutique /
        # stock à date pour les autres (fromager, éleveur, ruche,
        # micro-brasserie…). L'exploitant peut changer dans Paramètres.
        if not self.mode_fonctionnement:
            self.mode_fonctionnement = (
                self.ModeFonctionnement.BOUTIQUE
                if self.activite not in (self.Activite.MARAICHER,
                                         self.Activite.ARBORICULTEUR)
                else self.ModeFonctionnement.RECOLTE)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("portal:producer_detail", kwargs={"slug": self.slug})

    @property
    def siret_valide(self):
        """SIRET syntaxiquement valide : 14 chiffres, clé de Luhn correcte.
        (Validation de forme, sans appel au registre national en V1.)"""
        chiffres = "".join(c for c in (self.siret or "") if c.isdigit())
        if len(chiffres) != 14:
            return False
        total = 0
        for i, c in enumerate(chiffres):
            d = int(c)
            if i % 2 == 0:  # 14 chiffres : indices pairs doublés depuis la gauche
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0


class ProfilClient(models.Model):
    """Profil client (optionnel, pour faciliter les commandes récurrentes)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name="profil_client")
    telephone = models.CharField("Téléphone", max_length=20, blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    ville = models.CharField("Ville", max_length=100, blank=True)
    code_postal = models.CharField("Code postal", max_length=10, blank=True)
    photo_url = models.URLField(
        "Photo externe", blank=True,
        help_text="Lien vers une photo hébergée ailleurs (drive, cloud, "
                  "réseau) : rien n'est hébergé par le portail.")

    def __str__(self):
        return f"Client : {self.user.get_full_name() or self.user.username}"


class Categorie(models.Model):
    """Catégorie définie par chaque exploitant (issue #5)."""

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="categories")
    nom = models.CharField("Nom", max_length=80)
    slug = models.SlugField(max_length=100, blank=True)
    position = models.PositiveSmallIntegerField("Position", default=0)

    class Meta:
        verbose_name = "Catégorie"
        unique_together = ("exploitant", "nom")
        ordering = ["position", "nom"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


class ProduitStandard(models.Model):
    """Produit du catalogue standard embarqué (~80–120 produits types,
    issue #1). Lecture seule pour les exploitants : point de départ
    copiable. Illustrations emojis/SVG embarquées : zéro dépendance."""

    class Unite(models.TextChoices):
        KG = "KG", "le kg"
        PIECE = "PC", "la pièce"
        BOTTE = "BO", "la botte"
        BARQUETTE = "BQ", "la barquette"

    nom = models.CharField("Nom", max_length=150)
    categorie = models.CharField("Catégorie standard", max_length=80)
    # Catalogue rattaché à une activité : le catalogue « maraîcher »
    # historique reste la base des producteurs maraîchers ; chaque
    # activité (arboriculture, élevage, fromagerie, ruche…) dispose de
    # sa propre liste, tous catalogues restant accessibles.
    activite = models.CharField(
        "Activité", max_length=15,
        choices=Exploitant.Activite.choices,
        default=Exploitant.Activite.MARAICHER)
    unite_vente = models.CharField("Unité de vente", max_length=2,
                                   choices=Unite.choices, default=Unite.KG)
    saisons = models.JSONField("Saisons", default=list, blank=True,
                               help_text='Ex : ["printemps", "été"]')
    emoji = models.CharField("Emoji", max_length=8, blank=True)
    svg = models.TextField("SVG inline", blank=True)

    class Meta:
        verbose_name = "Produit standard"
        verbose_name_plural = "Produits standard (catalogue embarqué)"
        ordering = ["categorie", "nom"]

    def __str__(self):
        return f"{self.emoji} {self.nom}".strip()


class Produit(models.Model):
    """Produit du catalogue d'un exploitant.

    Attributs libres en JSONB (issue #5), traçabilité de la copie depuis le
    catalogue standard (issue #1), produits perso autorisés.
    """

    class Unite(models.TextChoices):
        KG = "KG", "le kg"
        PIECE = "PC", "la pièce"
        BOTTE = "BO", "la botte"
        BARQUETTE = "BQ", "la barquette"

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="produits")
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL,
                                  null=True, blank=True,
                                  related_name="produits")
    nom = models.CharField("Nom", max_length=150)
    slug = models.SlugField(max_length=160, blank=True)
    description = models.TextField("Description", blank=True)
    illustration = models.ImageField("Photo",
                                      upload_to=illustration_produit_chemin,
                                      blank=True, null=True)
    unite_vente = models.CharField("Unité de vente", max_length=2,
                                   choices=Unite.choices, default=Unite.KG)
    attributs = models.JSONField("Attributs libres", default=dict, blank=True,
                                 help_text='Ex : {"variété": "Butternut", "label": "AB"}')
    origine_standard = models.ForeignKey(ProduitStandard,
                                          on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name="copies")
    perso = models.BooleanField("Créé pour mon usage propre", default=False)
    prix = models.DecimalField("Prix de référence (€)", max_digits=6,
                               decimal_places=2, null=True, blank=True)
    actif = models.BooleanField("Actif", default=True)
    # Ordre d'affichage au sein de la catégorie (mode édition du
    # dashboard : boutons ▲▼ pour reclasser les produits).
    position = models.PositiveSmallIntegerField("Position", default=0)
    emoji = models.CharField(
        "Emoji", max_length=8, blank=True,
        help_text="Symbole affiché dans toutes les listes : hérité du "
                  "produit type d'origine, ou deviné par mot-clé "
                  "(commande charger_catalogues_activites).")

    class Meta:
        verbose_name = "Produit"
        unique_together = ("exploitant", "slug")
        ordering = ["categorie__position", "categorie__nom",
                    "position", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.exploitant.nom_ferme})"

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.slug or self.slug == slugify(self.nom or ""):
            # Slug dérivé du nom, dédoublonné au sein de l'exploitation
            # (comme Exploitant) : deux produits homonymes ne doivent
            # pas casser la contrainte (exploitant, slug).
            base = slugify(self.nom) or "produit"
            slug = base
            n = 2
            while Produit.objects.filter(
                    exploitant_id=self.exploitant_id,
                    slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # Libellé d'unité pour l'affichage public : « kg », « pièce(s) »…
    UNITES_COURTES = {"KG": "kg", "PC": "pièce(s)", "BO": "botte(s)",
                      "BQ": "barquette(s)"}
    # Singulier / pluriel accordés à la quantité (kg invariable).
    UNITES_ACCORD = {"KG": ("kg", "kg"), "PC": ("pièce", "pièces"),
                     "BO": ("botte", "bottes"),
                     "BQ": ("barquette", "barquettes")}

    @property
    def unite_courte(self):
        return self.UNITES_COURTES.get(self.unite_vente, self.unite_vente)

    def unite_pour(self, quantite):
        """Libellé d'unité accordé à la quantité : 1 pièce, 2 pièces ;
        0,5 kg, 3 kg (le kilogramme est invariable)."""
        try:
            q = float(quantite or 0)
        except (TypeError, ValueError):
            q = 0
        singulier, pluriel = self.UNITES_ACCORD.get(
            self.unite_vente, (self.unite_vente, self.unite_vente))
        return pluriel if q > 1 else singulier

    @property
    def image_externe(self):
        """Lien vers une photo hébergée ailleurs (drive, cloud, réseau) :
        stocké dans attributs["image_url"] — zéro stockage local."""
        return (self.attributs or {}).get("image_url", "")


class SemaineRecolte(models.Model):
    """Récolte d'une semaine donnée pour un exploitant.

    L'exploitant paramètre chaque semaine ce qui est visible côté vitrine.
    """

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="semaines")
    lundi = models.DateField("Lundi de la semaine", db_index=True)
    note = models.CharField("Note / actualité de la semaine", max_length=255,
                            blank=True)
    publiee = models.BooleanField("Publiée aux clients", default=True)

    class Meta:
        verbose_name = "Semaine de récolte"
        verbose_name_plural = "Semaines de récolte"
        unique_together = ("exploitant", "lundi")
        ordering = ["-lundi"]

    def __str__(self):
        return f"Récolte du {self.lundi} — {self.exploitant.nom_ferme}"


class LigneRecolte(models.Model):
    """Ligne de récolte : ESTIMATION indicative de quantité + prix.

    ⚠️ Les quantités saisies sont des ESTIMATIONS, pas un stock :
    elles informent le client mais ne bloquent ni ne décomptent aucune
    commande. Seules les quantités livrées dans les paniers comptent.
    """

    recolte = models.ForeignKey(SemaineRecolte, on_delete=models.CASCADE,
                                related_name="lignes")
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE,
                                related_name="lignes_recolte")
    quantite_estimee = models.DecimalField("Quantité estimée",
                                           max_digits=8, decimal_places=2)
    prix_unitaire = models.DecimalField("Prix unitaire (€)",
                                        max_digits=6, decimal_places=2)

    class Meta:
        verbose_name = "Ligne de récolte (estimation)"
        unique_together = ("recolte", "produit")

    def __str__(self):
        return f"{self.produit.nom} ~{self.quantite_estimee} @ {self.prix_unitaire}€"


class PointLivraison(models.Model):
    """Point de mise en relation avec la clientèle : livraison de
    paniers, boutique / point de vente, ou stand sur un marché. Les
    créneaux récurrents (jours, horaires, fréquence) se rattachent à
    n'importe lequel de ces types."""

    class Type(models.TextChoices):
        LIVRAISON = "LIVRAISON", "Point de livraison / retrait"
        BOUTIQUE = "BOUTIQUE", "Boutique / point de vente"
        MARCHE = "MARCHE", "Marché"
        EMPLACEMENT = "EMPLACEMENT", "Emplacement / arrêt foodtruck"

    TYPE_EMOJIS = {"LIVRAISON": "📍", "BOUTIQUE": "🏪", "MARCHE": "🎪",
                   "EMPLACEMENT": "🚚"}

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="points_livraison")
    nom = models.CharField("Nom", max_length=150)
    adresse = models.CharField("Adresse", max_length=255)
    ville = models.CharField("Ville", max_length=100)
    code_postal = models.CharField("Code postal", max_length=10)
    note = models.TextField("Précisions", blank=True)
    # Position cartographique (Plan IGN) : géocodée depuis l'adresse ou
    # posée par clic sur la carte par le maraîcher ; transmise au client
    # dès que son panier passe en prêt/livré (lien vers la carte).
    latitude = models.FloatField("Latitude", null=True, blank=True)
    longitude = models.FloatField("Longitude", null=True, blank=True)
    # Type de mise en relation : livraison de paniers (maraîchers et
    # arboriculteurs), boutique / point de vente, ou marché — tout
    # producteur peut aussi déclarer des créneaux récurrents sur un
    # marché (stand hebdomadaire, bisomadaire, mensuel).
    type_point = models.CharField(
        "Type de mise en relation", max_length=12,
        choices=Type.choices, default=Type.LIVRAISON,
        help_text="Livraison de paniers, vente en boutique ou stand de "
                  "marché : les créneaux récurrents se rattachent à "
                  "n'importe lequel de ces points.")

    class Meta:
        verbose_name = "Point de livraison"
        ordering = ["ville", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.ville})"

    @property
    def emoji_type(self):
        return self.TYPE_EMOJIS.get(self.type_point, "📍")


class CreneauLivraison(models.Model):
    """Créneau récurrent : jour, horaires, fréquence, capacité."""

    class Frequence(models.TextChoices):
        HEBDO = "H", "Chaque semaine"
        BIS = "B", "Une semaine sur deux"
        MENSUEL = "M", "Une fois par mois"

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="creneaux")
    point_livraison = models.ForeignKey(PointLivraison,
                                        on_delete=models.CASCADE,
                                        related_name="creneaux",
                                        blank=True, null=True)
    jour = models.PositiveSmallIntegerField(
        "Jour",
        choices=[(1, "Lundi"), (2, "Mardi"), (3, "Mercredi"), (4, "Jeudi"),
                 (5, "Vendredi"), (6, "Samedi"), (7, "Dimanche")],
    )
    heure_debut = models.TimeField("Début")
    heure_fin = models.TimeField("Fin")
    frequence = models.CharField("Fréquence", max_length=1,
                                choices=Frequence.choices,
                                default=Frequence.HEBDO)
    capacite = models.PositiveSmallIntegerField(
        "Capacité (paniers/commandes)", default=10)

    class Meta:
        verbose_name = "Créneau de livraison"
        ordering = ["jour", "heure_debut"]

    def __str__(self):
        return (f"{self.get_jour_display()} {self.heure_debut}–{self.heure_fin} "
                f"({self.get_frequence_display()})")


class Carte(models.Model):
    """Carte / boutique stable d'un traiteur, foodtruck ou
    producteur en mode boutique (fromager, apiculteur, conserverie,
    micro-brasseur) : vitrine permanente EN PLUS de l'encart de la
    semaine — le côté « boutique stable » qui convient à la majorité,
    quand l'encart saisonnier reste dans l'esprit récoltes du site.

    Plusieurs cartes coexistent (brouillons, versions archivées et
    republiables) mais UNE SEULE est active à la fois."""

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        ACTIVE = "ACTIVE", "Publiée (active)"
        ARCHIVEE = "ARCHIVEE", "Archivée"

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="cartes")
    nom = models.CharField(
        "Nom de la carte", max_length=120,
        help_text="Ex : « Carte du moment », « Menu de fête », "
                  "« En boutique en ce moment ».")
    statut = models.CharField("Statut", max_length=10,
                              choices=Statut.choices,
                              default=Statut.BROUILLON, db_index=True)
    creee_le = models.DateTimeField("Créée le", auto_now_add=True)
    maj_le = models.DateTimeField("Mise à jour", auto_now=True)

    class Meta:
        verbose_name = "Carte / boutique"
        verbose_name_plural = "Cartes / boutiques"
        ordering = ["-maj_le"]

    def __str__(self):
        return f"{self.nom} — {self.exploitant.nom_ferme} ({self.statut})"

    def activer(self):
        """Publie cette carte : la carte active précédente passe en
        archive (une seule active à la fois)."""
        with transaction.atomic():
            (Carte.objects.filter(exploitant=self.exploitant,
                                  statut=Carte.Statut.ACTIVE)
             .exclude(pk=self.pk)
             .update(statut=Carte.Statut.ARCHIVEE))
            self.statut = Carte.Statut.ACTIVE
            self.save(update_fields=["statut", "maj_le"])


class LigneCarte(models.Model):
    """Ligne d'une carte/boutique : reprend un PRODUIT du catalogue
    de l'exploitant (copié du catalogue de référence ou perso) ou une
    ligne entièrement libre (plat du jour, menu…), avec son prix."""

    carte = models.ForeignKey(Carte, on_delete=models.CASCADE,
                              related_name="lignes")
    produit = models.ForeignKey(Produit, on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name="lignes_cartes")
    nom_libre = models.CharField(
        "Nom (ligne libre)", max_length=150, blank=True, default="",
        help_text="Si la ligne ne reprend pas un produit du catalogue.")
    section = models.CharField(
        "Section", max_length=80, blank=True, default="",
        help_text="Ex : « Entrées », « Plats », « Fromages au lait cru »…")
    description = models.TextField("Description", blank=True)
    unite_vente = models.CharField("Unité de vente", max_length=2,
                                   choices=Produit.Unite.choices,
                                   default=Produit.Unite.KG)
    prix = models.DecimalField("Prix (€)", max_digits=6, decimal_places=2,
                               null=True, blank=True,
                               help_text="Vide : prix du produit lié.")
    # Stock publié sur la ligne (boutiques, cartes, menus) : vide =
    # vendu sans suivi de stock. Le restant affiché aux clients
    # décompte les quantités des commandes VALIDÉES uniquement
    # (après ajustement éventuel par l'exploitant).
    stock = models.DecimalField(
        "Stock publié", max_digits=8, decimal_places=2, null=True,
        blank=True,
        help_text="Quantité mise en vente : vide = illimité.")
    position = models.PositiveSmallIntegerField("Position", default=0)

    class Meta:
        verbose_name = "Ligne de carte"
        verbose_name_plural = "Lignes de carte"
        ordering = ["section", "position", "id"]

    def __str__(self):
        return f"{self.nom} ({self.carte.nom})"

    @property
    def nom(self):
        return self.produit.nom if self.produit else (self.nom_libre or "—")

    @property
    def prix_affiche(self):
        if self.prix is not None:
            return self.prix
        return self.produit.prix if self.produit else None

    @property
    def emoji(self):
        if not self.produit:
            return ""
        if self.produit.emoji:
            return self.produit.emoji
        return (self.produit.origine_standard.emoji
                if self.produit.origine_standard else "")

    @property
    def unite_courte(self):
        return Produit.UNITES_COURTES.get(self.unite_vente,
                                          self.unite_vente)


class Commande(models.Model):
    """Commande client (portail ou saisie par l'exploitant), à valider.

    Porte TOUJOURS l'identité contact du client, loggué ou non :
    nom + e-mail OU téléphone (clé de regroupement « commandes par client »).
    Seules les commandes validées puis livrées persistent (purge sinon).
    """

    class Statut(models.TextChoices):
        NOUVELLE = "NOUVELLE", "À valider"
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"
        ANNULEE = "ANNULEE", "Annulée"

    class AnnulationPar(models.TextChoices):
        """Qui a annulé la commande : le client depuis « Mes
        commandes », ou le producteur (panier annulé en
        préparation, motif transmis au client). Les deux cas
        partagent le statut ANNULEE mais se discernent partout,
        données comme interfaces."""
        CLIENT = "CLIENT", "Client"
        PRODUCTEUR = "PRODUCTEUR", "Producteur"

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="commandes")
    client = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                               blank=True, related_name="commandes",
                               help_text="Null si client sans compte")
    nom_client = models.CharField("Nom du client", max_length=150)
    email_client = models.EmailField("E-mail du client", blank=True)
    telephone_client = models.CharField("Téléphone du client", max_length=20,
                                        blank=True,
                                        help_text="E-mail OU téléphone requis")
    point_livraison = models.ForeignKey(PointLivraison,
                                       on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name="commandes")
    date_livraison = models.DateField("Date de livraison souhaitée")
    statut = models.CharField("Statut", max_length=10,
                              choices=Statut.choices,
                              default=Statut.NOUVELLE, db_index=True)
    annulee_par = models.CharField(
        "Annulée par", max_length=12, choices=AnnulationPar.choices,
        blank=True, default="",
        help_text="Discerne l'annulation client de l'annulation "
                  "producteur (panier annulé en préparation).")
    total = models.DecimalField("Total (€)", max_digits=8, decimal_places=2,
                                default=0)
    note = models.TextField("Message du client", blank=True)
    motif_refus = models.TextField(
        "Motif du refus", blank=True, default="",
        help_text="Raison visible par le client quand le producteur "
                  "refuse la commande.")
    saisie_exploitant = models.BooleanField("Saisie directe de l'exploitant",
                                           default=False)
    creee_le = models.DateTimeField(auto_now_add=True)
    validee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        ordering = ["-creee_le"]

    def __str__(self):
        return (f"Commande #{self.pk} — {self.nom_client} "
                f"→ {self.exploitant.nom_ferme}")

    @property
    def libelle_statut(self):
        """Statut affiché : les annulations distinguent le client du
        producteur (panier annulé) — côté pro comme côté client."""
        if self.statut == self.Statut.ANNULEE:
            if self.annulee_par == self.AnnulationPar.PRODUCTEUR:
                return "Annulée (producteur)"
            return "Annulée (client)"
        return self.get_statut_display()

    @property
    def contact_client(self):
        """Contact utilisé pour les envois e-mail/SMS (figé à l'instant t)."""
        return self.email_client or self.telephone_client


class LigneCommande(models.Model):
    """Ligne de commande : panier SOUHAITÉ, prix et quantité figés."""

    commande = models.ForeignKey(Commande, on_delete=models.CASCADE,
                                related_name="lignes")
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT,
                                related_name="lignes_commande")
    quantite = models.DecimalField("Quantité", max_digits=8, decimal_places=2)
    prix_unitaire = models.DecimalField("Prix unitaire (€)",
                                        max_digits=6, decimal_places=2)

    class Meta:
        verbose_name = "Ligne de commande"

    def total_ligne(self):
        return self.quantite * self.prix_unitaire


class Panier(models.Model):
    """Panier numéroté (n°1..X par JOUR et par POINT DE LIVRAISON) :
    le dernier panier porte le nombre total de paniers du point ce jour-là.
    Le contenu LIVRÉ (LignePanier) est la seule source du décompte de
    production et de l'export comptable."""

    class Statut(models.TextChoices):
        PREPARATION = "PREPARATION", "En préparation"
        PRET = "PRET", "Prêt"
        LIVRE = "LIVRE", "Livré"
        RECU = "RECU", "Reçu / retiré"
        ANNULE = "ANNULE", "Annulé"

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="paniers")
    client = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                               blank=True, related_name="paniers")
    nom_client = models.CharField("Nom du client", max_length=150)
    email_client = models.EmailField("E-mail du client", blank=True)
    telephone_client = models.CharField("Téléphone du client", max_length=20,
                                       blank=True)
    numero = models.PositiveSmallIntegerField("N° de panier")
    date_livraison = models.DateField("Jour de livraison", db_index=True)
    creneau = models.ForeignKey(CreneauLivraison, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="paniers")
    point_livraison = models.ForeignKey(PointLivraison,
                                        on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        related_name="paniers")
    commande = models.ForeignKey(Commande, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="paniers")
    statut = models.CharField("Statut", max_length=12,
                              choices=Statut.choices,
                              default=Statut.PREPARATION, db_index=True)
    total = models.DecimalField("Total (€)", max_digits=8, decimal_places=2,
                                default=0)
    note = models.TextField("Commentaire du producteur", blank=True,
                            help_text="Visible par le client (ajustements, "
                                      "remplacements éventuels)")
    motif_annulation = models.TextField(
        "Motif d'annulation", blank=True, default="",
        help_text="Raison visible par le client quand un panier en "
                  "préparation est annulé ; la commande repasse alors "
                  "« Annulée » et peut être recommandée.")
    # Instantané FIGÉ des infos du point de retrait à la création du
    # panier : si le producteur modifie ensuite le point (nom, adresse,
    # position), l'historique des paniers déjà livrés garde les infos
    # qui avaient été transmises aux clients.
    point_nom = models.CharField("Nom du point (figé)", max_length=150,
                                 blank=True, default="")
    point_adresse = models.CharField("Adresse du point (figée)",
                                     max_length=255, blank=True, default="")
    point_code_postal = models.CharField("CP du point (figé)", max_length=10,
                                         blank=True, default="")
    point_ville = models.CharField("Ville du point (figée)", max_length=100,
                                   blank=True, default="")
    point_latitude = models.FloatField("Latitude du point (figée)",
                                       null=True, blank=True)
    point_longitude = models.FloatField("Longitude du point (figée)",
                                        null=True, blank=True)

    def save(self, *args, **kwargs):
        # Figure l'identité du point à la première sauvegarde du panier
        # (une seule fois : les paniers suivants voient les modifs).
        if self.point_livraison_id and not self.point_nom:
            p = self.point_livraison
            self.point_nom = p.nom
            self.point_adresse = p.adresse
            self.point_code_postal = p.code_postal
            self.point_ville = p.ville
            self.point_latitude = p.latitude
            self.point_longitude = p.longitude
        super().save(*args, **kwargs)

    @property
    def point_affiche(self):
        """Infos de retrait affichées au client : l'instantané figé à la
        création du panier, en repli sur le point courant (paniers sans
        point ou antérieurs au figage)."""
        p = self.point_livraison
        return {
            "nom": self.point_nom or (p.nom if p else ""),
            "adresse": self.point_adresse or (p.adresse if p else ""),
            "code_postal": self.point_code_postal
                           or (p.code_postal if p else ""),
            "ville": self.point_ville or (p.ville if p else ""),
            "note": p.note if p else "",
            "latitude": (self.point_latitude if self.point_nom
                         else (p.latitude if p else None)),
            "longitude": (self.point_longitude if self.point_nom
                          else (p.longitude if p else None)),
        }

    class Meta:
        verbose_name = "Panier"
        unique_together = ("exploitant", "client", "date_livraison", "numero")
        ordering = ["date_livraison", "numero"]

    @property
    def destination_itineraire(self):
        """(lat, lon) du point de retrait s'il est géolocalisé, sinon
        de la ferme du producteur — base des liens de calcul
        d'itinéraire côté client (OpenStreetMap, Google Maps) quand le
        panier est marqué livré."""
        pt = self.point_livraison
        if (pt is not None and pt.latitude is not None
                and pt.longitude is not None):
            return (pt.latitude, pt.longitude)
        ex = self.exploitant
        if (ex is not None and ex.latitude is not None
                and ex.longitude is not None):
            return (ex.latitude, ex.longitude)
        return None

    def __str__(self):
        return (f"Panier n°{self.numero} — {self.nom_client} "
                f"le {self.date_livraison}")

    @classmethod
    def prochain_numero(cls, exploitant, date_livraison, point_livraison=None,
                         client=None, nom_client=""):
        """n°1..X par jour et par point de livraison : deux clients
        commandant le même jour au même point obtiennent 1 et 2. Les
        paniers sans point dédié forment leur propre séquence."""
        qs = cls.objects.filter(exploitant=exploitant,
                                date_livraison=date_livraison,
                                point_livraison=point_livraison)
        dernier = qs.order_by("-numero").values_list("numero", flat=True).first()
        return (dernier or 0) + 1


class LignePanier(models.Model):
    """Contenu EFFECTIVEMENT livré dans un panier — LA source du décompte
    de production et de l'export comptable CSV (issue #8)."""

    panier = models.ForeignKey(Panier, on_delete=models.CASCADE,
                               related_name="lignes")
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT,
                                related_name="lignes_panier")
    quantite = models.DecimalField("Quantité livrée", max_digits=8,
                                   decimal_places=2)
    prix_unitaire = models.DecimalField("Prix unitaire (€)",
                                        max_digits=6, decimal_places=2)

    class Meta:
        verbose_name = "Ligne de panier (livré)"

    def total_ligne(self):
        return self.quantite * self.prix_unitaire


class ModeleMessage(models.Model):
    """Modèle de message personnalisable (issue #3), placeholders
    {{ client }}, {{ panier }}, {{ ferme }}, {{ creneau }}. Fallback sur le
    défaut si le modèle personnalisé est cassé."""

    class Type(models.TextChoices):
        CONFIRMATION_COMMANDE = "CONFIRMATION_COMMANDE", "Confirmation de commande"
        PANIER_PRET = "PANIER_PRET", "Panier prêt"
        LIVRAISON_FAITE = "LIVRAISON_FAITE", "Livraison faite"
        BULLETIN = "BULLETIN", "Bulletin (newsletter)"
        ANNONCE = "ANNONCE", "Annonce"

    class Canal(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        SMS = "SMS", "SMS"

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="modeles_message")
    type = models.CharField("Type", max_length=25, choices=Type.choices)
    canal = models.CharField("Canal", max_length=5, choices=Canal.choices,
                             default=Canal.EMAIL)
    objet = models.CharField("Objet", max_length=200)
    corps = models.TextField("Corps")
    actif = models.BooleanField("Actif", default=True)

    class Meta:
        verbose_name = "Modèle de message"
        unique_together = ("exploitant", "type", "canal")

    def __str__(self):
        return f"{self.get_type_display()} ({self.get_canal_display()}) — {self.exploitant}"


class Bulletin(models.Model):
    """Bulletin du producteur (récolte de la semaine, actualités)."""

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="bulletins")
    semaine = models.ForeignKey(SemaineRecolte, on_delete=models.SET_NULL,
                                null=True, blank=True)
    objet = models.CharField("Objet", max_length=200)
    corps = models.TextField("Corps")
    envoye_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Bulletin"
        ordering = ["-envoye_le"]

    def __str__(self):
        return f"Bulletin — {self.objet}"


class Annonce(models.Model):
    """Annonce ponctuelle (« paniers disponibles », …)."""

    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="annonces")
    objet = models.CharField("Objet", max_length=200)
    corps = models.TextField("Corps")
    envoye_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Annonce"
        ordering = ["-envoye_le"]

    def __str__(self):
        return f"Annonce — {self.objet}"


class PreferenceContact(models.Model):
    """Préférences de contact par couple client ↔ exploitant (issue #3)."""

    class Canal(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        SMS = "SMS", "SMS"

    client = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name="preferences_contact")
    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="preferences_clients")
    veut_bulletin = models.BooleanField("Recevoir le bulletin", default=True)
    veut_annonces = models.BooleanField("Recevoir les annonces", default=True)
    canal = models.CharField("Canal préféré", max_length=5,
                             choices=Canal.choices, default=Canal.EMAIL)

    class Meta:
        verbose_name = "Préférence de contact"
        unique_together = ("client", "exploitant")

    def __str__(self):
        return f"{self.client} ↔ {self.exploitant}"


class ConfigMessagerie(models.Model):
    """SMTP et passerelle SMS de l'exploitant (jamais centralisés, issue #3).

    ⚠️ V2 : chiffrer smtp_mot_de_passe et config_sms au repos.
    """

    class PasserelleSMS(models.TextChoices):
        FREE = "FREE", "Free Mobile"
        OVH = "OVH", "OVH"
        TWILIO = "TWILIO", "Twilio"
        HTTP_PERSO = "HTTP_PERSO", "HTTP personnalisée"

    exploitant = models.OneToOneField(Exploitant, on_delete=models.CASCADE,
                                      related_name="config_messagerie")
    smtp_hote = models.CharField("Serveur SMTP", max_length=255, blank=True)
    smtp_port = models.PositiveSmallIntegerField("Port SMTP", default=587)
    smtp_utilisateur = models.CharField("Utilisateur SMTP", max_length=150,
                                       blank=True)
    smtp_mot_de_passe = models.CharField("Mot de passe SMTP", max_length=255,
                                         blank=True)
    smtp_expediteur = models.EmailField("Adresse d'expédition", blank=True)
    passerelle_sms = models.CharField("Passerelle SMS", max_length=15,
                                     choices=PasserelleSMS.choices, blank=True)
    config_sms = models.JSONField("Configuration passerelle", default=dict,
                                  blank=True)
    quota_journalier = models.PositiveSmallIntegerField(
        "Quota d'envois / jour", default=100)
    heures_calmes = models.CharField(
        "Heures calmes", max_length=11, blank=True,
        help_text="Ex : 21:00-08:00 — pas d'envoi dans cette plage")

    class Meta:
        verbose_name = "Configuration messagerie"

    def __str__(self):
        return f"Messagerie de {self.exploitant}"


class ParametresVitrine(models.Model):
    """Personnalisation de la vitrine publique (issue #4)."""

    exploitant = models.OneToOneField(Exploitant, on_delete=models.CASCADE,
                                      related_name="parametres_vitrine")
    titre_accroche = models.CharField("Titre d'accroche", max_length=150,
                                      blank=True)
    texte_accroche = models.TextField("Texte d'accroche", blank=True)
    couleur_theme = models.CharField("Couleur d'accent", max_length=7,
                                     default="#2e7d32")
    image_banniere = models.ImageField("Bannière", upload_to=banniere_chemin,
                                       blank=True, null=True)
    afficher_recolte = models.BooleanField("Afficher la récolte", default=True)
    afficher_catalogue = models.BooleanField("Afficher le catalogue", default=True)
    afficher_creneaux = models.BooleanField("Afficher les créneaux", default=True)
    reseaux = models.JSONField("Réseaux sociaux", default=dict, blank=True,
                               help_text='Ex : {"facebook": "https://…"}')
    # Rythme de publication de l'encart vitrine (« …de la semaine »,
    # « …du mois »…) : LIBRE — plusieurs publications par période
    # restent possibles, seul le libellé s'adapte. Vide = déduit de
    # l'activité (maraîcher : semaine, arboriculteur : mois…).
    class Rythme(models.TextChoices):
        JOUR = "JOUR", "Quotidien — « …du jour »"
        SEMAINE = "SEMAINE", "Hebdomadaire — « …de la semaine »"
        MOIS = "MOIS", "Mensuel — « …du mois »"
        SAISON = "SAISON", "Saisonnier — « …de la saison »"

    rythme_publication = models.CharField(
        "Rythme de publication", max_length=8,
        choices=Rythme.choices, blank=True, default="")
    # Paramètres de messagerie du propriétaire (page Paramètres) :
    # serveur SMTP d'envoi des e-mails (newsletters, annonces,
    # confirmations) et passerelle SMS pour la disponibilité hebdo.
    messagerie = models.JSONField("Messagerie", default=dict, blank=True,
                                  help_text='Ex : {"email_host": "smtp…"}')

    class Meta:
        verbose_name = "Paramètres de vitrine"
        verbose_name_plural = "Paramètres de vitrine"

    def __str__(self):
        return f"Vitrine de {self.exploitant}"



class MembreExploitation(models.Model):
    """Compte individuel rattaché à une exploitation : plusieurs
    personnes (famille, salariés, associés) peuvent gérer la même ferme
    — même SIRET — sans y être « propriétaire » du compte.

    Le propriétaire reste l'utilisateur porteur du OneToOneField
    Exploitant.user ; les membres accèdent aux mêmes espace pro,
    commandes et paniers via exploitant_pour().
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                 related_name="membre_exploitation")
    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                    related_name="membres")
    telephone = models.CharField("Téléphone", max_length=20, blank=True)
    ajoute_le = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        verbose_name = "Membre de l'exploitation"
        verbose_name_plural = "Membres de l'exploitation"
        ordering = ["ajoute_le"]

    def __str__(self):
        return (f"{self.user.get_full_name() or self.user.username}"
                f" — {self.exploitant.nom_ferme}")


class Favori(models.Model):
    """Producteur favori d'un compte : accès rapide depuis
    « Mes favoris ». Les clients ajoutent simplement des producteurs ;
    les pros distinguent leurs Fournisseurs de leurs Clients pro."""

    class Nature(models.TextChoices):
        CLIENT = "CLIENT", "Producteur suivi"
        FOURNISSEUR = "FOURNISSEUR", "Fournisseur"
        CLIENT_PRO = "CLIENT_PRO", "Client pro"

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name="favoris")
    exploitant = models.ForeignKey(Exploitant, on_delete=models.CASCADE,
                                   related_name="clients_favoris")
    nature = models.CharField("Nature du favori", max_length=20,
                              choices=Nature.choices,
                              default=Nature.CLIENT)
    ajoute_le = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        verbose_name = "Producteur favori"
        verbose_name_plural = "Producteurs favoris"
        unique_together = ("user", "exploitant")
        ordering = ["-ajoute_le"]

    def __str__(self):
        return (f"⭐ {self.exploitant.nom_ferme}"
                f" ({self.user.username})")


class Visiteur(models.Model):
    """Compteur d'audience minimaliste et RGPD-friendly : une ligne par
    session anonyme (clé de session, aucune donnée personnelle),
    créée/mise à jour à chaque rendu de page. Alimente le dénombrement
    « visiteurs » de la page de recherche."""

    session_key = models.CharField("Clé de session", max_length=40,
                                   unique=True)
    premiere_visite = models.DateTimeField("Première visite",
                                           auto_now_add=True)
    derniere_visite = models.DateTimeField("Dernière visite",
                                           auto_now=True)

    class Meta:
        verbose_name = "Visiteur"
        verbose_name_plural = "Visiteurs"

    def __str__(self):
        return f"👀 Visiteur {self.session_key[:8]}…"


class StatistiqueQuotidienne(models.Model):
    """Photo quotidienne des dénombrements du portail (producteurs
    visibles, clients inscrits, visiteurs) : alimente les mini-graphes
    de tendance de la page de recherche. Aucune donnée personnelle."""

    date = models.DateField("Jour", unique=True)
    nb_producteurs = models.PositiveIntegerField("Producteurs", default=0)
    nb_clients = models.PositiveIntegerField("Clients", default=0)
    nb_visiteurs = models.PositiveIntegerField("Visiteurs", default=0)

    class Meta:
        verbose_name = "Statistique quotidienne"
        verbose_name_plural = "Statistiques quotidiennes"
        ordering = ["date"]

    def __str__(self):
        return f"📊 {self.date} : {self.nb_producteurs} / " \
               f"{self.nb_clients} / {self.nb_visiteurs}"


def exploitant_pour(user):
    """L'exploitation gérée par ce compte, ou None : soit le compte
    propriétaire (Exploitant.user), soit un membre rattaché."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    exploitant = getattr(user, "exploitant", None)
    if exploitant is not None:
        return exploitant
    membre = getattr(user, "membre_exploitation", None)
    if membre is not None:
        return membre.exploitant
    return None
