/* Carte de localisation (Leaflet) — utilisée sur la fiche
   exploitation (latitude/longitude), l'inscription pro et les points
   de livraison.
   - Un élément avec data-pick-map devient une carte : le clic, le
     déplacement du marqueur ou les contrôles sur la carte renseignent
     les champs inputs pointés par data-lat-input / data-lon-input.
   - Champs d'adresse optionnels (data-adresse-input, data-ville-input,
     data-cp-input, data-dept-input) : géocodage inverse bidirectionnel —
     le marqueur déplacé met à jour adresse / ville / code postal /
     département, et une adresse saisie (validation d'un champ)
     repositionne le marqueur et recalcule lat/long.
   - Contrôles intégrés à la carte, comme sur la page Trouver :
     contrôleur de couches (Plan / Ortho, superpositions Régions et
     Départements), bouton 🎯 de géolocalisation et boite 🔎 de
     recherche intelligente (commune, adresse, département, pays) avec
     suggestions en menu déroulant — une région ou un pays zoome
     dessus sans bouger le marqueur, une adresse y place le marqueur
     et remplit les champs du formulaire.
   - Un bouton avec data-geocoder interroge Nominatim (OSM) à partir
     des champs adresse / code postal / ville, et positionne le
     marqueur (les champs lat/lon sont mis à jour automatiquement). */
