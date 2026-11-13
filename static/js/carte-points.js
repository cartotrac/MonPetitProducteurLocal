(function () {
  "use strict";

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
      marqueurs.push({ pk: p.pk, nom: p.nom, marqueur: m,
                       origine: [p.latitude, p.longitude] });
    });

    function recadrer() {
      if (marqueurs.length) {
        carte.fitBounds(
          L.featureGroup(marqueurs.map(function (x) { return x.marqueur; }))
            .getBounds(), { padding: [40, 40], maxZoom: 14 });
      } else {
        carte.setView([46.6, 2.4], 6);
      }
    }
    recadrer();

    /* ---- Exposer un point depuis sa fiche (lien « voir sur la carte ») ---- */
    function exposer(pk) {
      var trouve = marqueurs.filter(function (x) { return x.pk === pk; })[0];
      if (!trouve) { return false; }
      carteEl.scrollIntoView({ behavior: "smooth", block: "center" });
      carte.panTo(trouve.marqueur.getLatLng());
      trouve.marqueur.openPopup();
      var el = trouve.marqueur.getElement();
      if (el) {
        el.classList.add("pulse");
        setTimeout(function () { el.classList.remove("pulse"); }, 2400);
      }
      return true;
    }
    window.cartePoints = { exposer: exposer };

    /* ---- Barre de recherche intelligente (comme les autres cartes) ---- */
    var ctrlRecherche = L.control({ position: "topleft" });
    ctrlRecherche.onAdd = function () {
      var div = L.DomUtil.create("div",
        "leaflet-bar leaflet-control ctrl-recherche");
      var boite = L.DomUtil.create("div", "recherche-boite", div);
      var input = L.DomUtil.create("input", "recherche-input", boite);
      var liste = L.DomUtil.create("ul", "recherche-liste", boite);
      input.type = "search";
      input.placeholder = "🔎 Commune, adresse, département, pays…";
      input.setAttribute("aria-label",
        "Rechercher un lieu : la carte zoome dessus");
      liste.hidden = true;
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      var minuteur = null, sequence = 0;
      function cacher() { liste.hidden = true; liste.innerHTML = ""; }
      function choisir(res) {
        cacher();
        var lat = parseFloat(res.lat), lon = parseFloat(res.lon);
        if (isNaN(lat) || isNaN(lon)) { return; }
        if (res.boundingbox && res.boundingbox.length === 4) {
          carte.fitBounds(L.latLngBounds(
            [[+res.boundingbox[0], +res.boundingbox[2]],
             [+res.boundingbox[1], +res.boundingbox[3]]]),
            { maxZoom: 16, padding: [20, 20] });
        } else {
          carte.setView([lat, lon], 16);
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
        minuteur = setTimeout(function () {
          var n = ++sequence;
          fetch("https://nominatim.openstreetmap.org/search" +
                "?format=json&limit=6&countrycodes=fr&q=" +
                encodeURIComponent(q))
            .then(function (r) { return r.json(); })
            .then(function (res) { if (n === sequence) { suggestions(res || []); } })
            .catch(function () { if (n === sequence) { cacher(); } });
        }, 350);
      });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { cacher(); input.blur(); return; }
        if (e.key !== "Enter") { return; }
        e.preventDefault();
        var q = input.value.trim();
        if (!q) { return; }
        var premier = !liste.hidden && liste.querySelector("li");
        if (premier) { premier.click(); }
        else {
          fetch("https://nominatim.openstreetmap.org/search" +
                "?format=json&limit=1&countrycodes=fr&q=" +
                encodeURIComponent(q))
            .then(function (r) { return r.json(); })
            .then(function (res) {
              if (res.length) { choisir(res[0]); } else { cacher(); }
            })
            .catch(function () { cacher(); });
        }
      });
      document.addEventListener("click", function (e) {
        if (!boite.contains(e.target)) { cacher(); }
      });
      return div;
    };
    ctrlRecherche.addTo(carte);
    var coin = carte.getContainer().querySelector(".leaflet-top.leaflet-left");
    var divRecherche = carte.getContainer().querySelector(".ctrl-recherche");
    if (coin && divRecherche && divRecherche.parentNode === coin) {
      coin.insertBefore(divRecherche, coin.firstChild);
    }

    /* ---- Contrôles ✏️ Édition / ➕ Nouveau point (topright) ---- */
    var barre = L.control({ position: "topright" });
    barre.onAdd = function () {
      var div = L.DomUtil.create("div",
        "leaflet-bar leaflet-control ctrl-points");
      var btnEdit = L.DomUtil.create("button", "btn-points-edition", div);
      btnEdit.type = "button";
      btnEdit.innerHTML = "✏️ <span>Édition : non</span>";
      btnEdit.title = "Mode édition : déplacez un marqueur pour corriger sa position";
      var btnNew = L.DomUtil.create("button", "btn-points-nouveau", div);
      btnNew.type = "button";
      btnNew.innerHTML = "➕ <span>Nouveau point</span>";
      btnNew.title = "Créer un point : cliquez ensuite l'endroit sur la carte";
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      return div;
    };
    barre.addTo(carte);

    /* ---- Outils 🎯 géolocalisation et ⤢ recadrage (topright) ---- */
    var outils = L.control({ position: "topright" });
    outils.onAdd = function () {
      var div = L.DomUtil.create("div",
        "leaflet-bar leaflet-control ctrl-points-outils");
      var btnGeo = L.DomUtil.create("button", "btn-points-geoloc", div);
      btnGeo.type = "button";
      btnGeo.textContent = "🎯";
      btnGeo.title = "Me géolocaliser : recentre la carte sur ma position";
      var btnCadre = L.DomUtil.create("button", "btn-points-cadre", div);
      btnCadre.type = "button";
      btnCadre.textContent = "⤢";
      btnCadre.title = "Recadrer l'emprise sur tous mes points";
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      btnGeo.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Géolocalisation non supportée par ce navigateur.");
          return;
        }
        navigator.geolocation.getCurrentPosition(function (pos) {
          carte.setView([pos.coords.latitude, pos.coords.longitude], 15);
        }, function () { alert("Position refusée ou indisponible."); },
           { timeout: 10000 });
      });
      btnCadre.addEventListener("click", recadrer);
      return div;
    };
    outils.addTo(carte);

    var btnEdit = document.querySelector(".btn-points-edition");
    var btnNew = document.querySelector(".btn-points-nouveau");

    /* ---- Fenêtre de confirmation après déplacement d'un point ---- */
    var toast = null;
    function fermerToast() {
      if (toast) { toast.remove(); toast = null; }
    }
    function demanderEnregistrement(item, latlng) {
      fermerToast();
      toast = document.createElement("div");
      toast.className = "toast-points";
      toast.innerHTML =
        "<p><strong>" + esc(item.nom) + "</strong> déplacé — " +
        "adresse déduite (modifiable) :</p>" +
        '<input type="text" class="toast-adresse" ' +
        'placeholder="Adresse complète…">' +
        '<div class="toast-points-actions">' +
        '<button type="button" class="toast-ok">💾 Enregistrer</button>' +
        '<button type="button" class="toast-annuler">↩️ Annuler</button>' +
        "</div>";
      carteEl.appendChild(toast);
      var inp = toast.querySelector(".toast-adresse");
      var btnOk = toast.querySelector(".toast-ok");
      var btnKo = toast.querySelector(".toast-annuler");
      btnOk.disabled = true;
      btnOk.textContent = "⏳ Adresse…";
      fetch("https://nominatim.openstreetmap.org/reverse?format=json" +
            "&countrycodes=fr&lat=" + latlng.lat + "&lon=" + latlng.lng)
        .then(function (r) { return r.json(); })
        .then(function (res) {
          var a = (res && res.address) || {};
          var rue = [a.house_number, a.road].filter(Boolean).join(" ");
          var ville = a.city || a.town || a.village || a.municipality || "";
          var cp = a.postcode || "";
          inp.value = [rue, cp, ville].filter(Boolean).join(", ");
          btnOk.disabled = false;
          btnOk.textContent = "💾 Enregistrer";
          item.geo = { adresse: rue, ville: ville, cp: cp };
        })
        .catch(function () {
          btnOk.disabled = false;
          btnOk.textContent = "💾 Enregistrer (sans adresse)";
          item.geo = null;
        });
      inp.addEventListener("input", function () { item.geoSaisie = inp.value; });
      btnKo.addEventListener("click", function () {
        item.marqueur.setLatLng(item.origine);
        fermerToast();
      });
      btnOk.addEventListener("click", function () {
        var f = document.getElementById("form-deplacer-point");
        if (!f) { return; }
        f.elements["pk"].value = item.pk;
        f.elements["latitude"].value = latlng.lat.toFixed(6);
        f.elements["longitude"].value = latlng.lng.toFixed(6);
        var geo = item.geo || {};
        var saisie = (item.geoSaisie || "").trim();
        f.elements["adresse"].value = saisie || geo.adresse || "";
        f.elements["ville"].value = geo.ville || "";
        f.elements["code_postal"].value = geo.cp || "";
        f.submit();
      });
    }

    marqueurs.forEach(function (item) {
      item.marqueur.on("dragend", function () {
        demanderEnregistrement(item, item.marqueur.getLatLng());
      });
      item.marqueur.on("dragstart", fermerToast);
    });

    /* ---- Mode édition : marqueurs déplaçables + bouton ➕ visible ---- */
    var enEdition = false;
    var enCreation = false;
    var provisoire = null;
    var detailsCreation = document.getElementById("creation-point");
    var posInfo = document.getElementById("creation-point-position");
    var latIn = document.getElementById("id_latitude");
    var lonIn = document.getElementById("id_longitude");

    function remplirAdresseCreation(lat, lon) {
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
        .catch(function () { });
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
      remplirAdresseCreation(lat, lon);
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

    if (btnEdit) {
      btnEdit.addEventListener("click", function () {
        enEdition = !enEdition;
        btnEdit.classList.toggle("actif", enEdition);
        var lib = btnEdit.querySelector("span");
        if (lib) { lib.textContent = enEdition ? "Édition : actif" : "Édition : non"; }
        carteEl.classList.toggle("points-en-edition", enEdition);
        /* display:"" ne suffit pas : la règle CSS par défaut
           (.btn-points-nouveau { display:none) referait effet. */
        if (btnNew) { btnNew.style.display = enEdition ? "block" : "none"; }
        if (!enEdition) {
          fermerToast();
          basculerCreation(false);
        }
        marqueurs.forEach(function (x) {
          if (enEdition) { x.marqueur.dragging.enable(); }
          else { x.marqueur.dragging.disable(); }
        });
      });
    }
    if (btnNew) {
      btnNew.style.display = "none";
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

    /* ---- Liens croisés fiches → carte (voir / localiser) ---- */
    document.addEventListener("click", function (e) {
      var cible = e.target;
      while (cible && cible !== document) {
        if (cible.classList &&
            (cible.classList.contains("lien-exposer") ||
             cible.classList.contains("lien-localiser"))) { break; }
        cible = cible.parentNode;
      }
      if (!cible || cible === document) { return; }
      if (cible.classList.contains("lien-localiser") &&
          !enEdition && btnEdit) { btnEdit.click(); }
      var pk = parseInt(cible.getAttribute("data-point"), 10);
      if (!isNaN(pk)) { exposer(pk); }
    });
  });
})();
