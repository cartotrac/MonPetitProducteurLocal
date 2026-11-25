"""Filtres de template : accord des unités avec la quantité et
affichage propre des quantités.

Usage :
    {% load unites %}
    {{ ligne.quantite }} {{ ligne.quantite|unite:ligne.produit }}
    {{ ligne.quantite|qte }}            -> « 5 » au lieu de « 5,00 »
    {{ valeurs|get_item:offre.cle }}    -> accès dictionnaire à clé dynamique
"""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def unite(quantite, produit):
    """Libellé d'unité accordé à la quantité (singulier/pluriel),
    via Produit.unite_pour(). Les quantités entières (pièce, botte,
    barquette) restent des entiers à la saisie ; seul le kilogramme
    accepte les décimales."""
    try:
        return produit.unite_pour(quantite)
    except AttributeError:
        return getattr(produit, "unite_courte", "")


@register.filter
def qte(valeur):
    """Quantité affichée sans zéros parasites : Decimal('5.00') -> « 5 »,
    Decimal('2.50') -> « 2,5 ». Les produits vendus à la pièce, à la
    botte ou à la barquette sont saisis en entiers ; seule l'unité kg
    garde des décimales."""
    try:
        nombre = Decimal(str(valeur)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return valeur
    texte = format(nombre, "f")
    if "." in texte:
        texte = texte.rstrip("0").rstrip(".")
    return texte.replace(".", ",")


@register.filter
def get_item(dico, cle):
    """Accès à une clé dynamique de dictionnaire dans un template."""
    try:
        return dico.get(cle, "")
    except AttributeError:
        return ""


@register.filter
def contient_sans_choisi(paires):
    """Vrai si au moins un groupe de la publication saisonnière n'a
    AUCUN produit retenu : ces rubriques sont repliées en bas de la
    zone de saisie (elles n'apparaissent jamais sur la vitrine)."""
    try:
        return any(not g.get("nb_choisis") for g in paires)
    except (TypeError, AttributeError):
        return False
