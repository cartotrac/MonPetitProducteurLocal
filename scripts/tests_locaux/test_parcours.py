#!/usr/bin/env python3
"""Tests à froid des parcours clés du portail (volet « docs & qualité »).

Reconstruit une base sqlite jetable (schéma portal via schema_editor :
la migration 0001 de portal est spécifique PostgreSQL, on la marque
« appliquée » puis on crée les tables directement), y sème deux espaces
(maraîcher et foodtruck) et vérifie de bout en bout :

  1. vitrine publique (carte du moment, bloc « Nous trouver ») ;
  2. commande client + e-mail de confirmation (jamais bloquant) ;
  3. panier passé en « prêt » + notification e-mail au client ;
  4. page de recherche (données de la carte présentes, clustering câblé).

Usage, depuis la racine du dépôt (dépendances requirements.txt incluses) :

    python3 scripts/tests_locaux/test_parcours.py

Aucun accès réseau, aucune écriture hors du dossier du script : la base
sqlite et les e-mails restent locaux. Code de sortie : 0 si tout passe,
1 sinon (chaque échec affiché par « KO »).
"""
import datetime
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CHEMIN_ICI = os.path.dirname(os.path.abspath(__file__))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)
if CHEMIN_ICI not in sys.path:
    sys.path.insert(0, CHEMIN_ICI)
os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_test")

import django  # noqa: E402

django.setup()

# ------------------------------------------------------------ base jetable
from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
import django.db.models as dm  # noqa: E402

BASE = os.path.join(CHEMIN_ICI, "base_test.sqlite3")
if os.path.exists(BASE):
    os.remove(BASE)

call_command("migrate", "contenttypes", interactive=False, verbosity=0)
call_command("migrate", "auth", interactive=False, verbosity=0)
call_command("migrate", "sessions", interactive=False, verbosity=0)
call_command("migrate", "sites", interactive=False, verbosity=0)
call_command("migrate", "admin", interactive=False, verbosity=0)
call_command("migrate", "portal", "--fake", interactive=False, verbosity=0)

import importlib  # noqa: E402

with connection.schema_editor() as se:
    for module_nom in ("portal.models", "allauth.account.models",
                      "allauth.socialaccount.models"):
        module = importlib.import_module(module_nom)
        for nom in dir(module):
            obj = getattr(module, nom)
            if (isinstance(obj, type) and issubclass(obj, dm.Model)
                    and obj.__module__ == module_nom):
                se.create_model(obj)

from django.contrib.sites.models import Site  # noqa: E402

Site.objects.get_or_create(pk=1, defaults=dict(domain="example.com",
                                               name="example"))

# ------------------------------------------------------------------ seeds
from decimal import Decimal  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core import mail  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402
from portal.models import (Categorie, Carte, CreneauLivraison,  # noqa: E402
                           Exploitant, LigneCarte, Panier, ParametresVitrine,
                           PointLivraison, Produit)

OK, KO = [], []


def check(nom, cond, info=""):
    (OK if cond else KO).append(
        nom + (" :: " + str(info) if info and not cond else ""))


User = get_user_model()

# Un espace maraîcher et un foodtruck, chacun avec produit commandable,
# carte active, point géolocalisé et créneau récurrent.
SEEDS = [("ferme", "MARAICHER", "Ferme des Tests", 43.60, 2.15),
         ("truck", "FOODTRUCK", "Camion des Tests", 43.61, 2.16)]
for login, activite, nom_espace, lat, lon in SEEDS:
    u = User.objects.create_user(username=login, password="pw12345!",
                                 email=f"{login}@example.fr")
    e = Exploitant.objects.create(
        user=u, nom_espace=nom_espace, slug=login, activite=activite,
        visible=True, ville="Castres", code_postal="81100",
        telephone="0563221100", latitude=lat, longitude=lon)
    cat = Categorie.objects.create(exploitant=e, nom="Cat", position=1)
    prod = Produit.objects.create(exploitant=e, categorie=cat,
                                  nom="Article", prix=Decimal("3.00"),
                                  actif=True)
    carte = Carte.objects.create(exploitant=e, nom="Carte du moment",
                                 statut=Carte.Statut.ACTIVE)
    LigneCarte.objects.create(carte=carte, produit=prod,
                              prix=Decimal("3.00"))
    pt = PointLivraison.objects.create(
        exploitant=e, nom="Point principal", type_point="MARCHE",
        adresse="Place de la Mairie", ville="Castres",
        code_postal="81100", latitude=lat, longitude=lon)
    CreneauLivraison.objects.create(
        exploitant=e, point_livraison=pt, jour=3,
        heure_debut=datetime.time(10, 0), heure_fin=datetime.time(12, 0),
        frequence=CreneauLivraison.Frequence.HEBDO)
    v, _ = ParametresVitrine.objects.get_or_create(exploitant=e)
    v.modules = {"carte": True}
    v.save()

