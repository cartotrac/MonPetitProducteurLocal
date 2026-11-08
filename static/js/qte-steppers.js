/* Steppers de quantité : chaque champ numérique commandable
   (récolte, catalogue, carte) reçoit un bouton − et un bouton + qui
   ajustent la valeur par pas (kg : 0,01 ; pièce : 1), sans passer
   sous 0. Les champs épuisés (disabled) ne réagissent pas. */
(function () {
  document.querySelectorAll(
    "input[type='number'][name^='q'], " +
    "input[type='number'][name^='qty'], " +
    "input[type='number'][name^='carte_']").forEach(
    function (champ) {
      if (champ.dataset.stepper) { return; }
      champ.dataset.stepper = "1";
      var pas = parseFloat(champ.step) || 1;
      function bouton(texte, delta, titre) {
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = texte;
        b.className = "btn btn-sm btn-outline qte-step";
        b.title = titre;
        b.addEventListener("click", function () {
          if (champ.disabled) { return; }
          var v = parseFloat(champ.value);
          var base = (isNaN(v) || v < 0) ? 0 : v;
          champ.value = Math.max(
            0, Math.round((base + delta) * 100) / 100);
          champ.dispatchEvent(
            new Event("input", { bubbles: true }));
        });
        return b;
      }
      champ.insertAdjacentElement(
        "beforebegin", bouton("－", -pas, "Retirer " + pas));
      champ.insertAdjacentElement(
        "afterend", bouton("＋", pas, "Ajouter " + pas));
    });
})();
