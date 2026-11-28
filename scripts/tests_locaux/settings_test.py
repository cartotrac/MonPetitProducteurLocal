"""Réglages Django pour les tests à froid (scripts/tests_locaux).

Ne s'utilise jamais en production : la base est un fichier sqlite jetable
créé à côté du script, effacé puis reconstruit à chaque exécution.

Le module s'appuie sur config.settings (mêmes applications, mêmes
middlewares) en remplaçant uniquement la base, le backend e-mail (en
mémoire : les e-mails partent dans django.core.mail.outbox) et les
réglages de sécurité. DJANGO_DEBUG=1 est requis au chargement de
config.settings (sinon SECRET_KEY obligatoire) : le runner le fixe.
"""
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

from config.settings import *  # noqa: F401,F403

if "google" in SOCIALACCOUNT_PROVIDERS:  # noqa: F405
    SOCIALACCOUNT_PROVIDERS.pop("google")  # noqa: F405

SILENCED_SYSTEM_CHECKS = ["fields.E210"]
DEBUG = True
SECRET_KEY = "tests-locaux"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ALLOWED_HOSTS = ["*"]
# E-mails capturés en mémoire : vérifiables par le script, rien ne part.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "base_test.sqlite3"),
    }
}
