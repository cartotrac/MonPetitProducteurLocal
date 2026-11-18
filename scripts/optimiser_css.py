#!/usr/bin/env python3
"""Script d'optimisation et minification CSS pour MonPetitProducteurLocal.

Ce script :
1. Lit static/css/append.css (et static/css/style.css)
2. Supprime les commentaires et espaces superflus
3. Génère static/css/append.min.css et static/css/style.min.css
4. Est appelé automatiquement par scripts/deploy_prod.sh avant collectstatic
"""

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_CSS = BASE_DIR / "static" / "css"


def minifier_css(css_text: str) -> str:
    """Minifie une chaîne de code CSS sans altérer les règles valides."""
    # 1. Supprimer les commentaires CSS /* ... */
    css = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    # 2. Normaliser les espaces consécutifs en un seul espace
    css = re.sub(r"\s+", " ", css)
    # 3. Supprimer les espaces autour des délimiteurs et opérateurs CSS
    css = re.sub(r"\s*([\{\};:,>~+])\s*", r"\1", css)
    # 4. Supprimer les points-virgules superflus en fin de bloc
    css = re.sub(r";\}", "}", css)
    # 5. Supprimer les espaces autour de !important
    css = re.sub(r"\s*!important", "!important", css)
    # 6. Supprimer les blocs vides résiduels (ex: a{})
    css = re.sub(r"[^{}]+\{\}", "", css)
    return css.strip()


def traiter_fichier(nom_source: str, nom_cible: str):
    fichier_source = STATIC_CSS / nom_source
    fichier_cible = STATIC_CSS / nom_cible

    if not fichier_source.exists():
        print(f"[-] Fichier introuvable : {fichier_source}", file=sys.stderr)
        return

    with open(fichier_source, "r", encoding="utf-8") as f:
        contenu = f.read()

    taille_init = len(contenu.encode("utf-8"))
    minifie = minifier_css(contenu)
    taille_min = len(minifie.encode("utf-8"))

    with open(fichier_cible, "w", encoding="utf-8", newline="\n") as f:
        f.write(minifie)

    gain = ((taille_init - taille_min) / taille_init) * 100 if taille_init else 0
    print(
        f"[+] {nom_source} -> {nom_cible} : "
        f"{taille_init/1024:.1f} Ko -> {taille_min/1024:.1f} Ko "
        f"(-{gain:.1f}%)"
    )


def main():
    print("==> Optimisation & minification des feuilles de style CSS...")
    traiter_fichier("append.css", "append.min.css")
    traiter_fichier("style.css", "style.min.css")
    print("==> Minification terminée avec succès.")


if __name__ == "__main__":
    main()
