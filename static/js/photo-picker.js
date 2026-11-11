/* Aperçu photo de profil dédié : relie un conteneur
   [data-photo-apercu="id-du-champ-url"] au cadre .image-picker placé
   dans la page (mises en page personnalisées où l'aperçu n'est pas
   collé sous le champ — image-picker.js ignore ces champs grâce à
   l'attribut data-picker-custom du bloc englobant).
   Compléments d'ergonomie : conversion automatique des liens de
   partage Drive en lien d'image direct (note sous le champ), et
   bouton « Ma photo Google » (photo du compte Google connecté,
   jamais hébergée par le portail). */
(function () {
  "use strict";

  /* drive.google.com/file/d/ID… (ou open?id=ID) vers le lien d'image
     servi par Google — taille raisonnable pour un avatar. */
  function convertirDrive(url) {
    var m = url.match(/drive\.google\.com\/file\/d\/([0-9A-Za-z_-]{10,})/);
    if (m) {
      return "https://drive.google.com/thumbnail?id=" + m[1] +
             "&sz=s400";
    }
    m = url.match(/drive\.google\.com\/(?:open|uc)\?[^#]*[?&]id=([0-9A-Za-z_-]{10,})/);
    if (m) {
      return "https://drive.google.com/thumbnail?id=" + m[1] +
             "&sz=s400";
    }
    return null;
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-photo-apercu]").forEach(function (bloc) {
      var input = document.getElementById(bloc.dataset.photoApercu);
      var img = bloc.querySelector(".image-picker-img");
      if (!input || !img) { return; }

      var note = document.createElement("div");
      note.className = "photo-note";
      input.parentNode.insertBefore(note, input.nextSibling);

      function maj() {
        var url = (input.value || "").trim();
        bloc.classList.toggle("image-picker-actif", Boolean(url));
        bloc.classList.remove("image-picker-en-erreur");
        if (url) { img.src = url; }
      }

      function convertir() {
        var url = (input.value || "").trim();
        var direct = url ? convertirDrive(url) : null;
        if (direct && direct !== url) {
          input.value = direct;
          note.textContent =
            "🔗 Lien Drive converti en lien d'image direct.";
          maj();
        }
      }

      img.addEventListener("load", function () {
        bloc.classList.remove("image-picker-en-erreur");
      });
      img.addEventListener("error", function () {
        if ((input.value || "").trim()) {
          bloc.classList.add("image-picker-en-erreur");
        }
      });
      input.addEventListener("input", function () {
        note.textContent = "";
        maj();
      });
      input.addEventListener("change", convertir);

      /* état initial (photo déjà enregistrée sur la fiche) */
      maj();
    });

    /* Bouton « Ma photo Google » : renseigne l'URL de la photo du
       compte Google connecté (servie par Google, rien n'est hébergé
       par le portail). */
    document.querySelectorAll("[data-photo-google]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var colonne = btn.closest(".profil-photo");
        if (!colonne) { return; }
        var apercu = colonne.querySelector("[data-photo-apercu]");
        if (!apercu) { return; }
        var input = document.getElementById(apercu.dataset.photoApercu);
        if (!input || !btn.dataset.photoGoogle) { return; }
        input.value = btn.dataset.photoGoogle;
        input.dispatchEvent(new Event("input"));
        input.dispatchEvent(new Event("change"));
      });
    });
  });
})();
