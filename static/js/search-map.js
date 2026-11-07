/* Carte Leaflet de la page de recherche : affiche les RESULTATS FILTRES.
   Les données viennent du bloc json_script "donnees-carte" du template.

   Fonds de carte (sans cle, conformes aux conditions d'utilisation — les
   tuiles OpenStreetMap directes renvoient 403 aux serveurs benevoles) :
   - Plan    : CARTO Voyager (basemap CARTO/OSM)
   - Ortho   : Esri World Imagery (photographies aeriennes)

   Superpositions administratives (chargees a la demande, au premier
   affichage uniquement) :
   - Regions, Departements : france-geojson (gregoiredavid)
   Les departements (numero + nom) portent une etiquette permanente,
   revelee au-dela d'un seuil de zoom.
*/

var CAT_STYLES = {
  AB:       { color: "#1b5e20", label: "Agriculture Biologique (AB)" },
  PERMA:    { color: "#6a1b9a", label: "Permaculture" },
  PAYSAN:   { color: "#f9a825", label: "Agriculture paysanne" },
  RAISONNE: { color: "#0277bd", label: "Agriculture raisonnée" },
  CONV:     { color: "#546e7a", label: "Conventionnelle" }
};

var bloc = document.getElementById("donnees-carte");
var carte = L.map("carte-recherche").setView([46.6, 2.4], 6);

/* ------------------------------------------------------------------ fonds */
/* Fond « Plan » : Plan IGN V2 (Géoplateforme IGN, données ouvertes, WMTS
   SANS clé — plus fiable que les tuiles OSM directes qui renvoient 403).
   Même source que le Géoportail : data.geopf.fr. */
var fondPlan = L.tileLayer(
  "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0" +
  "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png" +
  "&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}", {
    maxZoom: 19,
    attribution: "Plan IGN V2 &copy; <a href=\"https://www.geoportail.gouv.fr/\">IGN</a>"
  });

var fondOrtho = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    attribution: "Esri, Maxar, Earthstar Geographics"
  });

fondPlan.addTo(carte);

/* ------------------------------------------- superpositions administratives */
var FOND_ADMIN = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/";

var COUCHES_ADMIN = {
  "Régions": {
    url: FOND_ADMIN + "regions.geojson",
    style: { color: "#8e24aa", weight: 2, fill: false, opacity: 0.9 }
  },
  "Départements": {
    url: FOND_ADMIN + "departements.geojson",
    style: { color: "#1565c0", weight: 1.5, fill: false, opacity: 0.8 },
    etiquette: "dep"      // numéro + nom affichés au-delà du zoom label
  }
};

/* Zoom minimum à partir duquel chaque couche administrative devient
   disponible : en dessous, elle est grisée dans le contrôle et son
   chargement est refusé. (La couche Communes a été retirée : trop
   lourde, et le fond Plan IGN suffit à identifier les communes.) */
var SEUILS = { "Régions": 0, "Départements": 6 };
/* Zoom minimum pour afficher les étiquettes (noms) des couches actives */
var SEUILS_LABELS = { "dep": 8 };

var couchesAdmin = {};
Object.keys(COUCHES_ADMIN).forEach(function (nom) {
  couchesAdmin[nom] = L.layerGroup();
});

// Un seul contrôle de couches : fonds (plan/ortho) + superpositions
L.control.layers(
  { "Plan": fondPlan, "Ortho (vue aérienne)": fondOrtho },
  couchesAdmin,
  { position: "topleft" }
).addTo(carte);

// Disponibilité d'une couche selon le zoom courant
function coucheDisponible(nom) {
  var seuil = SEUILS[nom] || 0;
  return carte.getZoom() >= seuil;
}

// Griser / dégriser les cases des couches administratives dans le contrôle
function majCouleurs() {
  document.querySelectorAll(".leaflet-control-layers-overlays label").forEach(function (lab) {
    var texte = (lab.textContent || "").trim();
    Object.keys(COUCHES_ADMIN).forEach(function (nom) {
      if (texte.indexOf(nom) === -1) return;
      var input = lab.querySelector("input");
      if (!input) return;
      if (coucheDisponible(nom)) {
        input.disabled = false;
        lab.style.opacity = 1;
        lab.title = "";
      } else {
        input.disabled = true;
        lab.style.opacity = 0.45;
        lab.title = "Disponible à partir du zoom " + (SEUILS[nom] || 0);
        // retirer la couche si elle était affichée
        if (input.checked && carte.hasLayer(couchesAdmin[nom])) {
          carte.removeLayer(couchesAdmin[nom]);
        }
      }
    });
  });
}

