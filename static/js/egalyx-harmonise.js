/* Egalyx — interface harmonisée : mise à plat des pages qui ont leur propre style.
   Chargé seulement en « Interface harmonisée ». Ne change que l'affichage (classes CSS), jamais les données.
   1. Bandeaux et tuiles en dégradé → fond clair à plat (texte foncé), petits éléments → couleur unie.
   2. Pastilles d'état (« En cours », « En retard », « Terminé »…) → la même écriture partout : forme + couleur.
   3. Ombres portées décoratives retirées. */
(function () {
  'use strict';
  var IGNORER = '.progress, canvas, svg, .matrice, .matrix, .heatmap, .risk-matrix, .risk-cell, .cellule, .cell-matrice, ' +
    '.legende, .legend, .gauge, .jauge, [data-garder-style], .eg-chat, .navbar, .sidebar-container, .select2-container';
  var ETATS = [
    ['retard', /^(en retard|retard|retardée?s?|échue?s?|en dépassement|dépassée?)$/i],
    ['valider', /^(à valider|en validation|en attente de validation|soumise?|demande de clôture|clôture demandée|à approuver|en revue)$/i],
    ['encours', /^(en cours|en_cours|démarrée?|ouverte?|en traitement|en action)$/i],
    ['termine', /^(terminée?s?|clôturée?s?|close?|réalisée?s?|achevée?|validée?|fermée?|résolue?|traitée?|conforme)$/i],
    ['annule', /^(annulée?|suspendue?|abandonnée?|archivée?)$/i],
    ['afaire', /^(à faire|a faire|a_faire|planifiée?|en attente|non démarrée?|nouveau|nouvelle|brouillon|prévue?)$/i]
  ];

  function rgb(chaine) {
    var m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/.exec(chaine || '');
    if (m) { return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] }; }
    var h = /#([0-9a-f]{6}|[0-9a-f]{3})\b/i.exec(chaine || '');
    if (!h) { return null; }
    var x = h[1].length === 3 ? h[1].replace(/./g, '$&$&') : h[1];
    return { r: parseInt(x.slice(0, 2), 16), g: parseInt(x.slice(2, 4), 16), b: parseInt(x.slice(4, 6), 16), a: 1 };
  }
  function clair(c) { return c && (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255 > 0.8; }
  function foncePlein(c) { return c && c.a > 0.6 && (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255 < 0.55; }

  function aplatir(racine) {
    var main = document.querySelector('main') || document.body;
    var largeur = main.getBoundingClientRect().width || window.innerWidth;
    var haut = main.getBoundingClientRect().top + window.scrollY;
    var elements = racine.querySelectorAll('*');
    for (var i = 0; i < elements.length; i++) {
      var el = elements[i];
      if (el.dataset.egH || el.closest(IGNORER)) { continue; }
      el.dataset.egH = '1';
      var cs = getComputedStyle(el);
      if (cs.display === 'none') { continue; }
      if (/georgia|times|serif/i.test(cs.fontFamily) && !/sans-serif/i.test(cs.fontFamily) && !el.matches('code, pre, kbd, samp')) {
        el.style.setProperty('font-family', 'Inter, system-ui, sans-serif', 'important');   // une seule police partout
      }
      var styleEcrit = el.getAttribute('style') || '';
      var degrade = (cs.backgroundImage && cs.backgroundImage.indexOf('gradient') !== -1) || styleEcrit.indexOf('gradient') !== -1;
      var fond = rgb(cs.backgroundColor);
      var texteClair = clair(rgb(cs.color));
      var b = el.getBoundingClientRect();
      var dejaPlat = el.parentElement && el.parentElement.closest('.eg-plat');
      if ((cs.webkitBackgroundClip || cs.backgroundClip) === 'text') { el.classList.add('eg-texte-plat'); continue; }
      if (degrade && el.matches('thead, thead tr, thead th, tr, th')) { el.classList.add('eg-thead'); continue; }
      var bandeauPossible = !dejaPlat && b.width >= 0.55 * largeur && b.height >= 56 && (b.top + window.scrollY - haut) < 360 &&
        !el.matches('.card-header, .fk-card-header, .modal-header, .modal-content, thead, tr, th, td, .table, .btn');
      if (degrade || (bandeauPossible && texteClair && foncePlein(fond))) {
        el.style.setProperty('background-image', 'none', 'important');
        if (bandeauPossible) {
          el.classList.add('eg-plat', 'eg-bandeau');
        } else if (!dejaPlat && (texteClair || el.querySelector('.text-white')) && b.width >= 110 && b.height >= 44 && !el.matches('.btn, .badge')) {
          el.classList.add('eg-plat');
          // la couleur d'origine de la tuile reste en repère discret à gauche (rouge = critique, orange = retard…)
          var r = rgb(cs.backgroundImage) || rgb(styleEcrit);
          if (r && (0.299 * r.r + 0.587 * r.g + 0.114 * r.b) / 255 > 0.25) {
            el.style.setProperty('box-shadow', 'inset 3px 0 0 rgb(' + r.r + ',' + r.g + ',' + r.b + ')', 'important');
          }
        } else if (degrade) {
          // petit élément (pastille, icône, avatar) : teinte claire de la couleur d'origine, icône dans cette couleur
          var c = rgb(cs.backgroundImage) || rgb(styleEcrit);
          el.classList.add('eg-teinte');
          el.style.setProperty('background-image', 'none', 'important');
          if (c && el.matches('.btn, [class*="btn-"], button') && (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255 < 0.75) {
            // bouton en dégradé : couleur unie (la première du dégradé), texte blanc conservé
            el.style.setProperty('background-color', 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')', 'important');
            el.style.setProperty('border-color', 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')', 'important');
          } else if (c) {
            var plein = 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')';
            el.style.setProperty('background-color', 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',.12)', 'important');
            el.style.setProperty('color', plein, 'important');
            el.querySelectorAll('i, svg, span').forEach(function (x) { x.style.setProperty('color', plein, 'important'); });
          }
        }
        continue;
      }
      // en-tête de carte coloré (fond plein, texte blanc) qui n'a pas la classe card-header
      if (texteClair && fond && fond.a > 0.6 && !clair(fond) && el.parentElement && el === el.parentElement.firstElementChild &&
          el.parentElement.matches('.card, .fk-card, [class*="card"], [class*="box"], [class*="panel"]') &&
          b.width >= 0.6 * el.parentElement.getBoundingClientRect().width && b.height <= 90 && !el.matches('.btn, .badge, .nav-link')) {
        el.classList.add('eg-entete-carte');
        continue;
      }
      if (cs.boxShadow && cs.boxShadow !== 'none' && !el.matches('.dropdown-menu, .modal-content, .popover, .tooltip, .toast, input, select, textarea, .form-control, .form-select')) {
        el.style.setProperty('box-shadow', 'none', 'important');
      }
    }
    contraste(racine);
    var pastilles = racine.querySelectorAll('.badge, .fk-badge, .badge-modern, .statut-badge, .status-badge, .badge-statut');
    for (var j = 0; j < pastilles.length; j++) {
      var p = pastilles[j];
      if (p.classList.contains('etat-h') || p.closest('[data-garder-style]')) { continue; }
      var texte = (p.textContent || '').replace(/\s+/g, ' ').trim();
      if (!texte || texte.length > 32) { continue; }
      for (var k = 0; k < ETATS.length; k++) {
        if (ETATS[k][1].test(texte)) {
          p.classList.add('etat-h', ETATS[k][0]);
          var icone = p.querySelector('i');
          if (icone) { icone.style.display = 'none'; }
          break;
        }
      }
    }
  }

  // Filet de sécurité : texte clair resté sur un fond devenu clair → texte foncé (ou gris pour les sous-titres)
  function fondEffectif(el) {
    for (var x = el; x && x !== document.documentElement; x = x.parentElement) {
      var c = rgb(getComputedStyle(x).backgroundColor);
      if (c && c.a > 0.5) { return c; }
      if (getComputedStyle(x).backgroundImage.indexOf('gradient') !== -1) { return null; }
    }
    return { r: 243, g: 245, b: 248, a: 1 };
  }
  function contraste(racine) {
    var tous = racine.querySelectorAll('*');
    for (var i = 0; i < tous.length; i++) {
      var el = tous[i];
      if (el.dataset.egC || el.closest(IGNORER + ', .badge, .navbar, .dropdown-menu')) { continue; }
      el.dataset.egC = '1';
      var cs = getComputedStyle(el);
      if (!clair(rgb(cs.color))) { continue; }
      var aDuTexte = el.tagName === 'I' || el.tagName === 'svg' || Array.prototype.some.call(el.childNodes, function (n) {
        return n.nodeType === 3 && n.textContent.trim();
      });
      if (!aDuTexte) { continue; }
      var fond = fondEffectif(el);
      if (fond && clair(fond)) {
        var discret = el.matches('.text-white-50, .text-white-75, small, .small, i') || parseFloat(cs.opacity) < 1;
        el.classList.add(discret ? 'eg-contraste-discret' : 'eg-contraste');
        el.style.setProperty('color', discret ? '#5D6B7C' : '#14202E', 'important');   // l'emporte sur toute règle de la page
      }
    }
  }

  function lancer() {
    if (!document.documentElement.classList.contains('ui-h')) { return; }
    aplatir(document.querySelector('main') || document.body);
    document.querySelectorAll('.modal').forEach(function (m) { aplatir(m); });
  }
  var attente = null;
  function plusTard() { clearTimeout(attente); attente = setTimeout(lancer, 120); }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', lancer); } else { lancer(); }
  window.addEventListener('load', plusTard);
  document.addEventListener('shown.bs.modal', plusTard);
  document.addEventListener('shown.bs.tab', plusTard);
  // listes chargées après coup (filtres, pagination, tableaux dynamiques)
  try {
    new MutationObserver(function (changes) {
      for (var i = 0; i < changes.length; i++) { if (changes[i].addedNodes.length) { plusTard(); return; } }
    }).observe(document.body, { childList: true, subtree: true });
  } catch (e) { /* navigateur ancien : la page reste lisible */ }
})();
