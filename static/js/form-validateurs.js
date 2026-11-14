/* Vérificateurs de saisie en direct : pastille ✓ / ✗ sous les
   champs e-mail, identifiant et mots de passe, pendant la frappe.
   Cibles (si
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

  /* Identifiant de connexion (section Sécurité) : format contrôlé
     pendant la frappe, disponibilité vérifiée auprès du serveur avec
     un léger délai — la décision finale reste à l'enregistrement. */
  function initUsername() {
    var input = champ("id_username");
    if (!input || !input.dataset.urlDispo) { return; }
    var el = indicateur(input);
    var minuteur = null;
    function majServeur() {
      fetch(input.dataset.urlDispo + "?username=" +
            encodeURIComponent((input.value || "").trim()),
            { headers: { "X-Requested-With": "XMLHttpRequest" },
              credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          majEtat(el, Boolean(d.disponible), d.message || "");
        })
        .catch(function () { vide(el); });
    }
    function maj() {
      var v = (input.value || "").trim();
      if (!v) { vide(el); return; }
      if (!/^[\w.@+-]+$/i.test(v)) {
        majEtat(el, false, "Lettres, chiffres et @/./+/-/_ uniquement");
        return;
      }
      majEtat(el, true, "Vérification de la disponibilité…");
      if (minuteur) { clearTimeout(minuteur); }
      minuteur = setTimeout(majServeur, 350);
    }
    input.addEventListener("input", maj);
    maj();
  }

  /* Téléphone : format numéro français/international avec pré-détection et contrôle */
  function initTelephone() {
    var inputs = [champ("id_telephone"), champ("id_tel")];
    inputs.forEach(function (input) {
      if (!input) return;
      var el = indicateur(input);
      var badgeIndicatif = champ("tel-indicatif");

      // Filtrer les caractères interdits : chiffres, +, espaces, tirets, parenthèses uniquement
      input.addEventListener("keypress", function (e) {
        if (!/[\d\s.+\-()]/.test(e.key) && e.key !== "Backspace" && e.key !== "Delete" && e.key !== "ArrowLeft" && e.key !== "ArrowRight") {
          e.preventDefault();
        }
      });

      function maj() {
        var v = (input.value || "").trim();
        // Suppression automatique d'éventuelles lettres collées par copier-coller
        var nettoyee = v.replace(/[^\d\s.+\-()]/g, "");
        if (nettoyee !== v) {
          input.value = nettoyee;
          v = nettoyee;
        }

        if (!v) {
          vide(el);
          input.classList.remove("input-saisie-alerte");
          if (badgeIndicatif) { badgeIndicatif.textContent = "🇫🇷 +33"; }
          return;
        }

        var propre = v.replace(/[\s.\-()]/g, "");

        // Détection automatique de l'indicatif
        if (badgeIndicatif) {
          if (propre.startsWith("+32") || propre.startsWith("0032")) {
            badgeIndicatif.textContent = "🇧🇪 +32";
          } else if (propre.startsWith("+41") || propre.startsWith("0041")) {
            badgeIndicatif.textContent = "🇨🇭 +41";
          } else if (propre.startsWith("+352") || propre.startsWith("00352")) {
            badgeIndicatif.textContent = "🇱🇺 +352";
          } else if (propre.startsWith("+1") || propre.startsWith("001")) {
            badgeIndicatif.textContent = "🇺🇸/🇨🇦 +1";
          } else if (propre.startsWith("+34") || propre.startsWith("0034")) {
            badgeIndicatif.textContent = "🇪🇸 +34";
          } else if (propre.startsWith("+39") || propre.startsWith("0039")) {
            badgeIndicatif.textContent = "🇮🇹 +39";
          } else if (propre.startsWith("+49") || propre.startsWith("0049")) {
            badgeIndicatif.textContent = "🇩🇪 +49";
          } else if (propre.startsWith("+44") || propre.startsWith("0044")) {
            badgeIndicatif.textContent = "🇬🇧 +44";
          } else {
            badgeIndicatif.textContent = "🇫🇷 +33";
          }
        }

        // Format téléphone : 10 chiffres (0X...) ou indicatif international
        var ok = /^(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}$/.test(v) || /^\+?\d{9,15}$/.test(propre);
        if (!ok) {
          majEtat(el, false, "Numéro invalide (ex : 06 12 34 56 78 ou +33 6 ...)");
          input.classList.add("input-saisie-alerte");
        } else {
          majEtat(el, true, "Numéro de téléphone valide");
          input.classList.remove("input-saisie-alerte");
        }
      }
      input.addEventListener("input", maj);
      maj();
    });
  }

  /* Validation des liens réseaux sociaux (Site web, Facebook, Instagram) */
  function initReseauxSociaux() {
    var site = champ("id_site_web");
    var fb = champ("id_facebook");
    var insta = champ("id_instagram");

    function relierLabelLien(input, labelId, nomReseau) {
      if (!input) return;
      var label = document.getElementById(labelId);
      if (!label) return;
      var texteBase = nomReseau || label.textContent.replace(' 🔗', '').trim();
      function majLabel() {
        var v = (input.value || "").trim();
        if (v && /^https?:\/\//i.test(v)) {
          label.innerHTML = '<a href="' + v + '" target="_blank" rel="noopener" class="lien-label-actif" title="Ouvrir le lien ' + texteBase + ' dans un nouvel onglet">' + texteBase + ' 🔗</a>';
        } else {
          label.textContent = texteBase + (texteBase.endsWith(":") ? "" : " :");
        }
      }
      input.addEventListener("input", majLabel);
      majLabel();
    }

    function validerUrl(input, type, regexMotCle, exemple, labelNom) {
      if (!input) return;
      var el = indicateur(input);
      function maj() {
        var v = (input.value || "").trim();
        if (!v) {
          vide(el);
          input.classList.remove("input-saisie-alerte");
          return;
        }
        // Vérification format URL général
        var isUrl = /^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(v);
        if (!isUrl) {
          majEtat(el, false, "L'adresse doit commencer par https:// ou http://");
          input.classList.add("input-saisie-alerte");
          return;
        }
        if (regexMotCle && !regexMotCle.test(v)) {
          majEtat(el, false, "Doit être un lien vers " + labelNom + " (" + exemple + ")");
          input.classList.add("input-saisie-alerte");
          return;
        }
        majEtat(el, true, "Lien " + labelNom + " valide");
        input.classList.remove("input-saisie-alerte");
      }
      input.addEventListener("input", maj);
      maj();
    }

    validerUrl(site, "site", null, "https://mon-domaine.fr", "votre site web");
    validerUrl(fb, "facebook", /(facebook\.com|fb\.com|fb\.me)/i, "https://www.facebook.com/votrepage", "Facebook");
    validerUrl(insta, "instagram", /(instagram\.com)/i, "https://www.instagram.com/votrecompte", "Instagram");

    relierLabelLien(site, "label_site_web", "Site web officiel");
    relierLabelLien(fb, "label_facebook", "Page Facebook");
    relierLabelLien(insta, "label_instagram", "Compte Instagram");

    // Contrôle du logo externe avec contour orange si url invalide
    var logo = champ("id_logo_externe");
    if (logo) {
      validerUrl(logo, "logo", null, "https://mon-site.fr/logo.png", "votre logo");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initEmail();
    initTelephone();
    initUsername();
    initMotDePasse1();
    initMotDePasse2();
    initReseauxSociaux();
  });
})();