// Afficher / masquer les étiquettes (noms) selon le zoom et l'activation
function majLabels() {
  var conteneur = carte.getContainer();
  ["dep"].forEach(function (cle) {
    var nomCouche = "Départements";
    var actif = carte.hasLayer(couchesAdmin[nomCouche])
      && carte.getZoom() >= (SEUILS_LABELS[cle] || 0);
    conteneur.classList.toggle("labels-" + cle + "-on", actif);
  });
}

// Les couches administratives se chargent au premier affichage seulement,
// et uniquement si le zoom est suffisant
carte.on("overlayadd", function (e) {
  var conf = COUCHES_ADMIN[e.name];
  if (!conf || conf.chargee) return;
  if (!coucheDisponible(e.name)) {
    // zoom insuffisant : décocher immédiatement, la couche reste grisé
    conf.grisee = true;
    majCouleurs();
    return;
  }
  conf.chargee = true;
  fetch(conf.url).then(function (r) { return r.json(); }).then(function (data) {
    var geo = L.geoJSON(data, {
      style: conf.style,
      onEachFeature: function (feature, couche) {
        var props = feature.properties || {};
        var nom = props.nom || props.NOM || props.code || props.CODE || "";
        if (nom) {
          couche.bindPopup("<strong>" + nom + "</strong>");
        }
        // Étiquette permanente : masquée par défaut (classe CSS) et
        // révélée par majLabels au-delà du seuil de zoom de sa couche.
        if (conf.etiquette) {
          var etiquette = nom;
          if (conf.etiquette === "dep") {
            var code = props.code || props.CODE || props.code_dep || "";
            etiquette = (code ? code + " — " : "") + nom;
          }
          couche.bindTooltip(etiquette, {
            permanent: true,
            direction: "center",
            className: "label-admin label-" + conf.etiquette
          });
        }
      }
    });
    couchesAdmin[e.name].addLayer(geo);
    majLabels();
  }).catch(function () {
    conf.chargee = false;  // permet de retenter en recochant la couche
  });
});

carte.on("zoomend", function () { majCouleurs(); majLabels(); });
carte.on("overlayremove", majLabels);
carte.whenReady(majCouleurs);

var ACTIVITES = {
  "MARAICHER": "🥬 Maraîcher·ère",
  "ARBORICULTEUR": "🍎 Arboriculteur·rice",
  "ELEVEUR": "🐄 Éleveur·euse",
  "FROMAGER": "🧀 Fromager·ère",
  "APICULTEUR": "🍯 Apiculteur·rice",
  "MICRO_BRASSEUR": "🍺 Micro-brasseur·euse",
  "CONSERVERIE": "🥫 Conserverie",
  "FOODTRUCK": "🚚 Foodtruck",
  "TRAITEUR": "🥗 Traiteur·e",
  "AUTRE": "🌾 Autre production locale"
};

/* ------------------- mode de visualisation (producteurs <-> restauration) */
var blocCarte = document.getElementById("carte-recherche");
var modeCarte = (blocCarte && blocCarte.getAttribute("data-mode"))
  || "producteurs";
var ACTIVITES_RESTAURATION = ["FOODTRUCK", "TRAITEUR"];
/* Activités affichées dans la légende selon le mode : tout sauf
   foodtruck / traiteur en mode producteurs, uniquement ces deux-là
   en mode restauration (la légende suit la bascule). */
function activitesDuMode() {
  return Object.keys(ACTIVITES).filter(function (cle) {
    return modeCarte === "restauration"
      ? ACTIVITES_RESTAURATION.indexOf(cle) >= 0
      : ACTIVITES_RESTAURATION.indexOf(cle) < 0;
  });
}

/* Spécialités foodtruck : libellés pour le popup du marqueur
   (le symbole du camion est complété par l'emoji de spécialité). */
var SPECIALITES = {
  "SANDWICHS": "Sandwichs & Plats",
  "PIZZA": "Pizza",
  "BURGER": "Burger",
  "TRAITEUR": "Traiteur",
  "ROTISSEUR": "Rôtisseur"
};

