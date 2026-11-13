/* Cartographie complète des points (page « Points & créneaux ») :
   - Tous les points localisés s'affichent avec leur symbole
     (📍 livraison, 🏪 boutique, 🎪 marché, 🚚 emplacement foodtruck)
     et un popup détaillé (type, adresse, précisions, créneaux).
   - ✏️ Mode édition : les marqueurs deviennent déplaçables ; le
     déplacement enregistre la nouvelle position (action point_geo)
     et recharge la page.
   - ➕ Nouveau point : mode création — un clic sur la carte place un
     marqueur, remplit latitude/longitude, déduit l'adresse par
     géocodage inverse (Nominatim) et ouvre le formulaire minimal. */
(function () {
  "use strict";

  /* Échappement HTML : toute valeur issue des données est neutralisée
     avant insertion dans un popup (XSS stockée impossible). */
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
  var SYMBOLES = { "LIVRAISON": "📍", "BOUTIQUE": "🏪", "MARCHE": "🎪",
                   "EMPLACEMENT": "🚚" };

  document.addEventListener("DOMContentLoaded", function () {
    var carteEl = document.getElementById("carte-points");
    var bloc = document.getElementById("points-carte");
    if (!carteEl || !bloc || typeof L === "undefined") { return; }
    var points = [];
    try { points = JSON.parse(bloc.textContent) || []; }
    catch (e) { points = []; }

    var carte = L.map(carteEl.id).setView([46.6, 2.4], 6);
    var fondPlan = L.tileLayer(FOND_IGN, {
      maxZoom: 19,
      attribution: "Plan IGN V2 &copy; <a href=\"https://www.geoportail.gouv.fr/\">IGN</a>"
    }).addTo(carte);
    var fondOrtho = L.tileLayer(FOND_ORTHO, {
      maxZoom: 19,
      attribution: "Esri, Maxar, Earthstar Geographics"
    });
    L.control.layers(
      { "Plan": fondPlan, "Ortho (vue aérienne)": fondOrtho },
      null, { position: "topleft" }).addTo(carte);

    /* ---- Marqueurs des points existants ---- */
    var marqueurs = [];
    points.forEach(function (p) {
      if (p.latitude === null || p.longitude === null) { return; }
      var m = L.marker([p.latitude, p.longitude], {
        draggable: false,
        icon: L.divIcon({
          className: "marker-exploitant",
          html: '<span class="marker-activite">' +
                (SYMBOLES[p.type] || "📍") + "</span>",
          iconSize: [22, 22], iconAnchor: [11, 11]
        })
      }).addTo(carte);
      var popup = "<strong>" + esc(p.nom) + "</strong><br>" +
        esc(p.type_libelle || "") + "<br>" +
        esc([p.adresse, p.code_postal, p.ville].filter(Boolean).join(", "));
      if (p.note) { popup += "<br><em>" + esc(p.note) + "</em>"; }
      (p.creneaux || []).forEach(function (c) {
        popup += "<br>🗓 " + esc(c);
      });
      m.bindPopup(popup).bindTooltip(esc(p.nom), { direction: "top" });
      m.on("dragend", function () {
        var ll = m.getLatLng();
        var f = document.getElementById("form-deplacer-point");
        if (!f) { return; }
        f.elements["pk"].value = p.pk;
        f.elements["latitude"].value = ll.lat.toFixed(6);
        f.elements["longitude"].value = ll.lng.toFixed(6);
        f.submit();
      });
      marqueurs.push({ pk: p.pk, marqueur: m });
    });
    if (marqueurs.length) {
      carte.fitBounds(
        L.featureGroup(marqueurs.map(function (x) { return x.marqueur; }))
          .getBounds(), { padding: [40, 40], maxZoom: 14 });
    }

    /* ---- Contrôles ✏️ Mode édition et ➕ Nouveau point ---- */
    var barre = L.control({ position: "topright" });
    barre.onAdd = function () {
      var div = L.DomUtil.create("div",
        "leaflet-bar leaflet-control ctrl-points");
      var btnEdit = L.DomUtil.create("button", "btn-points-edition", div);
      btnEdit.type = "button";
      btnEdit.innerHTML = "✏️ <span>Édition : non</span>";
      btnEdit.title = "Mode édition : déplacez un marqueur pour corriger sa position (enregistrée immédiatement)";
      var btnNew = L.DomUtil.create("button", "btn-points-nouveau", div);
      btnNew.type = "button";
      btnNew.innerHTML = "➕ <span>Nouveau point</span>";
      btnNew.title = "Créer un point : cliquez ensuite l'endroit sur la carte";
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      return div;
    };
    barre.addTo(carte);
    var btnEdit = carteEl.parentNode.querySelector(".btn-points-edition")
      || document.querySelector(".btn-points-edition");
    var btnNew = document.querySelector(".btn-points-nouveau");

    /* Mode édition : marqueurs déplaçables, enregistrement au lâcher. */
    var enEdition = false;
    if (btnEdit) {
      btnEdit.addEventListener("click", function () {
        enEdition = !enEdition;
        btnEdit.classList.toggle("actif", enEdition);
        btnEdit.querySelector("span").textContent =
          enEdition ? "Édition : actif" : "Édition : non";
        carteEl.classList.toggle("points-en-edition", enEdition);
        marqueurs.forEach(function (x) {
          if (enEdition) { x.marqueur.dragging.enable(); }
          else { x.marqueur.dragging.disable(); }
        });
      });
    }

    /* Mode création : clic sur la carte → marqueur provisoire +
       formulaire minimal ouvert, adresse déduite (géocodage inverse). */
    var enCreation = false;
    var provisoire = null;
    var detailsCreation = document.getElementById("creation-point");
    var posInfo = document.getElementById("creation-point-position");
    var latIn = document.getElementById("id_latitude");
    var lonIn = document.getElementById("id_longitude");

    function remplirAdresse(lat, lon) {
      fetch("https://nominatim.openstreetmap.org/reverse?format=json" +
            "&countrycodes=fr&lat=" + lat + "&lon=" + lon)
        .then(function (r) { return r.json(); })
        .then(function (res) {
          var a = (res && res.address) || {};
          var adresse = [a.house_number, a.road].filter(Boolean).join(" ");
          var ville = a.city || a.town || a.village || a.municipality || "";
          var cp = a.postcode || "";
          var el;
          if (adresse) { el = document.getElementById("id_adresse"); if (el) { el.value = adresse; } }
          if (ville) { el = document.getElementById("id_ville"); if (el) { el.value = ville; } }
          if (cp) { el = document.getElementById("id_code_postal"); if (el) { el.value = cp; } }
          if (posInfo) {
            posInfo.textContent = "Emplacement choisi : " +
              [adresse, cp, ville].filter(Boolean).join(", ") +
              " (" + lat.toFixed(5) + ", " + lon.toFixed(5) + "). " +
              "Complétez le nom puis créez le point.";
          }
        })
        .catch(function () { /* géocodage indisponible : lat/lon
                                suffisent, les champs restent libres */ });
    }

    function placerProvisoire(lat, lon) {
      if (latIn) { latIn.value = lat.toFixed(6); }
      if (lonIn) { lonIn.value = lon.toFixed(6); }
      if (!provisoire) {
        provisoire = L.marker([lat, lon], {
          draggable: true, opacity: 0.85,
          icon: L.divIcon({
            className: "marker-exploitant marker-provisoire",
            html: '<span class="marker-activite">➕</span>',
            iconSize: [22, 22], iconAnchor: [11, 11]
          })
        }).addTo(carte);
        provisoire.on("dragend", function () {
          var ll = provisoire.getLatLng();
          placerProvisoire(ll.lat, ll.lng);
        });
      } else {
        provisoire.setLatLng([lat, lon]);
      }
      if (posInfo) {
        posInfo.textContent = "Emplacement choisi (" + lat.toFixed(5) +
          ", " + lon.toFixed(5) + ") — adresse en cours de déduction…";
      }
      remplirAdresse(lat, lon);
    }

    function basculerCreation(force) {
      enCreation = (force !== undefined) ? force : !enCreation;
      if (btnNew) { btnNew.classList.toggle("actif", enCreation); }
      carteEl.classList.toggle("points-en-creation", enCreation);
      if (enCreation) {
        if (detailsCreation) {
          detailsCreation.hidden = false;
          detailsCreation.open = true;
        }
        if (posInfo) {
          posInfo.textContent = "Cliquez sur la carte pour choisir " +
            "l'emplacement du nouveau point (ou déplacez le marqueur ➕).";
        }
      } else if (provisoire) {
        carte.removeLayer(provisoire);
        provisoire = null;
        if (detailsCreation) { detailsCreation.hidden = true; }
      }
    }

    if (btnNew) {
      btnNew.addEventListener("click", function () { basculerCreation(); });
    }
    carte.on("click", function (e) {
      if (!enCreation) { return; }
      placerProvisoire(e.latlng.lat, e.latlng.lng);
      if (detailsCreation && !detailsCreation.open) {
        detailsCreation.open = true;
        detailsCreation.scrollIntoView(
          { behavior: "smooth", block: "nearest" });
      }
    });
  });
})();
