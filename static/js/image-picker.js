/* Sélecteur d'image externe avec aperçu dynamique.
   S'active automatiquement sur les champs URL de photo/logo
   (#id_photo_externe, #id_logo_externe) : aperçu en direct pendant la
   saisie, message explicite si le lien ne pointe pas vers une image.
   Les champs situés dans un bloc [data-picker-custom] sont ignorés :
   la page fournit son propre aperçu (photo-picker.js), on ne duplique
   pas le cadre collé sous le champ. */
(function () {
  "use strict";

  var CIBLES = [
    { id: "id_photo_externe", libelle: "👤 Photo de profil", vide: "👤 Aucune photo" },
    { id: "id_logo_externe",  libelle: "🏛️ Logo de l'exploitation", vide: "🌱 Aucun logo" }
  ];

  function creerPicker(input, conf) {
    var conteneur = document.createElement("div");
    conteneur.className = "image-picker";

    var cadre = document.createElement("div");
    cadre.className = "image-picker-cadre";

    var apercu = document.createElement("img");
    apercu.className = "image-picker-img";
    apercu.alt = conf.libelle;

    var vide = document.createElement("div");
    vide.className = "image-picker-placeholder";
    vide.textContent = conf.vide;

    var erreur = document.createElement("div");
    erreur.className = "image-picker-erreur";
    erreur.textContent = "❌ Image introuvable : vérifiez que le lien pointe directement vers l'image (.jpg, .png, .webp…).";

    var aide = document.createElement("p");
    aide.className = "muted image-picker-aide";
    aide.textContent = "Aperçu en direct : collez le lien direct de l'image " +
      "(Drive/Cloud : utilisez le lien de partage de l'image ou un lien se terminant par .jpg/.png/.webp).";

    cadre.appendChild(apercu);
    cadre.appendChild(vide);
    cadre.appendChild(erreur);
    conteneur.appendChild(cadre);
    conteneur.appendChild(aide);

    // insérer juste après le champ
    if (input.nextSibling) {
      input.parentNode.insertBefore(conteneur, input.nextSibling);
    } else {
      input.parentNode.appendChild(conteneur);
    }

    function maj() {
      var url = (input.value || "").trim();
      conteneur.classList.toggle("image-picker-actif", Boolean(url));
      conteneur.classList.remove("image-picker-en-erreur");
      if (url) apercu.src = url;
    }

    apercu.addEventListener("load", function () {
      conteneur.classList.remove("image-picker-en-erreur");
    });
    apercu.addEventListener("error", function () {
      if (input.value.trim()) conteneur.classList.add("image-picker-en-erreur");
    });
    input.addEventListener("input", maj);
    input.addEventListener("change", maj);

    // état initial (préremplissage depuis la fiche)
    maj();
  }

  document.addEventListener("DOMContentLoaded", function () {
    CIBLES.forEach(function (conf) {
      var input = document.getElementById(conf.id);
      // Mise en page personnalisée (aperçu placé dans la page) :
      // le champ est pris en charge par photo-picker.js.
      if (input && input.closest("[data-picker-custom]")) { return; }
      if (input) creerPicker(input, conf);
    });
  });
})();