/* --------------------------------------------------------------- legende */
var legend = L.control({ position: "bottomright" });
var legendSpans = {};   // clés d'activité -> <span> pour mise à jour des comptes
legend.onAdd = function () {
  var div = L.DomUtil.create("div", "map-legend");
  /* Symboles par activité (identiques aux marqueurs et aux vignettes) —
     seuls symboles affichés : le filtre par cases à cocher (modes de
     production) a été retiré pour alléger la légende. Chaque ligne
     porte le dénombrement des entités VISIBLES dans l'emprise. */
  var symboles = document.createElement("div");
  symboles.className = "legend-symbole";
  if (modeCarte === "marches") {
    /* Mode marchés : deux symboles seulement — les marchés et les
       boutiques de producteurs détectés, dénombrés dans l'emprise. */
    symboles.innerHTML =
      '<span data-activite="MARCHE">🎪 Marchés <em class="legend-nb"></em></span>' +
      '<span data-activite="BOUTIQUE">🏪 Boutiques <em class="legend-nb"></em></span>';
  } else {
    symboles.innerHTML = activitesDuMode().map(function (cle) {
      return '<span data-activite="' + cle + '">' + ACTIVITES[cle] +
             ' <em class="legend-nb"></em></span>';
    }).join("");
  }
  div.appendChild(symboles);
  Array.prototype.forEach.call(
    symboles.querySelectorAll("span[data-activite]"), function (s) {
      legendSpans[s.getAttribute("data-activite")] =
        s.querySelector(".legend-nb");
    });
  return div;
};
legend.addTo(carte);

var markers = [];
var exploitants = JSON.parse(bloc.textContent);

exploitants.forEach(function (e) {
  /* Marché / boutique de producteurs : marqueur dédié (🎪 orange,
     🏪 rose), popup avec les horaires déduits et lien vers la
     fiche virtuelle ; le type alimente la légende. */
  if (e.est_marche) {
    var iconeM = L.divIcon({
      className: "marker-exploitant",
      html: '<span class="marker-activite marker-marche">' +
            e.symbole + "</span>",
      iconSize: [22, 22], iconAnchor: [11, 11]
    });
    var horairesM = (e.horaires_txt || []).join("<br>");
    var markerM = L.marker([e.latitude, e.longitude],
                           { icon: iconeM }).bindPopup(
      "<strong>" + e.nom + "</strong>" +
      '<br><span class="muted">' +
      (e.type === "MARCHE" ? "🎪 Marché" : "🏪 Boutique") +
      " · " + e.nb_producteurs + " producteur" +
      (e.nb_producteurs > 1 ? "s" : "") + "</span>" +
      (horairesM ? "<br>" + horairesM : "") +
      "<br>" + (e.ville || "") +
      '<br><a href="' + e.url + '">Voir la fiche →</a>'
    );
    markerM._activite = e.type;
    markers.push(markerM);
    carte.addLayer(markerM);
    return;
  }
  var style = CAT_STYLES[e.mode_production] || CAT_STYLES.CONV;
  var activite = ACTIVITES[e.activite] || "";
  /* Symbole : camion + emoji de spécialité pour les foodtrucks,
     symbole de l'activité sinon (précalculé côté serveur). */
  var symbole = e.symbole
    || (activite || "🌾 Autre").split(" ")[0];
  var libelle = activite;
  if (e.activite === "FOODTRUCK" && e.specialite
      && SPECIALITES[e.specialite]) {
    libelle += " — " + SPECIALITES[e.specialite];
  }
  var badgeDemo = e.est_demo
    ? '<br><span class="badge badge-demo">🧪 DÉMO</span>' : "";
  /* Marqueur compact : le symbole d'activité est le corps du marqueur,
     la couleur du mode de production est portée par une petite pastille
     en bas à droite (peu d'espace pris sur la carte). */
  var icone = L.divIcon({
    className: "marker-exploitant",
    html: '<span class="marker-activite' +
          (e.activite === "FOODTRUCK" && e.specialite
             ? " marker-foodtruck" : "") + '">' + symbole + "</span>" +
          '<span class="marker-point" style="background:' + style.color + '"></span>',
    iconSize: [22, 22], iconAnchor: [11, 11]
  });
  /* Position dynamique (foodtrucks) : emplacement du créneau en
     cours ou du prochain arrêt, calculé au moment de la recherche. */
  var positionDyn = (e.position_libelle || "")
    ? '<br><span class="muted">📍 ' + e.position_libelle + "</span>"
    : "";
  var marker = L.marker([e.latitude, e.longitude], { icon: icone }).bindPopup(
    "<strong>" + e.nom_ferme + "</strong>" +
    (libelle ? '<br><span class="muted">' + libelle + "</span>" : "") +
    badgeDemo +
    "<br>" + (e.ville || "") +
    positionDyn +
    '<br><a href="' + e.url + '">Nos Produits →</a>'
  );
  marker._category = e.mode_production;
  marker._activite = e.activite;
  markers.push(marker);
  carte.addLayer(marker);
});