(function () {
  "use strict";

/* Échappement HTML : toute valeur issue des données (noms, villes,
   URL, horaires) est neutralisée avant insertion dans un popup ou une
   info-bulle — XSS stockée impossible (audit sécurité, lot 1). */
function esc(t) {
  return String(t == null ? "" : t)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

  var FOND_IGN = "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile" +
    "&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal" +
    "&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}";
  var FOND_ORTHO = "https://server.arcgisonline.com/ArcGIS/rest/services" +
    "/World_Imagery/MapServer/tile/{z}/{y}/{x}";
  var FOND_ADMIN = "https://raw.githubusercontent.com/gregoiredavid" +
    "/france-geojson/master/";

  function valeur(id) {
    var el = document.getElementById(id);
    return el ? (el.value || "").trim() : "";
  }

  function nombre(valeur) {
    var n = parseFloat(valeur);
    return isNaN(n) ? null : n;
  }

  function champ(carteEl, cle) {
    var id = carteEl.dataset[cle];
    return id ? document.getElementById(id) : null;
  }

  /* Répartir les éléments d'une adresse géocodée dans les champs du
     formulaire (extraction : numéro+voie → adresse, commune → ville,
     code postal, département déduit des deux premiers chiffres). */
  function remplirDepuisAdresse(champs, a) {
    function mettre(el, val) { if (el && val) { el.value = val; } }
    mettre(champs.adresse,
           [a.house_number, a.road].filter(Boolean).join(" "));
    mettre(champs.ville,
           a.city || a.town || a.village || a.municipality || "");
    mettre(champs.cp, a.postcode || "");
    mettre(champs.dept, (a.postcode || "").slice(0, 2));
  }

  /* ---- Superpositions administratives (Régions, Départements) ----
     Même source que la page Trouver : chargées à la demande, au
     premier affichage seulement. Les étiquettes des départements
     apparaissent au-delà du zoom 8 (classe labels-dep-on). */
  function initCouchesAdmin(carte) {
    var CONF = {
      "Régions": { url: FOND_ADMIN + "regions.geojson",
                   style: { color: "#8e24aa", weight: 2,
                            fill: false, opacity: 0.9 } },
      "Départements": { url: FOND_ADMIN + "departements.geojson",
                        style: { color: "#1565c0", weight: 1.5,
                                 fill: false, opacity: 0.8 },
                        etiquette: "dep" }
    };
    var groupes = {};
    Object.keys(CONF).forEach(function (nom) {
      groupes[nom] = L.layerGroup();
    });
    function majLabels() {
      var actif = carte.hasLayer(groupes["Départements"])
        && carte.getZoom() >= 8;
      carte.getContainer().classList.toggle("labels-dep-on", actif);
    }
    carte.on("overlayadd", function (e) {
      var conf = CONF[e.name];
      if (!conf || conf.chargee) { majLabels(); return; }
      conf.chargee = true;
      fetch(conf.url).then(function (r) { return r.json(); })
        .then(function (data) {
          var geo = L.geoJSON(data, {
            style: conf.style,
            onEachFeature: function (feature, couche) {
              var props = feature.properties || {};
              var nom = props.nom || props.NOM || props.code || "";
              if (nom) {
                couche.bindPopup("<strong>" + esc(nom) + "</strong>");
              }
              if (conf.etiquette) {
                var etiquette = nom;
                if (conf.etiquette === "dep") {
                  var code = props.code || props.CODE || "";
                  etiquette = (code ? code + " — " : "") + nom;
                }
                couche.bindTooltip(esc(etiquette), {
                  permanent: true, direction: "center",
                  className: "label-admin label-" + conf.etiquette
                });
              }
            }
          });
          groupes[e.name].addLayer(geo);
          majLabels();
        }).catch(function () { conf.chargee = false; });
    });
    carte.on("zoomend overlayremove", majLabels);
    return groupes;
  }

  /* ---- Boite de recherche intelligente (menu déroulant) ---- */
  function initRecherche(carte, carteEl, appliquer, champs, aDesChamps) {
    var conteneur = null;
    var PRECIS = ["place", "building", "amenity", "shop",
                  "office", "tourism", "leisure"];
    var ctrl = L.control({ position: "topleft" });
    ctrl.onAdd = function () {
      var div = L.DomUtil.create("div",
        "leaflet-bar leaflet-control ctrl-recherche");
      var boite = L.DomUtil.create("div", "recherche-boite", div);
      var input = L.DomUtil.create("input", "recherche-input", boite);
      var liste = L.DomUtil.create("ul", "recherche-liste", boite);
      input.type = "search";
      input.placeholder = "🔎 Commune, adresse, département, pays…";
      input.setAttribute("aria-label",
        "Rechercher un lieu : la carte zoome dessus, une adresse y place le marqueur");
      liste.hidden = true;
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);

      var minuteur = null, sequence = 0;
      function cacher() { liste.hidden = true; liste.innerHTML = ""; }
      function chercher(q, cb) {
        var n = ++sequence;
        fetch("https://nominatim.openstreetmap.org/search" +
              "?format=json&limit=6&addressdetails=1&q=" +
              encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (res) { if (n === sequence) { cb(res || []); } })
          .catch(function () { if (n === sequence) { cb([]); } });
      }
      function choisir(res) {
        cacher();
        var libelle = res.display_name || "";
        if (libelle) { input.value = libelle.split(",")[0]; }
        var lat = parseFloat(res.lat), lon = parseFloat(res.lon);
        if (isNaN(lat) || isNaN(lon)) { return; }
        var bornes = null;
        if (res.boundingbox && res.boundingbox.length === 4) {
          bornes = L.latLngBounds(
            [[+res.boundingbox[0], +res.boundingbox[2]],
             [+res.boundingbox[1], +res.boundingbox[3]]]);
        }
        var precis = res.category &&
          PRECIS.indexOf(res.category) >= 0;
        if (precis) {
          /* Lieu précis (adresse, commune…) : le marqueur y va et
             les champs du formulaire sont remplis par extraction. */
          appliquer(lat, lon, true);
          if (bornes) { carte.fitBounds(bornes, { maxZoom: 16 }); }
          else { carte.setView([lat, lon], 16); }
          if (aDesChamps && res.address) {
            remplirDepuisAdresse(champs, res.address);
          }
        } else {
          /* Région, département, pays : zoom de navigation seule,
             le marqueur (position de l'exploitation) ne bouge pas. */
          if (bornes) { carte.fitBounds(bornes, { padding: [20, 20] }); }
          else { carte.setView([lat, lon], 10); }
        }
      }
      function suggestions(res) {
        liste.innerHTML = "";
        res.forEach(function (r) {
          var li = document.createElement("li");
          li.textContent = r.display_name || "";
          li.addEventListener("click", function () { choisir(r); });
          liste.appendChild(li);
        });
        liste.hidden = !res.length;
      }
      input.addEventListener("input", function () {
        var q = input.value.trim();
        clearTimeout(minuteur);
        if (q.length < 3) { cacher(); return; }
        minuteur = setTimeout(function () { chercher(q, suggestions); }, 350);
      });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { cacher(); input.blur(); return; }
        if (e.key !== "Enter") { return; }
        e.preventDefault();
        var q = input.value.trim();
        if (!q) { return; }
        clearTimeout(minuteur);
        var premier = !liste.hidden && liste.querySelector("li");
        if (premier) { premier.click(); }
        else { chercher(q, function (res) {
          if (res.length) { choisir(res[0]); } else { cacher(); }
        }); }
      });
      document.addEventListener("click", function (e) {
        if (!boite.contains(e.target)) { cacher(); }
      });
      conteneur = div;
      return div;
    };
    ctrl.addTo(carte);
    /* En tête de colonne : la boîte passe AU-DESSUS des boutons de
       zoom et du contrôle de couches. */
    var coin = carte.getContainer().querySelector(
      ".leaflet-top.leaflet-left");
    if (coin && conteneur && conteneur.parentNode === coin) {
      coin.insertBefore(conteneur, coin.firstChild);
    }
  }

  function initCarte(carteEl) {
    /* Leaflet absent (CDN unpkg injoignable, bloqueur de publicité,
       hors-ligne) : message visible dans le cadre au lieu d'une
       carte muette — l'utilisateur sait pourquoi rien ne répond. */
    if (typeof L === "undefined") {
      carteEl.innerHTML = '<p class="muted" style="padding:1rem;margin:0">' +
        "⚠️ Carte indisponible : la bibliothèque Leaflet (unpkg.com) " +
        "n'a pas pu être chargée — connexion, bloqueur de publicité ? " +
        "Rechargez la page ou saisissez directement votre adresse " +
        "ci-dessous.</p>";
      console.error("pick-map : Leaflet (unpkg) n'est pas chargé.");
      return;
    }
    var latIn = document.getElementById(carteEl.dataset.latInput);
    var lonIn = document.getElementById(carteEl.dataset.lonInput);
    if (!latIn || !lonIn) return;

    var lat = nombre(latIn.value), lon = nombre(lonIn.value);
    var position = (lat !== null && lon !== null)
      ? [lat, lon] : [46.6, 2.4];
    var zoomInitial = (lat !== null && lon !== null) ? 15 : 6;

    var carte = L.map(carteEl.id).setView(position, zoomInitial);
    var fondPlan = L.tileLayer(FOND_IGN, {
      maxZoom: 19,
      attribution: "Plan IGN V2 &copy; <a href=\"https://www.geoportail.gouv.fr/\">IGN</a>"
    }).addTo(carte);
    var fondOrtho = L.tileLayer(FOND_ORTHO, {
      maxZoom: 19,
      attribution: "Esri, Maxar, Earthstar Geographics"
    });

    var marqueur = L.marker(position, { draggable: true }).addTo(carte);
    if (lat === null || lon === null) marqueur.setOpacity(0.55);

    /* Points existants (page « Points & créneaux ») : affichés avec
       leur symbole propre (📍 livraison, 🏪 boutique, 🎪 marché) et
       cadrage automatique sur leur emprise — voir #points-carte. */
    var blocPoints = document.getElementById("points-carte");
    if (blocPoints) {
      var symboles = { "LIVRAISON": "📍", "BOUTIQUE": "🏪",
                       "MARCHE": "🎪" };
      try {
        var existants = JSON.parse(blocPoints.textContent) || [];
        var bornes = [];
        existants.forEach(function (p) {
          if (p.latitude === null || p.longitude === null) return;
          bornes.push([p.latitude, p.longitude]);
          L.marker([p.latitude, p.longitude], {
            icon: L.divIcon({
              className: "marker-exploitant",
              html: '<span class="marker-activite">' +
                    (symboles[p.type] || "📍") + "</span>",
              iconSize: [22, 22], iconAnchor: [11, 11]
            })
          }).bindPopup("<strong>" + esc(p.nom) + "</strong>")
            .bindTooltip(esc(p.nom), { direction: "top" })
            .addTo(carte);
        });
        if (bornes.length) {
          carte.fitBounds(bornes, { padding: [40, 40], maxZoom: 14 });
          marqueur.setOpacity(0.85);
        }
      } catch (e) { /* bloc JSON absent ou invalide : carte normale */ }
    }

    /* Champs d'adresse liés (optionnels) : géocodage inverse
       bidirectionnel. */
    var champs = {
      adresse: champ(carteEl, "adresseInput"),
      ville: champ(carteEl, "villeInput"),
      cp: champ(carteEl, "cpInput"),
      dept: champ(carteEl, "deptInput")
    };
    var aDesChamps = !!(champs.adresse || champs.ville ||
                        champs.cp || champs.dept);

    function geocodageInverse(lat, lon) {
      if (!aDesChamps) return;
      fetch("https://nominatim.openstreetmap.org/reverse?format=json" +
            "&countrycodes=fr&lat=" + lat + "&lon=" + lon)
        .then(function (r) { return r.json(); })
        .then(function (res) {
          remplirDepuisAdresse(champs, (res && res.address) || {});
        })
        .catch(function () { /* géocodage inverse indisponible :
                                lat/lon sont déjà positionnés */ });
    }

    function appliquer(lat, lon, silencieux) {
      latIn.value = lat.toFixed(6);
      lonIn.value = lon.toFixed(6);
      marqueur.setLatLng([lat, lon]);
      marqueur.setOpacity(1);
      if (!silencieux) carte.panTo([lat, lon]);
    }

    carte.on("click", function (e) {
      appliquer(e.latlng.lat, e.latlng.lng);
      geocodageInverse(e.latlng.lat, e.latlng.lng);
    });
    marqueur.on("dragend", function () {
      var p = marqueur.getLatLng();
      appliquer(p.lat, p.lng);
      geocodageInverse(p.lat, p.lng);
    });
    latIn.addEventListener("change", function () {
      var a = nombre(latIn.value), o = nombre(lonIn.value);
      if (a !== null && o !== null) appliquer(a, o);
    });
    lonIn.addEventListener("change", function () {
      var a = nombre(latIn.value), o = nombre(lonIn.value);
      if (a !== null && o !== null) appliquer(a, o);
    });

    /* Contrôleur de couches (Plan / Ortho + Régions / Départements). */
    L.control.layers(
      { "Plan": fondPlan, "Ortho (vue aérienne)": fondOrtho },
      initCouchesAdmin(carte),
      { position: "topleft" }
    ).addTo(carte);

    /* 🎯 Géolocalisation sur la carte : positionne le marqueur et
       complète les champs d'adresse par géocodage inverse. */
    var geoloc = L.control({ position: "topright" });
    geoloc.onAdd = function () {
      var div = L.DomUtil.create("div",
        "leaflet-bar leaflet-control ctrl-geoloc");
      var btn = L.DomUtil.create("button", "btn-geoloc-cible", div);
      btn.type = "button";
      btn.textContent = "🎯";
      btn.title = "Me géolocaliser : positionne le marqueur";
      btn.setAttribute("aria-label", btn.title);
      L.DomEvent.disableClickPropagation(div);
      btn.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Géolocalisation non supportée par ce navigateur.");
          return;
        }
        navigator.geolocation.getCurrentPosition(function (pos) {
          appliquer(pos.coords.latitude, pos.coords.longitude);
          carte.setView([pos.coords.latitude, pos.coords.longitude], 15);
          geocodageInverse(pos.coords.latitude, pos.coords.longitude);
        }, function () { alert("Position refusée ou indisponible."); },
           { timeout: 10000 });
      });
      return div;
    };
    geoloc.addTo(carte);

    /* 🔎 Recherche intelligente (suggestions, zoom, extraction). */
    initRecherche(carte, carteEl, appliquer, champs, aDesChamps);

    /* Validation d'une adresse saisie dans le formulaire : le
       marqueur se repositionne et lat/long sont recalculées (comme
       si le marqueur avait été déplacé à la main). */
    if (aDesChamps) {
      [champs.adresse, champs.cp, champs.ville].forEach(function (el) {
        if (!el) return;
        el.addEventListener("change", function () {
          var q = [valeur(carteEl.dataset.adresseInput),
                   valeur(carteEl.dataset.cpInput),
                   valeur(carteEl.dataset.villeInput)]
            .filter(Boolean).join(", ");
          if (!q) return;
          fetch("https://nominatim.openstreetmap.org/search" +
                "?format=json&limit=1&countrycodes=fr&q=" +
                encodeURIComponent(q))
            .then(function (r) { return r.json(); })
            .then(function (res) {
              if (!res.length) return;
              var a = parseFloat(res[0].lat),
                  o = parseFloat(res[0].lon);
              appliquer(a, o);
              carte.setView([a, o], 16);
            })
            .catch(function () { /* géocodage indisponible : la
                                    carte reste le recours */ });
        });
      });
    }

    carteEl._pickMap = { carte: carte, marqueur: marqueur,
                         appliquer: appliquer };
  }

  function initGeocodage(bouton) {
    bouton.addEventListener("click", function () {
      var adresse = valeur(bouton.dataset.adresse);
      var cp = valeur(bouton.dataset.cp);
      var ville = valeur(bouton.dataset.ville);
      var requete = [adresse, cp, ville].filter(Boolean).join(", ");
      if (!requete) {
        alert("Renseignez d'abord l'adresse (ou ville / code postal).");
        return;
      }
      bouton.disabled = true;
      bouton.textContent = "⏳ Recherche…";
      fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1" +
            "&countrycodes=fr&addressdetails=0&q=" +
            encodeURIComponent(requete))
        .then(function (r) { return r.json(); })
        .then(function (res) {
          bouton.disabled = false;
          bouton.textContent = bouton.dataset.libelle || "📍 Localiser";
          if (!res.length) {
            alert("Adresse introuvable : précisez ou cliquez directement sur la carte.");
            return;
          }
          var lat = parseFloat(res[0].lat), lon = parseFloat(res[0].lon);
          var carteEl = bouton.dataset.carte
            ? document.getElementById(bouton.dataset.carte) : null;
          if (carteEl && carteEl._pickMap) {
            carteEl._pickMap.appliquer(lat, lon);
            carteEl._pickMap.carte.setView([lat, lon], 17);
          } else {
            var latIn = document.getElementById(bouton.dataset.lat);
            var lonIn = document.getElementById(bouton.dataset.lon);
            if (latIn) latIn.value = lat.toFixed(6);
            if (lonIn) lonIn.value = lon.toFixed(6);
            // data-submit : envoyer le formulaire parent juste après
            // le géocodage (ex : enregistrer la position d'un point)
            if (bouton.dataset.submit && bouton.closest("form")) {
              bouton.closest("form").submit();
            }
          }
        })
        .catch(function () {
          bouton.disabled = false;
          bouton.textContent = bouton.dataset.libelle || "📍 Localiser";
          alert("Géocodage indisponible : cliquez directement sur la carte.");
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-pick-map]").forEach(initCarte);
    document.querySelectorAll("[data-geocoder]").forEach(initGeocodage);
  });
})();
