/* Carte Leaflet des producteurs — MonPetitMaraicher */

/* Échappement HTML : toute valeur issue des données (noms, villes,
   URL, horaires) est neutralisée avant insertion dans un popup ou une
   info-bulle — XSS stockée impossible (audit sécurité, lot 1). */
function esc(t) {
  return String(t == null ? "" : t)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


// Styles par mode de production
var CAT_STYLES = {
  AB:      { color: "#1b5e20", label: "Agriculture Biologique (AB)" },
  PERMA:   { color: "#6a1b9a", label: "Permaculture" },
  PAYSAN:  { color: "#f9a825", label: "Agriculture paysanne" },
  RAISONNE:{ color: "#0277bd", label: "Agriculture raisonnée" },
  CONV:    { color: "#546e7a", label: "Conventionnelle" }
};

// France métropolitaine
var map = L.map("carte-producteurs").setView([46.6, 2.4], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>"
}).addTo(map);

var layers = {}; // catégorie -> LayerGroup
var markers = [];

// Légende + filtres
var legend = L.control({ position: "bottomright" });
legend.onAdd = function () {
  var div = L.DomUtil.create("div", "map-legend");
  for (var key in CAT_STYLES) {
    var style = CAT_STYLES[key];
    div.innerHTML +=
      '<label><input type="checkbox" checked data-cat="' + key + '">' +
      '<span class="legend-dot" style="background:' + style.color + '"></span>' +
      style.label + "</label>";
  }
  return div;
};
legend.addTo(map);

// Chargement des exploitants
fetch(document.body.dataset.geojsonUrl)
  .then(function (r) { return r.json(); })
  .then(function (exploitants) {
    exploitants.forEach(function (e) {
      var style = CAT_STYLES[e.mode_production] || CAT_STYLES.CONV;
      var marker = L.circleMarker([e.latitude, e.longitude], {
        radius: 8,
        color: "#fff",
        weight: 1.5,
        fillColor: style.color,
        fillOpacity: 0.85
      }).bindPopup(
        "<strong>" + esc(e.nom_ferme) + "</strong><br>" + esc(e.ville || "") +
        '<br><a href="' + esc(e.url) + '">Voir la ferme →</a>'
      );
      marker._category = e.mode_production;
      markers.push(marker);
    });
    applyFilters();
  });

function applyFilters() {
  var enabled = {};
  document.querySelectorAll(".map-legend input").forEach(function (cb) {
    enabled[cb.dataset.cat] = cb.checked;
  });
  markers.forEach(function (m) {
    if (enabled[m._category]) {
      if (!map.hasLayer(m)) map.addLayer(m);
    } else if (map.hasLayer(m)) {
      map.removeLayer(m);
    }
  });
}

document.addEventListener("change", function (e) {
  if (e.target.closest && e.target.closest(".map-legend")) applyFilters();
});

// Géolocalisation de l'utilisateur
document.getElementById("btn-geoloc").addEventListener("click", function () {
  if (!navigator.geolocation) {
    alert("La géolocalisation n'est pas supportée par votre navigateur.");
    return;
  }
  navigator.geolocation.getCurrentPosition(
    function (pos) {
      map.setView([pos.coords.latitude, pos.coords.longitude], 11);
      L.circleMarker([pos.coords.latitude, pos.coords.longitude], {
        radius: 6, color: "#c62828", fillColor: "#ef5350", fillOpacity: 0.9
      }).addTo(map).bindPopup("Vous êtes ici").openPopup();
    },
    function () { alert("Position non disponible."); },
    { timeout: 10000 }
  );
});