/* --------------------------- filtre spatial dynamique + dénombrements */
/* Légende : compte des marqueurs par activité DANS l'emprise courante ;
   vignettes : seules celles dans l'emprise restent affichées. */
function majEmprise() {
  var bornes = carte.getBounds();
  var comptes = {};
  markers.forEach(function (m) {
    if (bornes.contains(m.getLatLng())) {
      comptes[m._activite] = (comptes[m._activite] || 0) + 1;
    }
  });
  Object.keys(legendSpans).forEach(function (cle) {
    var nb = comptes[cle] || 0;
    if (legendSpans[cle]) {
      legendSpans[cle].textContent = "(" + nb + ")";
      legendSpans[cle].parentNode.style.opacity = nb ? 1 : 0.45;
    }
  });
  var cartes = document.querySelectorAll(
    ".vignette-producteur[data-lat]");
  cartes.forEach(function (card) {
    var lat = parseFloat(card.getAttribute("data-lat"));
    var lng = parseFloat(card.getAttribute("data-lng"));
    card.classList.toggle(
      "hors-carte", !bornes.contains(L.latLng(lat, lng)));
  });
}
carte.on("moveend zoomend", majEmprise);

// Cadrer la carte sur les résultats
if (exploitants.length) {
  var bornes = [];
  exploitants.forEach(function (e) { bornes.push([e.latitude, e.longitude]); });
  carte.fitBounds(bornes, { padding: [30, 30], maxZoom: 12 });
}
carte.whenReady(majEmprise);

/* ----------------------------------------------- géolocalisation (cible) */
/* Bouton « 🎯 Me géolocaliser » directement SUR la carte (haut droite),
   symbole seul avec info-bulle au survol. */
/* Bascule de mode depuis la carte : le formulaire de recherche est
   re-soumis avec le mode inverse — titre, filtres, légende et
   marqueurs s'adaptent d'un coup. */
var modeCtrl = L.control({ position: "topright" });
modeCtrl.onAdd = function () {
  var div = L.DomUtil.create("div", "leaflet-bar mode-carte");
  var cible = modeCarte === "producteurs" ? "restauration"
            : modeCarte === "restauration" ? "marches" : "producteurs";
  var btn = document.createElement("a");
  btn.href = "#";
  btn.textContent = cible === "restauration" ? "🍽️"
                  : cible === "marches" ? "🎪" : "🥬";
  btn.title = cible === "restauration"
    ? "Basculer : traiteurs & foodtrucks"
    : cible === "marches" ? "Basculer : marchés & boutiques"
    : "Basculer : producteurs";
  btn.setAttribute("aria-label", btn.title);
  L.DomEvent.disableClickPropagation(div);
  btn.addEventListener("click", function (evenement) {
    evenement.preventDefault();
    var form = document.querySelector(".search-bar");
    if (!form) { return; }
    var cache = form.querySelector('input[name="visu"]');
    if (!cache) {
      cache = document.createElement("input");
      cache.type = "hidden";
      cache.name = "visu";
      form.appendChild(cache);
    }
    cache.value = cible === "restauration" ? "restauration"
               : cible === "marches" ? "marches" : "";
    form.submit();
  });
  div.appendChild(btn);
  return div;
};
modeCtrl.addTo(carte);

