"""Stockage statique avec manifeste (cache-busting auto).

En production (DEBUG=0), collectstatic genere des fichiers hashes
(append.min.a1b2c3.css) et un manifeste staticfiles/staticfiles.json :
les templates {% static %} pointent automatiquement vers le hash, donc
plus besoin de bump manuel ?v=XX. manifest_strict = False : une entree
absente du manifeste retombe sur l'URL non hashee au lieu de lever une
erreur 500.
"""

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ManifestPermissif(ManifestStaticFilesStorage):
    manifest_strict = False
