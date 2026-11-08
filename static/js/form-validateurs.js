/* Vérificateurs de saisie en direct : pastille ✓ / ✗ sous les
   champs e-mail et mots de passe, pendant la frappe. Cibles (si
   présentes dans la page) : #id_email, #id_password1 et
   #id_password2 (inscriptions), #id_new_password1 et
   #id_new_password2 (section Sécurité). Aide visuelle uniquement :
   la validation finale reste côté serveur (Django). */
(function () {
  "use strict";

  var COURANTS = ["password", "password1", "password123", "123456",
    "1234567", "12345678", "123456789", "qwerty", "azerty",
    "azertyuiop", "abc123", "iloveyou", "admin", "administrateur",
    "letmein", "soleil", "doudou", "loulou", "chouchou", "motdepasse",
    "mot2passe", "motdepasse1"];

  function champ(id) { return document.getElementById(id); }

  function indicateur(input) {
    var el = document.createElement("div");
    el.className = "saisie-indicateur";
    input.parentNode.insertBefore(el, input.nextSibling);
    return el;
  }

  function majEtat(el, ok, message) {
    el.classList.toggle("indicateur-ok", ok);
    el.classList.toggle("indicateur-erreur", !ok);
    el.textContent = (ok ? "✓ " : "✗ ") + message;
  }

  function vide(el) {
    el.className = "saisie-indicateur";
    el.textContent = "";
  }

  /* E-mail : format d'adresse valide (le compte existant déjà est
     vérifié à la soumission par le serveur). */
  function initEmail() {
    var input = champ("id_email");
    if (!input) { return; }
    var el = indicateur(input);
    function maj() {
      var v = (input.value || "").trim();
      if (!v) { vide(el); return; }
      var ok = /^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$/i.test(v);
      majEtat(el, ok, ok ? "Adresse e-mail valide"
                         : "Format d'adresse invalide (ex : prenom@domaine.fr)");
    }
    input.addEventListener("input", maj);
    maj();
  }

  /* Choix du mot de passe : longueur, pas uniquement des chiffres,
     pas un mot de passe trop courant (même esprit que la validation
     Django :MinimumLength, NumericPassword, CommonPassword). */
  function initMotDePasse1() {
    var input = champ("id_password1") || champ("id_new_password1");
    if (!input) { return; }
    var el = indicateur(input);
    function maj() {
      var v = input.value || "";
      if (!v) { vide(el); return; }
      if (v.length < 8) {
        majEtat(el, false, "8 caractères minimum (" + v.length + "/8)");
        return;
      }
      if (/^\d+$/.test(v)) {
        majEtat(el, false, "Pas uniquement des chiffres");
        return;
      }
      if (COURANTS.indexOf(v.toLowerCase()) !== -1) {
        majEtat(el, false, "Mot de passe trop courant : évitez les classiques");
        return;
      }
      majEtat(el, true, "Mot de passe valide");
    }
    input.addEventListener("input", maj);
    maj();
  }

  /* Confirmation : les deux mots de passe correspondent (la pastille
     suit aussi la retouche du premier champ). */
  function initMotDePasse2() {
    var input = champ("id_password2") || champ("id_new_password2");
    var ref = champ("id_password1") || champ("id_new_password1");
    if (!input || !ref) { return; }
    var el = indicateur(input);
    function maj() {
      var v = input.value || "";
      if (!v) { vide(el); return; }
      var ok = v === ref.value;
      majEtat(el, ok, ok ? "Les deux mots de passe correspondent"
                         : "Les mots de passe ne correspondent pas");
    }
    input.addEventListener("input", maj);
    ref.addEventListener("input", maj);
    maj();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initEmail();
    initMotDePasse1();
    initMotDePasse2();
  });
})();
