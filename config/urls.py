from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from portal import auth_views as portal_auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Connexion par nom d'utilisateur OU e-mail (avant l'include, qui
    # définit aussi "login/" : la première route gagnante est la nôtre).
    path("comptes/login/", portal_auth_views.connexion, name="login"),
    path("comptes/", include("django.contrib.auth.urls")),  # logout, password...
    # « Continuer avec Google » : flux OAuth allauth (google/login/,
    # google/login/callback/…). Placé APRÈS nos routes : la connexion
    # classique /comptes/login/ reste la nôtre.
    path("comptes/", include("allauth.urls")),
    path("", include("portal.urls")),
]

# Fichiers statiques (CSS…) et médias (logos, photos), servis par Django
# y compris en production (DEBUG=0). NB : le helper django.conf.urls.static
# ne génère des routes QUE si DEBUG=True — on ne l'utilise donc pas.
# Requis : « manage.py collectstatic --noinput » après chaque modification
# de fichiers statiques. Les « chemins statiques » du panneau AlwaysData
# peuvent court-circuité ces routes (Apache sert alors directement) : c'est
# le comportement souhaité, plus performant.
urlpatterns += [
    re_path(r"^static/(?P<path>.*)$", static_serve,
            {"document_root": settings.STATIC_ROOT}),
    re_path(r"^media/(?P<path>.*)$", static_serve,
            {"document_root": settings.MEDIA_ROOT}),
]

admin.site.site_header = "MonPetitMaraicher — Administration"
admin.site.site_title = "MonPetitMaraicher"
admin.site.index_title = "Back-office du portail"
