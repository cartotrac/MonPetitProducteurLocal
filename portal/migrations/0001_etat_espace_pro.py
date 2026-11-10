"""État initial versionné des migrations du portail + renommage
nom_ferme → nom_espace (notion d'ESPACE PRO local).

⚠️ Migration SPÉCIALE : la base de production existait déjà (les
migrations étaient générées localement, hors git). Cette migration
reconstruit l'ÉTAT Django complet des modèles (CreateModel en
state_operations, aucune table créée) et applique en base le seul
changement réel : le RENAME COLUMN portal_exploitant.nom_ferme →
nom_espace. L'état reflète les modèles avec le NOUVEAU nom de champ.

Déploiement : git pull puis « python manage.py migrate ». Le RunSQL
est idempotent (ne s'exécute que si l'ancienne colonne existe).
Une base VIDE ne peut pas être recréée par migrate : repartir d'un
dump SQL.
"""
from django.db import migrations, models
import django.db.models.deletion
import portal.models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Exploitant",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom_espace", models.CharField(
                         max_length=150,
                         verbose_name="Nom de l'espace pro")),
                        ("slug", models.SlugField(
                         blank=True, max_length=160, unique=True,
                         verbose_name="Adresse publique")),
                        ("siret", models.CharField(
                         blank=True, max_length=14, verbose_name="SIRET")),
                        ("mode_production", models.CharField(
                         choices=[("AB", "Agriculture Biologique (AB)"),
                                  ("PERMA", "Permaculture"),
                                  ("PAYSAN", "Agriculture paysanne"),
                                  ("RAISONNE", "Agriculture raisonnée"),
                                  ("CONV", "Conventionnelle")],
                         default="CONV", max_length=10,
                         verbose_name="Mode de production")),
                        ("activite", models.CharField(
                         choices=[("MARAICHER", "Maraîcher·ère"),
                                  ("ARBORICULTEUR", "Arboriculteur·rice"),
                                  ("ELEVEUR", "Éleveur·euse"),
                                  ("FROMAGER", "Fromager·ère"),
                                  ("APICULTEUR", "Apiculteur·rice"),
                                  ("MICRO_BRASSEUR", "Micro-brasseur·euse"),
                                  ("CONSERVERIE", "Conserverie"),
                                  ("FOODTRUCK", "Foodtruck"),
                                  ("TRAITEUR", "Traiteur·e"),
                                  ("RESTAURANT", "Restaurant"),
                                  ("AUTRE", "Autre production locale")],
                         default="MARAICHER", max_length=15,
                         verbose_name="Activité")),
                        ("specialite", models.CharField(
                         blank=True, choices=[
                             ("SANDWICHS", "Sandwichs & plats"),
                             ("PIZZA", "Pizza au feu de bois"),
                             ("BURGER", "Burger gourmet"),
                             ("TRAITEUR", "Traiteur"),
                             ("ROTISSEUR", "Rôtisseur"),
                             ("TACOS", "Tacos & mexicain"),
                             ("KEBAB", "Kebab & grec"),
                             ("GALETTE", "Crêpes & galettes"),
                             ("POISSON", "Fish & chips — friture"),
                             ("ASIATIQUE", "Wok, buns & bao"),
                             ("GLACIER", "Glaces & desserts"),
                             ("BUFFET", "Buffets & réceptions"),
                             ("COCKTAIL", "Pièces cocktail & verrines"),
                             ("FETES", "Repas de fête & banquets"),
                             ("MARITIME", "Traiteur maritime"),
                             ("CHARCUTIER", "Charcutier-traiteur"),
                             ("MARCHE", "Cuisine du marché"),
                             ("BISTRO", "Bistronomie"),
                             ("GASTRO", "Gastronomique"),
                             ("GRILL", "Grillades & viandes"),
                             ("MER", "Poissons & fruits de mer"),
                             ("PIZZERIA", "Pizzeria"),
                             ("TERROIR", "Cuisine de terroir"),
                             ("VEGETAL", "Végétal & végétarien"),
                             ("BOVINE", "Viande bovine"),
                             ("VOLAILLE", "Volailles & œufs"),
                             ("PORCINE", "Porc & charcuterie"),
                             ("OVINE", "Agneau & mouton"),
                             ("LAPIN", "Lapins"),
                             ("AQUACULTURE", "Pisciculture & aquaculture"),
                             ("ESCARGOT", "Héliciculture — escargots")],
                         default="", max_length=12,
                         verbose_name="Spécialité")),
                        ("logo", models.ImageField(
                         blank=True, null=True,
                         upload_to=portal.models.logo_chemin,
                         verbose_name="Logo miniature")),
                        ("description", models.TextField(
                         blank=True,
                         verbose_name="Présentation de l'exploitation")),
                        ("adresse", models.CharField(
                         blank=True, max_length=255,
                         verbose_name="Adresse")),
                        ("ville", models.CharField(
                         blank=True, max_length=100,
                         verbose_name="Ville")),
                        ("code_postal", models.CharField(
                         blank=True, max_length=10,
                         verbose_name="Code postal")),
                        ("departement", models.CharField(
                         blank=True, db_index=True, max_length=3,
                         verbose_name="Département")),
                        ("telephone", models.CharField(
                         blank=True, max_length=20,
                         verbose_name="Téléphone")),
                        ("latitude", models.FloatField(
                         blank=True, help_text="Position sur la carte (optionnel)",
                         null=True, verbose_name="Latitude")),
                        ("longitude", models.FloatField(
                         blank=True, help_text="Position sur la carte (optionnel)",
                         null=True, verbose_name="Longitude")),
                        ("visible", models.BooleanField(
                         default=True,
                         verbose_name="Visible publiquement")),
                        ("est_demo", models.BooleanField(
                         default=False,
                         verbose_name="Espace de démonstration")),
                        ("mode_fonctionnement", models.CharField(
                         blank=True, choices=[
                             ("RECOLTE", "Récoltes hebdomadaires (paniers)"),
                             ("BOUTIQUE", "Boutique / stock à date")],
                         help_text=("Récoltes : la semaine se publie et se "
                                    "commande en paniers. Boutique : un stock "
                                    "de produits à date est vendu en direct "
                                    "aux points de vente."),
                         max_length=10,
                         verbose_name="Mode de fonctionnement")),
                        ("creee_le", models.DateTimeField(
                         auto_now_add=True)),
                        ("user", models.OneToOneField(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="exploitant", to="auth.user")),
                    ],
                    options={
                        "verbose_name": "Espace pro",
                        "verbose_name_plural": "Espaces pro",
                        "ordering": ["nom_espace"],
                    },
                ),
                migrations.CreateModel(
                    name="ProfilClient",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("telephone", models.CharField(
                         blank=True, max_length=20,
                         verbose_name="Téléphone")),
                        ("adresse", models.CharField(
                         blank=True, max_length=255,
                         verbose_name="Adresse")),
                        ("ville", models.CharField(
                         blank=True, max_length=100,
                         verbose_name="Ville")),
                        ("code_postal", models.CharField(
                         blank=True, max_length=10,
                         verbose_name="Code postal")),
                        ("photo_url", models.URLField(
                         blank=True,
                         help_text=("Lien vers une photo hébergée ailleurs "
                                    "(drive, cloud, réseau) : rien n'est "
                                    "hébergé par le portail."),
                         verbose_name="Photo externe")),
                        ("alias", models.CharField(
                         blank=True, help_text=("S'il est renseigné, l'alias "
                                                "remplace le nom du compte "
                                                "partout où il apparaît "
                                                "(salutation, commandes "
                                                "passées en nom propre) — "
                                                "personnalisable dans « Mon "
                                                "profil »."),
                         max_length=80, verbose_name="Alias affiché")),
                        ("user", models.OneToOneField(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="profil_client", to="auth.user")),
                    ],
                    options={"verbose_name": "Profil client"},
                ),
                migrations.CreateModel(
                    name="Categorie",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom", models.CharField(
                         max_length=80, verbose_name="Nom")),
                        ("slug", models.SlugField(blank=True,
                         max_length=100)),
                        ("position", models.PositiveSmallIntegerField(
                         default=0, verbose_name="Position")),
                        ("exploitant",
                         models.ForeignKey(
                          on_delete=django.db.models.deletion.CASCADE,
                          related_name="categories", to="portal.exploitant")),
                    ],
                    options={
                        "verbose_name": "Catégorie",
                        "ordering": ["position", "nom"],
                        "unique_together": {("exploitant", "nom")},
                    },
                ),
                migrations.CreateModel(
                    name="ProduitStandard",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom", models.CharField(
                         max_length=150, verbose_name="Nom")),
                        ("categorie", models.CharField(
                         max_length=80,
                         verbose_name="Catégorie standard")),
                        ("activite", models.CharField(
                         choices=[("MARAICHER", "Maraîcher·ère"),
                                  ("ARBORICULTEUR", "Arboriculteur·rice"),
                                  ("ELEVEUR", "Éleveur·euse"),
                                  ("FROMAGER", "Fromager·ère"),
                                  ("APICULTEUR", "Apiculteur·rice"),
                                  ("MICRO_BRASSEUR", "Micro-brasseur·euse"),
                                  ("CONSERVERIE", "Conserverie"),
                                  ("FOODTRUCK", "Foodtruck"),
                                  ("TRAITEUR", "Traiteur·e"),
                                  ("RESTAURANT", "Restaurant"),
                                  ("AUTRE", "Autre production locale")],
                         default="MARAICHER", max_length=15,
                         verbose_name="Activité")),
                        ("unite_vente", models.CharField(
                         choices=[("KG", "le kg"), ("PC", "la pièce"),
                                  ("BO", "la botte"), ("BQ", "la barquette")],
                         default="KG", max_length=2,
                         verbose_name="Unité de vente")),
                        ("saisons", models.JSONField(
                         blank=True, default=list,
                         help_text='Ex : ["printemps", "été"]',
                         verbose_name="Saisons")),
                        ("emoji", models.CharField(
                         blank=True, max_length=8, verbose_name="Emoji")),
                        ("svg", models.TextField(blank=True,
                         verbose_name="SVG inline")),
                        ("prix_indicatif", models.DecimalField(
                         blank=True, decimal_places=2, help_text=(
                          "Prix unitaire réaliste suggéré par défaut lors "
                          "de la copie."), max_digits=6, null=True,
                         verbose_name="Prix indicatif (€)")),
                    ],
                    options={
                        "verbose_name": "Produit standard",
                        "ordering": ["categorie", "nom"],
                        "verbose_name_plural":
                            "Produits standard (catalogue embarqué)",
                    },
                ),
                migrations.CreateModel(
                    name="Produit",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom", models.CharField(
                         max_length=150, verbose_name="Nom")),
                        ("slug", models.SlugField(blank=True,
                         max_length=160)),
                        ("description", models.TextField(
                         blank=True, verbose_name="Description")),
                        ("illustration", models.ImageField(
                         blank=True, null=True,
                         upload_to=portal.models.illustration_produit_chemin,
                         verbose_name="Photo")),
                        ("unite_vente", models.CharField(
                         choices=[("KG", "le kg"), ("PC", "la pièce"),
                                  ("BO", "la botte"), ("BQ", "la barquette")],
                         default="KG", max_length=2,
                         verbose_name="Unité de vente")),
                        ("attributs", models.JSONField(
                         blank=True, default=dict,
                         help_text='Ex : {"variété": "Butternut", "label": "AB"}',
                         verbose_name="Attributs libres")),
                        ("perso", models.BooleanField(
                         default=False,
                         verbose_name="Créé pour mon usage propre")),
                        ("prix", models.DecimalField(
                         blank=True, decimal_places=2, max_digits=6,
                         null=True, verbose_name="Prix de référence (€)")),
                        ("actif", models.BooleanField(default=True,
                         verbose_name="Actif")),
                        ("position", models.PositiveSmallIntegerField(
                         default=0, verbose_name="Position")),
                        ("emoji", models.CharField(
                         blank=True, help_text=(
                          "Symbole affiché dans toutes les listes : hérité "
                          "du produit type d'origine, ou deviné par "
                          "mot-clé (commande charger_catalogues_activites)."),
                         max_length=8, verbose_name="Emoji")),
                        ("categorie", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="produits", to="portal.categorie")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="produits", to="portal.exploitant")),
                        ("origine_standard", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="copies",
                         to="portal.produitstandard")),
                    ],
                    options={
                        "verbose_name": "Produit",
                        "ordering": ["categorie__position", "categorie__nom",
                                     "position", "nom"],
                        "unique_together": {("exploitant", "slug")},
                    },
                ),
                migrations.CreateModel(
                    name="SemaineRecolte",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("lundi", models.DateField(
                         db_index=True,
                         verbose_name="Lundi de la semaine")),
                        ("note", models.CharField(
                         blank=True, max_length=255,
                         verbose_name="Note / actualité de la semaine")),
                        ("publiee", models.BooleanField(
                         default=True,
                         verbose_name="Publiée aux clients")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="semaines", to="portal.exploitant")),
                    ],
                    options={
                        "ordering": ["-lundi"],
                        "unique_together": {("exploitant", "lundi")},
                        "verbose_name": "Semaine de récolte",
                        "verbose_name_plural": "Semaines de récolte",
                    },
                ),
                migrations.CreateModel(
                    name="LigneRecolte",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("quantite_estimee", models.DecimalField(
                         decimal_places=2, max_digits=8,
                         verbose_name="Quantité estimée")),
                        ("prix_unitaire", models.DecimalField(
                         decimal_places=2, max_digits=6,
                         verbose_name="Prix unitaire (€)")),
                        ("produit", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="lignes_recolte",
                         to="portal.produit")),
                        ("recolte", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="lignes",
                         to="portal.semainerecolte")),
                    ],
                    options={
                        "unique_together": {("recolte", "produit")},
                        "verbose_name": "Ligne de récolte (estimation)",
                    },
                ),
                migrations.CreateModel(
                    name="PointLivraison",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom", models.CharField(
                         max_length=150, verbose_name="Nom")),
                        ("adresse", models.CharField(
                         max_length=255, verbose_name="Adresse")),
                        ("ville", models.CharField(
                         max_length=100, verbose_name="Ville")),
                        ("code_postal", models.CharField(
                         max_length=10, verbose_name="Code postal")),
                        ("note", models.TextField(
                         blank=True, verbose_name="Précisions")),
                        ("latitude", models.FloatField(
                         blank=True, null=True,
                         verbose_name="Latitude")),
                        ("longitude", models.FloatField(
                         blank=True, null=True,
                         verbose_name="Longitude")),
                        ("type_point", models.CharField(
                         choices=[("LIVRAISON", "Point de livraison / retrait"),
                                  ("BOUTIQUE", "Boutique / point de vente"),
                                  ("MARCHE", "Marché"),
                                  ("EMPLACEMENT",
                                   "Emplacement / arrêt foodtruck")],
                         default="LIVRAISON", help_text=(
                          "Livraison de paniers, vente en boutique ou stand "
                          "de marché : les créneaux récurrents se "
                          "rattachent à n'importe lequel de ces points."),
                         max_length=12,
                         verbose_name="Type de mise en relation")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="points_livraison",
                         to="portal.exploitant")),
                    ],
                    options={
                        "ordering": ["ville", "nom"],
                        "verbose_name": "Point de livraison",
                    },
                ),
                migrations.CreateModel(
                    name="CreneauLivraison",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("jour", models.PositiveSmallIntegerField(
                         choices=[(1, "Lundi"), (2, "Mardi"),
                                  (3, "Mercredi"), (4, "Jeudi"),
                                  (5, "Vendredi"), (6, "Samedi"),
                                  (7, "Dimanche")],
                         verbose_name="Jour")),
                        ("heure_debut", models.TimeField(
                         verbose_name="Début")),
                        ("heure_fin", models.TimeField(
                         verbose_name="Fin")),
                        ("frequence", models.CharField(
                         choices=[("H", "Chaque semaine"),
                                  ("B", "Une semaine sur deux"),
                                  ("M", "Une fois par mois")],
                         default="H", max_length=1,
                         verbose_name="Fréquence")),
                        ("capacite", models.PositiveSmallIntegerField(
                         default=10,
                         verbose_name="Capacité (paniers/commandes)")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="creneaux", to="portal.exploitant")),
                        ("point_livraison", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="creneaux",
                         to="portal.pointlivraison")),
                    ],
                    options={
                        "ordering": ["jour", "heure_debut"],
                        "verbose_name": "Créneau de livraison",
                    },
                ),
                migrations.CreateModel(
                    name="Carte",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom", models.CharField(
                         help_text=("Ex : « Carte du moment », « Menu de "
                                    "fête », « En boutique en ce moment »."),
                         max_length=120, verbose_name="Nom de la carte")),
                        ("statut", models.CharField(
                         choices=[("BROUILLON", "Brouillon"),
                                  ("ACTIVE", "Publiée (active)"),
                                  ("ARCHIVEE", "Archivée")],
                         db_index=True, default="BROUILLON",
                         max_length=10, verbose_name="Statut")),
                        ("creee_le", models.DateTimeField(
                         auto_now_add=True, verbose_name="Créée le")),
                        ("maj_le", models.DateTimeField(
                         auto_now=True, verbose_name="Mise à jour")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="cartes", to="portal.exploitant")),
                    ],
                    options={
                        "ordering": ["-maj_le"],
                        "verbose_name": "Carte / boutique",
                        "verbose_name_plural": "Cartes / boutiques",
                    },
                ),
                migrations.CreateModel(
                    name="LigneCarte",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom_libre", models.CharField(
                         blank=True, default="", help_text=(
                          "Si la ligne ne reprend pas un produit du "
                          "catalogue."),
                         max_length=150,
                         verbose_name="Nom (ligne libre)")),
                        ("section", models.CharField(
                         blank=True, default="", help_text=(
                          "Ex : « Entrées », « Plats », « Fromages au lait "
                          "cru »…"),
                         max_length=80, verbose_name="Section")),
                        ("description", models.TextField(
                         blank=True, verbose_name="Description")),
                        ("unite_vente", models.CharField(
                         choices=[("KG", "le kg"), ("PC", "la pièce"),
                                  ("BO", "la botte"), ("BQ", "la barquette")],
                         default="KG", max_length=2,
                         verbose_name="Unité de vente")),
                        ("prix", models.DecimalField(
                         blank=True, decimal_places=2, help_text=(
                          "Vide : prix du produit lié."), max_digits=6,
                         null=True, verbose_name="Prix (€)")),
                        ("stock", models.DecimalField(
                         blank=True, decimal_places=2, help_text=(
                          "Quantité mise en vente : vide = illimité."),
                         max_digits=8, null=True,
                         verbose_name="Stock publié")),
                        ("position", models.PositiveSmallIntegerField(
                         default=0, verbose_name="Position")),
                        ("carte", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="lignes", to="portal.carte")),
                        ("produit", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="lignes_cartes", to="portal.produit")),
                    ],
                    options={
                        "ordering": ["section", "position", "id"],
                        "verbose_name": "Ligne de carte",
                        "verbose_name_plural": "Lignes de carte",
                    },
                ),
                migrations.CreateModel(
                    name="Commande",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom_client", models.CharField(
                         max_length=150, verbose_name="Nom du client")),
                        ("email_client", models.EmailField(
                         blank=True, max_length=254,
                         verbose_name="E-mail du client")),
                        ("telephone_client", models.CharField(
                         blank=True, help_text=(
                          "E-mail OU téléphone requis"), max_length=20,
                         verbose_name="Téléphone du client")),
                        ("date_livraison", models.DateField(
                         verbose_name="Date de livraison souhaitée")),
                        ("statut", models.CharField(
                         choices=[("NOUVELLE", "À valider"),
                                  ("VALIDEE", "Validée"),
                                  ("REFUSEE", "Refusée"),
                                  ("ANNULEE", "Annulée")],
                         db_index=True, default="NOUVELLE", max_length=10,
                         verbose_name="Statut")),
                        ("annulee_par", models.CharField(
                         blank=True, choices=[
                             ("CLIENT", "Client"),
                             ("PRODUCTEUR", "Producteur")],
                         default="", help_text=(
                          "Discerne l'annulation client de l'annulation "
                          "producteur (panier annulé en préparation)."),
                         max_length=12, verbose_name="Annulée par")),
                        ("motif_annulation", models.CharField(
                         blank=True, default="", help_text=(
                          "Motif optionnel : saisi par le client à "
                          "l'annulation, ou repris du panier pour une "
                          "annulation producteur."),
                         max_length=200,
                         verbose_name="Motif d'annulation")),
                        ("total", models.DecimalField(
                         decimal_places=2, default=0, max_digits=8,
                         verbose_name="Total (€)")),
                        ("note", models.TextField(
                         blank=True, verbose_name="Message du client")),
                        ("motif_refus", models.TextField(
                         blank=True, default="", help_text=(
                          "Raison visible par le client quand le "
                          "producteur refuse la commande."),
                         verbose_name="Motif du refus")),
                        ("saisie_exploitant", models.BooleanField(
                         default=False,
                         verbose_name="Saisie directe de l'exploitant")),
                        ("creee_le", models.DateTimeField(
                         auto_now_add=True)),
                        ("validee_le", models.DateTimeField(
                         blank=True, null=True,
                         verbose_name="Validée le")),
                        ("client", models.ForeignKey(
                         blank=True, help_text="Null si client sans compte",
                         null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="commandes", to="auth.user")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="commandes", to="portal.exploitant")),
                        ("point_livraison", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="commandes",
                         to="portal.pointlivraison")),
                    ],
                    options={
                        "ordering": ["-creee_le"],
                        "verbose_name": "Commande",
                        "verbose_name_plural": "Commandes",
                    },
                ),
                migrations.CreateModel(
                    name="LigneCommande",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("quantite", models.DecimalField(
                         decimal_places=2, max_digits=8,
                         verbose_name="Quantité")),
                        ("prix_unitaire", models.DecimalField(
                         decimal_places=2, max_digits=6,
                         verbose_name="Prix unitaire (€)")),
                        ("commande", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="lignes", to="portal.commande")),
                        ("produit", models.ForeignKey(
                         on_delete=django.db.models.deletion.PROTECT,
                         related_name="lignes_commande",
                         to="portal.produit")),
                    ],
                    options={
                        "verbose_name": "Ligne de commande",
                    },
                ),
                migrations.CreateModel(
                    name="Panier",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nom_client", models.CharField(
                         max_length=150, verbose_name="Nom du client")),
                        ("email_client", models.EmailField(
                         blank=True, max_length=254,
                         verbose_name="E-mail du client")),
                        ("telephone_client", models.CharField(
                         blank=True, max_length=20,
                         verbose_name="Téléphone du client")),
                        ("numero", models.PositiveSmallIntegerField(
                         verbose_name="N° de panier")),
                        ("date_livraison", models.DateField(
                         db_index=True,
                         verbose_name="Jour de livraison")),
                        ("statut", models.CharField(
                         choices=[("PREPARATION", "En préparation"),
                                  ("PRET", "Prêt"), ("LIVRE", "Livré"),
                                  ("RECU", "Reçu / retiré"),
                                  ("ANNULE", "Annulé")],
                         db_index=True, default="PREPARATION",
                         max_length=12, verbose_name="Statut")),
                        ("total", models.DecimalField(
                         decimal_places=2, default=0, max_digits=8,
                         verbose_name="Total (€)")),
                        ("note", models.TextField(
                         blank=True, help_text=(
                          "Visible par le client (ajustements, "
                          "remplacements éventuels)"),
                         verbose_name="Commentaire du producteur")),
                        ("motif_annulation", models.TextField(
                         blank=True, default="", help_text=(
                          "Raison visible par le client quand un panier "
                          "en préparation est annulé ; la commande repasse "
                          "alors « Annulée » et peut être recommandée."),
                         verbose_name="Motif d'annulation")),
                        ("point_nom", models.CharField(
                         blank=True, default="", max_length=150,
                         verbose_name="Nom du point (figé)")),
                        ("point_adresse", models.CharField(
                         blank=True, default="", max_length=255,
                         verbose_name="Adresse du point (figée)")),
                        ("point_code_postal", models.CharField(
                         blank=True, default="", max_length=10,
                         verbose_name="CP du point (figé)")),
                        ("point_ville", models.CharField(
                         blank=True, default="", max_length=100,
                         verbose_name="Ville du point (figée)")),
                        ("point_latitude", models.FloatField(
                         blank=True, null=True,
                         verbose_name="Latitude du point (figée)")),
                        ("point_longitude", models.FloatField(
                         blank=True, null=True,
                         verbose_name="Longitude du point (figée)")),
                        ("client", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="paniers", to="auth.user")),
                        ("commande", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="paniers", to="portal.commande")),
                        ("creneau", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="paniers",
                         to="portal.creneaulivraison")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="paniers", to="portal.exploitant")),
                        ("point_livraison", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         related_name="paniers",
                         to="portal.pointlivraison")),
                    ],
                    options={
                        "ordering": ["date_livraison", "numero"],
                        "unique_together": {("exploitant", "client",
                                             "date_livraison", "numero")},
                        "verbose_name": "Panier",
                    },
                ),
                migrations.CreateModel(
                    name="LignePanier",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("quantite", models.DecimalField(
                         decimal_places=2, max_digits=8,
                         verbose_name="Quantité livrée")),
                        ("prix_unitaire", models.DecimalField(
                         decimal_places=2, max_digits=6,
                         verbose_name="Prix unitaire (€)")),
                        ("panier", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="lignes", to="portal.panier")),
                        ("produit", models.ForeignKey(
                         on_delete=django.db.models.deletion.PROTECT,
                         related_name="lignes_panier", to="portal.produit")),
                    ],
                    options={
                        "verbose_name": "Ligne de panier (livré)",
                    },
                ),
                migrations.CreateModel(
                    name="ModeleMessage",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("type", models.CharField(
                         choices=[
                             ("CONFIRMATION_COMMANDE",
                              "Confirmation de commande"),
                             ("PANIER_PRET", "Panier prêt"),
                             ("LIVRAISON_FAITE", "Livraison faite"),
                             ("BULLETIN", "Bulletin (newsletter)"),
                             ("ANNONCE", "Annonce")],
                         max_length=25, verbose_name="Type")),
                        ("canal", models.CharField(
                         choices=[("EMAIL", "E-mail"), ("SMS", "SMS")],
                         default="EMAIL", max_length=5,
                         verbose_name="Canal")),
                        ("objet", models.CharField(
                         max_length=200, verbose_name="Objet")),
                        ("corps", models.TextField(verbose_name="Corps")),
                        ("actif", models.BooleanField(default=True,
                         verbose_name="Actif")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="modeles_message",
                         to="portal.exploitant")),
                    ],
                    options={
                        "unique_together": {("exploitant", "type", "canal")},
                        "verbose_name": "Modèle de message",
                    },
                ),
                migrations.CreateModel(
                    name="Bulletin",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("objet", models.CharField(
                         max_length=200, verbose_name="Objet")),
                        ("corps", models.TextField(verbose_name="Corps")),
                        ("envoye_le", models.DateTimeField(
                         blank=True, null=True,
                         verbose_name="Envoyé le")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="bulletins",
                         to="portal.exploitant")),
                        ("semaine", models.ForeignKey(
                         blank=True, null=True,
                         on_delete=django.db.models.deletion.SET_NULL,
                         to="portal.semainerecolte")),
                    ],
                    options={
                        "ordering": ["-envoye_le"],
                        "verbose_name": "Bulletin",
                    },
                ),
                migrations.CreateModel(
                    name="Annonce",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("objet", models.CharField(
                         max_length=200, verbose_name="Objet")),
                        ("corps", models.TextField(verbose_name="Corps")),
                        ("envoye_le", models.DateTimeField(
                         blank=True, null=True,
                         verbose_name="Envoyé le")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="annonces", to="portal.exploitant")),
                    ],
                    options={
                        "ordering": ["-envoye_le"],
                        "verbose_name": "Annonce",
                    },
                ),
                migrations.CreateModel(
                    name="PreferenceContact",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("veut_bulletin", models.BooleanField(
                         default=True,
                         verbose_name="Recevoir le bulletin")),
                        ("veut_annonces", models.BooleanField(
                         default=True,
                         verbose_name="Recevoir les annonces")),
                        ("canal", models.CharField(
                         choices=[("EMAIL", "E-mail"), ("SMS", "SMS")],
                         default="EMAIL", max_length=5,
                         verbose_name="Canal préféré")),
                        ("client", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="preferences_contact",
                         to="auth.user")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="preferences_clients",
                         to="portal.exploitant")),
                    ],
                    options={
                        "unique_together": {("client", "exploitant")},
                        "verbose_name": "Préférence de contact",
                    },
                ),
                migrations.CreateModel(
                    name="ConfigMessagerie",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("smtp_hote", models.CharField(
                         blank=True, max_length=255,
                         verbose_name="Serveur SMTP")),
                        ("smtp_port", models.PositiveSmallIntegerField(
                         default=587, verbose_name="Port SMTP")),
                        ("smtp_utilisateur", models.CharField(
                         blank=True, max_length=150,
                         verbose_name="Utilisateur SMTP")),
                        ("smtp_mot_de_passe", models.CharField(
                         blank=True, max_length=255,
                         verbose_name="Mot de passe SMTP")),
                        ("smtp_expediteur", models.EmailField(
                         blank=True, max_length=254,
                         verbose_name="Adresse d'expédition")),
                        ("passerelle_sms", models.CharField(
                         blank=True,
                         choices=[("FREE", "Free Mobile"), ("OVH", "OVH"),
                                  ("TWILIO", "Twilio"),
                                  ("HTTP_PERSO", "HTTP personnalisée")],
                         max_length=15,
                         verbose_name="Passerelle SMS")),
                        ("config_sms", models.JSONField(
                         blank=True, default=dict,
                         verbose_name="Configuration passerelle")),
                        ("quota_journalier",
                         models.PositiveSmallIntegerField(
                          default=100,
                          verbose_name="Quota d'envois / jour")),
                        ("heures_calmes", models.CharField(
                         blank=True, help_text=(
                          "Ex : 21:00-08:00 — pas d'envoi dans cette "
                          "plage"), max_length=11,
                         verbose_name="Heures calmes")),
                        ("exploitant", models.OneToOneField(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="config_messagerie",
                         to="portal.exploitant")),
                    ],
                    options={
                        "verbose_name": "Configuration messagerie",
                    },
                ),
                migrations.CreateModel(
                    name="ParametresVitrine",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("titre_accroche", models.CharField(
                         blank=True, max_length=150,
                         verbose_name="Titre d'accroche")),
                        ("texte_accroche", models.TextField(
                         blank=True, verbose_name="Texte d'accroche")),
                        ("couleur_theme", models.CharField(
                         default="#2e7d32", max_length=7,
                         verbose_name="Couleur d'accent")),
                        ("image_banniere", models.ImageField(
                         blank=True, null=True,
                         upload_to=portal.models.banniere_chemin,
                         verbose_name="Bannière")),
                        ("afficher_recolte", models.BooleanField(
                         default=True,
                         verbose_name="Afficher la récolte")),
                        ("afficher_catalogue", models.BooleanField(
                         default=True,
                         verbose_name="Afficher le catalogue")),
                        ("afficher_creneaux", models.BooleanField(
                         default=True,
                         verbose_name="Afficher les créneaux")),
                        ("reseaux", models.JSONField(
                         blank=True, default=dict,
                         help_text='Ex : {"facebook": "https://…"}',
                         verbose_name="Réseaux sociaux")),
                        ("rythme_publication", models.CharField(
                         blank=True,
                         choices=[("JOUR", "Quotidien — « …du jour »"),
                                  ("SEMAINE",
                                   "Hebdomadaire — « …de la semaine »"),
                                  ("MOIS", "Mensuel — « …du mois »"),
                                  ("SAISON",
                                   "Saisonnier — « …de la saison »")],
                         default="", max_length=8,
                         verbose_name="Rythme de publication")),
                        ("messagerie", models.JSONField(
                         blank=True, default=dict,
                         help_text='Ex : {"email_host": "smtp…"}',
                         verbose_name="Messagerie")),
                        ("exploitant", models.OneToOneField(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="parametres_vitrine",
                         to="portal.exploitant")),
                    ],
                    options={
                        "verbose_name": "Paramètres de vitrine",
                        "verbose_name_plural": "Paramètres de vitrine",
                    },
                ),
                migrations.CreateModel(
                    name="MembreExploitation",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("telephone", models.CharField(
                         blank=True, max_length=20,
                         verbose_name="Téléphone")),
                        ("ajoute_le", models.DateTimeField(
                         auto_now_add=True, verbose_name="Ajouté le")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="membres", to="portal.exploitant")),
                        ("user", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="membres_exploitation",
                         to="auth.user")),
                    ],
                    options={
                        "ordering": ["ajoute_le"],
                        "unique_together": {("user", "exploitant")},
                        "verbose_name": "Membre de l'espace",
                        "verbose_name_plural": "Membres de l'espace",
                    },
                ),
                migrations.CreateModel(
                    name="Favori",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("nature", models.CharField(
                         choices=[("CLIENT", "Producteur suivi"),
                                  ("FOURNISSEUR", "Fournisseur"),
                                  ("CLIENT_PRO", "Client pro")],
                         default="CLIENT", max_length=20,
                         verbose_name="Nature du favori")),
                        ("ajoute_le", models.DateTimeField(
                         auto_now_add=True, verbose_name="Ajouté le")),
                        ("exploitant", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="clients_favoris",
                         to="portal.exploitant")),
                        ("user", models.ForeignKey(
                         on_delete=django.db.models.deletion.CASCADE,
                         related_name="favoris", to="auth.user")),
                    ],
                    options={
                        "ordering": ["-ajoute_le"],
                        "unique_together": {("user", "exploitant")},
                        "verbose_name": "Producteur favori",
                        "verbose_name_plural": "Producteurs favoris",
                    },
                ),
                migrations.CreateModel(
                    name="Visiteur",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("session_key", models.CharField(
                         max_length=40, unique=True,
                         verbose_name="Clé de session")),
                        ("premiere_visite", models.DateTimeField(
                         auto_now_add=True,
                         verbose_name="Première visite")),
                        ("derniere_visite", models.DateTimeField(
                         auto_now=True, verbose_name="Dernière visite")),
                    ],
                    options={
                        "verbose_name": "Visiteur",
                        "verbose_name_plural": "Visiteurs",
                    },
                ),
                migrations.CreateModel(
                    name="StatistiqueQuotidienne",
                    fields=[
                        ("id", models.AutoField(auto_created=True,
                         primary_key=True, serialize=False,
                         verbose_name="ID")),
                        ("date", models.DateField(unique=True,
                         verbose_name="Jour")),
                        ("nb_producteurs",
                         models.PositiveIntegerField(
                          default=0, verbose_name="Producteurs")),
                        ("nb_clients", models.PositiveIntegerField(
                         default=0, verbose_name="Clients")),
                        ("nb_visiteurs", models.PositiveIntegerField(
                         default=0, verbose_name="Visiteurs")),
                        ("nb_pros_reels", models.PositiveIntegerField(
                         default=0, verbose_name="Pros réels")),
                        ("nb_locaux", models.PositiveIntegerField(
                         default=0,
                         verbose_name="Producteurs locaux")),
                        ("nb_locaux_reels",
                         models.PositiveIntegerField(
                          default=0,
                          verbose_name="Producteurs locaux réels")),
                        ("nb_restauration",
                         models.PositiveIntegerField(
                          default=0, verbose_name="Pros restauration")),
                        ("nb_restauration_reels",
                         models.PositiveIntegerField(
                          default=0,
                          verbose_name="Pros restauration réels")),
                        ("nb_marches", models.PositiveIntegerField(
                         default=0, verbose_name="Marchés")),
                        ("nb_boutiques", models.PositiveIntegerField(
                         default=0, verbose_name="Boutiques")),
                        ("nb_marches_reels",
                         models.PositiveIntegerField(
                          default=0, verbose_name="Marchés réels")),
                        ("nb_boutiques_reels",
                         models.PositiveIntegerField(
                          default=0, verbose_name="Boutiques réelles")),
                    ],
                    options={
                        "ordering": ["date"],
                        "verbose_name": "Statistique quotidienne",
                        "verbose_name_plural": "Statistiques quotidiennes",
                    },
                ),
            ],
            database_operations=[
                # Renommage réel en base : la colonne existante
                # portal_exploitant.nom_ferme devient nom_espace.
                # Idempotent : ne s'exécute que si l'ancienne colonne
                # existe encore (base de prod existante).
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = 'portal_exploitant' "
                        "AND column_name = 'nom_ferme') THEN "
                        "ALTER TABLE portal_exploitant "
                        "RENAME COLUMN nom_ferme TO nom_espace; "
                        "END IF; END $$;"),
                    reverse_sql=(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = 'portal_exploitant' "
                        "AND column_name = 'nom_espace') THEN "
                        "ALTER TABLE portal_exploitant "
                        "RENAME COLUMN nom_espace TO nom_ferme; "
                        "END IF; END $$;"),
                ),
            ],
        ),
    ]
