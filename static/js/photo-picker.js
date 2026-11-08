/* Aperçu photo de profil dédié : relie un conteneur
   [data-photo-apercu="id-du-champ-url"] au cadre .image-picker placé
   dans la page (mises en page personnalisées où l'aperçu n'est pas
   collé sous le champ — image-picker.js ignore ces champs grâce à
   l'attribut data-picker-custom du bloc englobant). */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-photo-apercu]").forEach(function (bloc) {
      var input = document.getElementById(bloc.dataset.photoApercu);
      var img = bloc.querySelector(".image-picker-img");
      if (!input || !img) { return; }

      function maj() {
        var url = (input.value || "").trim();
        bloc.classList.toggle("image-picker-actif", Boolean(url));
        bloc.classList.remove("image-picker-en-erreur");
        if (url) { img.src = url; }
      }

      img.addEventListener("load", function () {
        bloc.classList.remove("image-picker-en-erreur");
      });
      img.addEventListener("error", function () {
        if ((input.value || "").trim()) {
          bloc.classList.add("image-picker-en-erreur");
        }
      });
      input.addEventListener("input", maj);
      input.addEventListener("change", maj);

      /* état initial (photo déjà enregistrée sur la fiche) */
      maj();
    });
  });
})();
