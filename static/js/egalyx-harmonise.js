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
      var dejaPlat = el.parentElement && el.parentElement.closest('.eg-plat, .eg-bandeau, .pg-entete');
      var dansBande = el.parentElement && el.parentElement.closest('.eg-bandeau, .pg-entete');
      if ((cs.webkitBackgroundClip || cs.backgroundClip) === 'text') { el.classList.add('eg-texte-plat'); continue; }
      if (degrade && el.matches('thead, thead tr, thead th, tr, th')) { el.classList.add('eg-thead'); continue; }
      var bandeauPossible = !dejaPlat && b.width >= 0.55 * largeur && b.height >= 56 && (b.top + window.scrollY - haut) < 360 &&
        !el.matches('.card-header, .fk-card-header, .modal-header, .modal-content, thead, tr, th, td, .table, .btn');
      if (degrade || (bandeauPossible && texteClair && foncePlein(fond))) {
        el.style.setProperty('background-image', 'none', 'important');
        if (dansBande && !el.matches('.btn, [class*="btn-"], .badge')) {
          el.classList.add('eg-dans-bande');            // tuile ou pastille posée dans la bande de titre
        } else if (bandeauPossible) {
          el.classList.add('eg-bandeau');
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
      var couleur = rgb(cs.color);
      if (couleur && !clair(couleur) && (0.299 * couleur.r + 0.587 * couleur.g + 0.114 * couleur.b) / 255 < 0.4) {
        var f0 = fondEffectif(el);
        if (f0 && (0.299 * f0.r + 0.587 * f0.g + 0.114 * f0.b) / 255 < 0.3 && el.closest('.eg-bandeau, .pg-entete')) {
          el.style.setProperty('color', '#FFFFFF', 'important');      // texte foncé posé sur la bande marine
        }
        continue;
      }
      if (!clair(couleur)) { continue; }
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

  // Page sans bande de titre : l'en-tête qui porte le premier grand titre devient la bande
  function bandeTitre(main) {
    if (!main || main.querySelector('.eg-bandeau, .pg-entete')) { return; }
    var haut = main.getBoundingClientRect().top, h = null;
    var titres = main.querySelectorAll('h1, h2, h3, h4, .h1, .h2, .h3, .h4, .page-title');
    for (var i = 0; i < titres.length && !h; i++) {
      var t = titres[i];
      if (t.getBoundingClientRect().top - haut > 320) { break; }
      if (t.closest('.modal, table, form, .dropdown-menu, .alert') || !t.getBoundingClientRect().height) { continue; }
      var carte = t.closest('.card, .fk-card, .eg-plat');
      if (carte) {
        // carte d'en-tête (titre de la page, quelques boutons) : elle devient la bande
        var rc = carte.getBoundingClientRect();
        if (rc.top - haut < 200 && rc.height <= 300 && !carte.querySelector('table, canvas, input:not([type=hidden]), select, textarea')
            && carte.getBoundingClientRect().width >= 0.55 * main.getBoundingClientRect().width && !t.closest('.card-header, .fk-card-header')) {
          carte.classList.add('eg-bandeau');
          return;
        }
        continue;
      }
      h = t;
    }
    if (!h) {
      // titre dans l'en-tête de la première carte : cet en-tête devient la bande
      var tete = main.querySelector('.card-header, .fk-card-header');
      if (tete && !tete.closest('.modal, .dropdown-menu') && tete.getBoundingClientRect().height
          && tete.getBoundingClientRect().top - haut < 200 && tete.querySelector('h1, h2, h3, h4, h5, .h3, .h4, .h5, .card-title')
          && tete.getBoundingClientRect().width >= 0.55 * main.getBoundingClientRect().width && !tete.querySelector('.nav-tabs, .nav-pills')) {
        tete.classList.add('eg-bandeau', 'eg-bandeau-tete');
      }
      return;
    }
    // largeur de référence : la colonne de la page (pages étroites et centrées), sinon toute la zone principale
    var largeurMain = main.getBoundingClientRect().width, choisi = h;
    for (var a = h.parentElement; a && a !== main; a = a.parentElement) {
      var la = a.getBoundingClientRect().width;
      if (la >= 0.4 * main.getBoundingClientRect().width && (getComputedStyle(a).maxWidth !== 'none' || a.matches('[class*="container"], [class*="col-lg-"], [class*="col-md-"], [class*="col-xl-"]'))) {
        largeurMain = la; break;
      }
    }
    for (var x = h.parentElement; x && x !== main && !x.matches('main, .container-fluid > .row, body'); x = x.parentElement) {
      var r = x.getBoundingClientRect();
      if (r.height > 240 || x.querySelector('table, canvas, .card, .fk-card, form .form-control, .row .col-md-3')) { break; }
      choisi = x;
      if (r.width >= 0.55 * largeurMain && x.querySelector('.btn, .breadcrumb, p, small') ) { break; }
    }
    if (choisi.getBoundingClientRect().width < 0.55 * largeurMain) { return; }
    if (choisi === h && h.parentElement && h.parentElement.querySelector('.card, .fk-card, form, table')) {
      // titre posé seul dans la colonne : on le regroupe avec son lien de retour et son sous-titre
      var petit = function (e) {
        return e && e.nodeType === 1 && !e.matches('.card, .fk-card, form, table, .row, .alert, script, style, .modal')
          && !e.querySelector('.card, form, table, input, select, textarea, canvas') && e.getBoundingClientRect().height < 90;
      };
      var groupe = [h], e2;
      for (e2 = h.previousElementSibling; petit(e2) && groupe.length < 4; e2 = e2.previousElementSibling) { groupe.unshift(e2); }
      for (e2 = h.nextElementSibling; petit(e2) && groupe.length < 5; e2 = e2.nextElementSibling) { groupe.push(e2); }
      var bande = document.createElement('div');
      bande.className = 'eg-bandeau eg-bandeau-cree';
      h.parentElement.insertBefore(bande, groupe[0]);
      groupe.forEach(function (x) { bande.appendChild(x); });
      return;
    }
    choisi.classList.add('eg-bandeau');
  }

  // Graphiques (Chart.js) : même police, mêmes couleurs de texte et de grille que le reste
  function graphiques() {
    var C = window.Chart;
    if (!C || !C.version || parseInt(C.version, 10) < 3) { return; }      // Chart.js 2 : on n'y touche pas
    try {
      if (C.defaults && C.defaults.font) {
        C.defaults.font.family = 'Inter, system-ui, sans-serif'; C.defaults.color = '#5D6B7C'; C.defaults.borderColor = '#EDF1F5';
      }
      var liste = C.instances ? (Array.isArray(C.instances) ? C.instances : Object.values(C.instances)) : [];
      var objet = function (o, k) { if (!o[k] || typeof o[k] !== 'object') { o[k] = {}; } return o[k]; };
      var police = { family: 'Inter, system-ui, sans-serif', size: 12 };
      liste.forEach(function (g) {
        if (!g.config || !g.config.options) { return; }
        var o = g.config.options;                 // options écrites par la page (pas les options calculées)
        var type = g.config.type || '';
        try {
          var legende = objet(objet(o, 'plugins'), 'legend'), etiquettes = objet(legende, 'labels');
          etiquettes.usePointStyle = true; etiquettes.boxWidth = 8; etiquettes.boxHeight = 8; etiquettes.color = '#5D6B7C'; etiquettes.font = police;
          var bulle = objet(o.plugins, 'tooltip');
          bulle.backgroundColor = '#0B1F3A'; bulle.titleColor = '#FFFFFF'; bulle.bodyColor = '#E2E8F0'; bulle.cornerRadius = 6; bulle.padding = 10;
          Object.keys(o.scales || {}).forEach(function (k) {
            var sc = o.scales[k];
            if (!sc || typeof sc !== 'object' || Array.isArray(sc)) { return; }
            objet(sc, 'grid').color = '#EDF1F5';
            objet(sc, 'border').color = '#DDE3EA';
            var tk = objet(sc, 'ticks'); tk.color = '#5D6B7C'; tk.font = { family: police.family, size: 11 };
          });
          ((g.config.data && g.config.data.datasets) || []).forEach(function (d) {
            if (/doughnut|pie|polar/.test(type)) { d.borderColor = '#FFFFFF'; d.borderWidth = 2; d.hoverOffset = 4; }
            if (/bar/.test(type)) { d.borderRadius = 4; d.borderSkipped = false; }
            if (/line/.test(type)) { d.borderWidth = 2; if (d.pointRadius !== 0) { d.pointRadius = 3; } }
          });
          if (/doughnut|pie/.test(type) && !o.cutout) { o.cutout = '62%'; }
          g.update('none');
        } catch (e) { /* un graphique particulier reste comme il était */ }
      });
    } catch (e) { /* Chart.js absent ou ancien */ }
  }

  function lancer() {
    if (!document.documentElement.classList.contains('ui-h')) { return; }
    aplatir(document.querySelector('main') || document.body);
    bandeTitre(document.querySelector('main'));
    document.querySelectorAll('main .eg-bandeau, main .pg-entete').forEach(function (b) {
      b.querySelectorAll('[data-eg-c]').forEach(function (x) { delete x.dataset.egC; });
      contraste(b);                                      // la bande a changé les couleurs : on revérifie dedans
    });
    document.querySelectorAll('.modal').forEach(function (m) { aplatir(m); });
  }
  var attente = null;
  function plusTard() { clearTimeout(attente); attente = setTimeout(lancer, 120); }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', lancer); } else { lancer(); }
  window.addEventListener('load', function () { plusTard(); setTimeout(graphiques, 300); setTimeout(graphiques, 1500); });
  document.addEventListener('shown.bs.modal', plusTard);
  document.addEventListener('shown.bs.tab', plusTard);
  // listes chargées après coup (filtres, pagination, tableaux dynamiques)
  try {
    new MutationObserver(function (changes) {
      for (var i = 0; i < changes.length; i++) { if (changes[i].addedNodes.length) { plusTard(); return; } }
    }).observe(document.body, { childList: true, subtree: true });
  } catch (e) { /* navigateur ancien : la page reste lisible */ }
})();
