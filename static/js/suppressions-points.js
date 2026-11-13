(function () {
  "use strict";

  /* Suppressions réversibles de la page Points & créneaux :
     - créneau : masquage immédiat + toast « Annuler » (7 s) ;
     - point : fenêtre de validation récapitulative, puis le même
       toast d'annulation. La suppression n'est envoyée au serveur
       qu'à la fin du délai : tant qu'on reste sur la page, on peut
       revenir en arrière. */

  document.addEventListener("DOMContentLoaded", function () {
    var toast = document.createElement("div");
    toast.className = "toast-suppression";
    toast.hidden = true;
    document.body.appendChild(toast);
    var minuteur = null, enAttente = null;

    function annule() {
      if (minuteur) { clearInterval(minuteur); minuteur = null; }
      if (enAttente) {
        enAttente.element.classList.remove("suppression-en-cours");
        enAttente = null;
      }
      toast.hidden = true;
    }

    function programme(form, element, libelle) {
      enAttente = { form: form, element: element };
      element.classList.add("suppression-en-cours");
      var restant = 7;
      function rendu() {
        toast.innerHTML = "<span>🗑 " + libelle + " — suppression" +
          " dans " + restant + " s</span>" +
          "<button type=\"button\"" +
          " class=\"btn-annuler-suppression\">↩️ Annuler</button>";
      }
      rendu();
      toast.querySelector(".btn-annuler-suppression")
        .addEventListener("click", annule);
      minuteur = setInterval(function () {
        restant -= 1;
        if (restant <= 0) {
          clearInterval(minuteur);
          minuteur = null;
          toast.hidden = true;
          form.submit();
        } else { rendu(); }
      }, 1000);
    }

    /* ---- Fenêtre de validation récapitulative (points) ---- */
    var dlg = document.createElement("dialog");
    dlg.className = "dlg-suppression";
    document.body.appendChild(dlg);

    function recapPoint(form) {
      var d = form.dataset;
      var nb = parseInt(d.creneaux || "0", 10);
      dlg.innerHTML =
        "<h3>⚠️ Supprimer ce point ?</h3>" +
        "<ul>" +
        "<li><strong>" + (d.nom || "") + "</strong> — " + (d.type || "") + "</li>" +
        (d.adresse ? "<li>" + d.adresse + "</li>" : "") +
        "<li>" + nb + " créneau" + (nb === 1 ? "" : "x") +
        " rattaché" + (nb === 1 ? "" : "s") +
        " sera" + (nb === 1 ? "" : "ont") + " également supprimé" +
        (nb === 1 ? "" : "s") + "</li>" +
        "</ul>" +
        "<p class=\"muted\">Les paniers déjà livrés conservent les" +
        " informations transmises aux clients. Après validation, la" +
        " suppression reste annulable quelques secondes tant que vous" +
        " restez sur la page.</p>" +
        "<div class=\"dlg-actions\">" +
        "<button type=\"button\" class=\"btn btn-sm btn-danger btn-confirmer\">🗑 Supprimer définitivement</button>" +
        "<button type=\"button\" class=\"btn btn-sm btn-annuler\">↩️ Annuler</button>" +
        "</div>";
      dlg.querySelector(".btn-confirmer").addEventListener(
        "click", function () {
          dlg.close();
          programme(form, form.closest(".harvest-item") || form,
                    "Point « " + (d.nom || "") + " »");
        });
      dlg.querySelector(".btn-annuler").addEventListener(
        "click", function () { dlg.close(); });
      dlg.showModal();
    }

    /* ---- Interception des soumissions (capture) ---- */
    document.addEventListener("submit", function (e) {
      var form = e.target;
      if (!form || !form.querySelector) { return; }
      var champ = form.querySelector('input[name="action"]');
      var action = champ ? champ.value : "";
      if (action === "point_supprimer" &&
          form.classList.contains("form-supprimer-point")) {
        e.preventDefault();
        recapPoint(form);
      } else if (action === "creneau_supprimer") {
        e.preventDefault();
        var li = form.closest("li");
        var libelle = li ? li.textContent.trim().replace(/\s+/g, " ").slice(0, 60)
                         : "Créneau";
        programme(form, li || form, "Créneau « " + libelle + "… »");
      }
    }, true);
  });
})();
