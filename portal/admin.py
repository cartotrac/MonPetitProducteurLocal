from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (Annonce, Bulletin, Categorie, Commande, ConfigMessagerie,
                     CreneauLivraison, Exploitant, LigneCommande, LignePanier,
                     LigneRecolte, ModeleMessage, Panier, ParametresVitrine,
                     PointLivraison, PreferenceContact, Produit,
                     ProduitStandard, ProfilClient, SemaineRecolte)


class ExploitantInline(admin.StackedInline):
    model = Exploitant
    can_delete = False
    show_change_link = True


class ProfilClientInline(admin.StackedInline):
    model = ProfilClient
    can_delete = False
    show_change_link = True


class PortalUserAdmin(UserAdmin):
    inlines = [ExploitantInline, ProfilClientInline]


admin.site.unregister(User)
admin.site.register(User, PortalUserAdmin)


@admin.register(Exploitant)
class ExploitantAdmin(admin.ModelAdmin):
    list_display = ("nom_espace", "ville", "departement", "mode_production",
                    "visible")
    list_filter = ("mode_production", "visible", "departement")
    search_fields = ("nom_espace", "ville", "siret")


@admin.register(ProduitStandard)
class ProduitStandardAdmin(admin.ModelAdmin):
    list_display = ("emoji", "nom", "categorie", "unite_vente", "saisons")
    list_filter = ("categorie", "unite_vente")
    search_fields = ("nom",)


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "exploitant", "position")
    search_fields = ("nom", "exploitant__nom_espace")


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ("nom", "exploitant", "categorie", "unite_vente", "prix",
                    "actif")
    list_filter = ("actif", "unite_vente")
    search_fields = ("nom", "exploitant__nom_espace")
    autocomplete_fields = ("categorie", "origine_standard")


class LigneRecolteInline(admin.TabularInline):
    model = LigneRecolte
    extra = 0


@admin.register(SemaineRecolte)
class SemaineRecolteAdmin(admin.ModelAdmin):
    list_display = ("exploitant", "lundi", "publiee")
    list_filter = ("publiee",)
    inlines = [LigneRecolteInline]


@admin.register(PointLivraison)
class PointLivraisonAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville", "code_postal", "exploitant")
    search_fields = ("nom", "ville")


@admin.register(CreneauLivraison)
class CreneauLivraisonAdmin(admin.ModelAdmin):
    list_display = ("exploitant", "jour", "heure_debut", "heure_fin",
                    "frequence", "capacite", "point_livraison")


class LigneCommandeInline(admin.TabularInline):
    model = LigneCommande
    extra = 0
    readonly_fields = ("produit", "quantite", "prix_unitaire")


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ("id", "exploitant", "nom_client", "date_livraison",
                    "statut", "total")
    list_filter = ("statut", "date_livraison")
    search_fields = ("nom_client", "email_client", "telephone_client",
                     "exploitant__nom_espace")
    inlines = [LigneCommandeInline]


class LignePanierInline(admin.TabularInline):
    model = LignePanier
    extra = 0


@admin.register(Panier)
class PanierAdmin(admin.ModelAdmin):
    list_display = ("numero", "exploitant", "nom_client", "date_livraison",
                    "statut", "total")
    list_filter = ("statut", "date_livraison")
    search_fields = ("nom_client", "email_client", "telephone_client")
    inlines = [LignePanierInline]


@admin.register(ModeleMessage)
class ModeleMessageAdmin(admin.ModelAdmin):
    list_display = ("exploitant", "type", "canal", "actif")
    list_filter = ("type", "canal", "actif")


admin.site.register(Bulletin)
admin.site.register(Annonce)
admin.site.register(PreferenceContact)
admin.site.register(ConfigMessagerie)
admin.site.register(ParametresVitrine)