# ------------------------------------------------- 1. vitrines publiques
c = Client()
for login, activite, nom_espace, *_ in SEEDS:
    r = c.get(f"/exploitant/{login}/")
    html = r.content.decode()
    check(f"[{login}] vitrine 200", r.status_code == 200, r.status_code)
    check(f"[{login}] carte du moment", "Carte du moment" in html)
    check(f"[{login}] bloc Nous trouver", "vitrine-points-geo" in html)
    check(f"[{login}] créneau bandeau", "Point principal" in html)

# --------------------------- 2. commande + e-mail de confirmation (M2)
r = c.get("/commander/ferme/")
cle = re.search(r'name="((?:qty_|carte_)[^"]+)"',
                r.content.decode()).group(1)
mail.outbox = []
r = c.post("/commander/ferme/", {
    cle: "2", "nom_client": "Camille Client",
    "email_client": "camille@example.fr",
    "telephone_client": "0612345678",
    "date_livraison": str(timezone.localdate() + datetime.timedelta(days=3)),
    "point_livraison": str(PointLivraison.objects.get(
        exploitant__slug="ferme").pk)})
check("commande créée", Panier.objects.count() == 0
      and __import__("portal.models", fromlist=["Commande"]).Commande
      .objects.exists(), r.status_code)
check("e-mail de confirmation parti", len(mail.outbox) == 1,
      len(mail.outbox))
if mail.outbox:
    check("confirmation : récap produit", "Article" in mail.outbox[0].body)
    check("confirmation : total", "6.00" in mail.outbox[0].body)

# ----------------------------------- 3. panier « prêt » + notification
from portal.models import Commande  # noqa: E402

e_ferme = Exploitant.objects.get(slug="ferme")
prod = Produit.objects.filter(exploitant=e_ferme).first()
panier = Panier.objects.create(
    exploitant=e_ferme, nom_client="Camille Client",
    email_client="camille@example.fr", telephone_client="0612345678",
    numero=Panier.prochain_numero(e_ferme, timezone.localdate()),
    date_livraison=timezone.localdate(), statut=Panier.Statut.PREPARATION,
    total=Decimal("6.00"))
from portal.models import LignePanier  # noqa: E402

LignePanier.objects.create(panier=panier, produit=prod,
                           quantite=Decimal("2"),
                           prix_unitaire=Decimal("3.00"))
c_pro = Client()
c_pro.login(username="ferme", password="pw12345!")
mail.outbox = []
r = c_pro.post(f"/espace-paniers/{panier.pk}/", {
    "action": "statut", "statut": "PRET"})
panier.refresh_from_db()
check("panier passé en prêt", panier.statut == Panier.Statut.PRET,
      panier.statut)
check("notification e-mail au client", len(mail.outbox) == 1,
      len(mail.outbox))
if mail.outbox:
    check("notification : adresse du client",
          mail.outbox[0].to == ["camille@example.fr"], mail.outbox[0].to)
    check("notification : contenu panier",
          "panier" in mail.outbox[0].subject.lower()
          or "panier" in mail.outbox[0].body.lower(),
          mail.outbox[0].subject)

# --------------------------------------------- 4. page de recherche (L4)
r = c.get("/recherche/")
html = r.content.decode()
check("recherche 200", r.status_code == 200, r.status_code)
check("clustering câblé (CDN)", "leaflet.markercluster" in html)
m = re.search(r'<script[^>]*id="donnees-carte"[^>]*>(.*?)</script>',
              html, re.S)
check("données de la carte présentes", m is not None)
if m:
    import json  # noqa: E402

    donnees = json.loads(m.group(1))
    localises = [d for d in donnees if d.get("latitude") is not None]
    check("marqueurs géolocalisés", len(localises) >= 1, len(localises))

# ------------------------------------------------------- échec SMTP doux
from portal import views  # noqa: E402


class MailCasse:
    def __init__(self, *a, **k):
        pass

    def send(self):
        raise RuntimeError("SMTP down")


mail_orig = views.django.core.mail.EmailMessage
views.django.core.mail.EmailMessage = MailCasse
mail.outbox = []
r = c.post("/commander/ferme/", {
    cle: "1", "nom_client": "Client Sans SMTP",
    "email_client": "sans-smtp@example.fr",
    "telephone_client": "0611223344",
    "date_livraison": str(timezone.localdate() + datetime.timedelta(days=4)),
    "point_livraison": str(PointLivraison.objects.get(
        exploitant__slug="ferme").pk)})
views.django.core.mail.EmailMessage = mail_orig
check("échec SMTP : commande créée quand même",
      Commande.objects.count() == 2, Commande.objects.count())

# ---------------------------------------------------------------- bilan
print("== RÉUSSITES ==")
for x in OK:
    print(" OK", x)
print("== ÉCHECS ==")
for x in KO:
    print(" KO", x)
if os.path.exists(BASE):
    os.remove(BASE)
sys.exit(1 if KO else 0)