var geolocCtrl = L.control({ position: "topright" });
geolocCtrl.onAdd = function () {
  var div = L.DomUtil.create("div",
    "leaflet-bar leaflet-control ctrl-geoloc");
  var btn = L.DomUtil.create("button", "btn-geoloc-cible", div);
  btn.type = "button";
  btn.title = "Me géolocaliser";
  btn.setAttribute("aria-label", "Me géolocaliser");
  btn.textContent = "🎯";
  L.DomEvent.disableClickPropagation(div);
  btn.addEventListener("click", function () {
    if (!navigator.geolocation) {
      alert("La géolocalisation n'est pas supportée par votre navigateur.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        carte.setView([pos.coords.latitude, pos.coords.longitude], 11);
        L.circleMarker([pos.coords.latitude, pos.coords.longitude], {
          radius: 6, color: "#c62828", fillColor: "#ef5350", fillOpacity: 0.9
        }).addTo(carte).bindPopup("Vous êtes ici").openPopup();
      },
      function () { alert("Position non disponible."); },
      { timeout: 10000 }
    );
  });
  /* 🏠 « Chez moi » : pro connecté → son exploitation (coordonnées
     passées par le serveur) ; client connecté → géolocalisation ;
     visiteur anonyme → pas de bouton. */
  var chezMoi = null;
  var blocMaison = document.getElementById("home-carte");
  if (blocMaison) {
    try { chezMoi = JSON.parse(blocMaison.textContent); } catch (e) {}
  }
  if (chezMoi) {
    var maison = L.DomUtil.create("button", "btn-geoloc-cible", div);
    maison.type = "button";
    maison.title = "Chez moi";
    maison.setAttribute("aria-label", "Centrer sur mon adresse");
    maison.textContent = "🏠";
    maison.addEventListener("click", function () {
      if (chezMoi.lat !== null && chezMoi.lat !== undefined) {
        carte.setView([chezMoi.lat, chezMoi.lon], 12);
        L.circleMarker([chezMoi.lat, chezMoi.lon], {
          radius: 6, color: "#1565c0", fillColor: "#64b5f6",
          fillOpacity: 0.9
        }).addTo(carte).bindPopup("🏠 Mon exploitation").openPopup();
      } else if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function (pos) {
          carte.setView([pos.coords.latitude, pos.coords.longitude], 11);
        }, function () { alert("Position non disponible."); },
        { timeout: 10000 });
      }
    });
  }
  /* 🌍 Recadrage global : tous les marqueurs visibles à l'écran. */
  var monde = L.DomUtil.create("button", "btn-geoloc-cible", div);
  monde.type = "button";
  monde.title = "Revoir tous les résultats";
  monde.setAttribute("aria-label", "Recadrer sur tous les résultats");
  monde.textContent = "🌍";
  monde.addEventListener("click", function () {
    if (exploitants.length) {
      var bornes = [];
      exploitants.forEach(function (e) {
        bornes.push([e.latitude, e.longitude]);
      });
      carte.fitBounds(bornes, { padding: [30, 30], maxZoom: 12 });
    }
  });
  return div;
};
geolocCtrl.addTo(carte);

/* ------------------------------------------- zone spatiale (dept/région/CP) */
/* Saisie intelligente : nom ou numéro de département, nom de région
   ou code postal (les 2 premiers chiffres suffisent) — la carte
   zoome directement dessus au chargement. Le champ ne filtre PAS
   le jeu de résultats côté serveur : ce sont l'emprise de la carte
   et majEmprise() qui masquent les vignettes hors zone. */
(function () {
  var zone = ((blocCarte.getAttribute("data-zone") || "")).trim();
  if (!zone) { return; }
  function normalise(t) {
    return (t || "").toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]/g, "");
  }
  var chiffres = (zone.match(/\d/g) || []).join("");
  var code = chiffres.length >= 2 ? chiffres.slice(0, 2) : "";
  var nom = normalise(zone.replace(/\d+/g, ""));
  function cherche(features) {
    return features.filter(function (f) {
      var p = f.properties || {};
      if (code && String(p.code).replace(/^0+/, "") ===
          code.replace(/^0+/, "")) { return true; }
      return !!(nom && normalise(p.nom) === nom);
    });
  }
  function cadreSiTrouve(features) {
    var trouves = cherche(features);
    if (!trouves.length) { return false; }
    var bornes = L.latLngBounds();
    trouves.forEach(function (f) {
      bornes.extend(L.geoJSON(f).getBounds());
    });
    carte.fitBounds(bornes, { padding: [30, 30] });
    return true;
  }
  function essai(url, ensuite) {
    fetch(url).then(function (r) { return r.json(); })
      .then(function (gj) { ensuite(gj.features || []); })
      .catch(function () { /* réseau indisponible : cadrage par défaut */ });
  }
  essai(FOND_ADMIN + "departements.geojson", function (feats) {
    if (!cadreSiTrouve(feats)) {
      essai(FOND_ADMIN + "regions.geojson", cadreSiTrouve);
    }
  });
})();
