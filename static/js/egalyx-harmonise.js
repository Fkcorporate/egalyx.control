/* Egalyx — interface harmonisée : mise à plat des pages qui ont leur propre style.
   Chargé seulement en « Interface harmonisée ». Ne change que l'affichage (classes CSS), jamais les données.
   1. Bandeaux et tuiles en dégradé → fond clair à plat (texte foncé), petits éléments → couleur unie.
   2. Pastilles d'état (« En cours », « En retard », « Terminé »…) → la même écriture partout : forme + couleur.
   3. Ombres portées décoratives retirées. */
(function () {
  'use strict';
  var IGNORER = '.progress, canvas, svg, .matrice, .matrix, .heatmap, .risk-matrix, .risk-cell, .cellule, .cell-matrice, ' +
    '.legende, .legend, .gauge, .jauge, [data-garder-style], .eg-chat, .navbar, .sidebar-container, .select2-container, ' +
    // zones de dessin (logigrammes, organigrammes) : leurs formes gardent leurs couleurs, la feuille de style les met à plat
    '#editeur-logigramme, .minimap, .oc-vue, .ed-cadre, .orga-cadre, [class*="logigramme-canvas"], [class*="organigramme-canvas"]';
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
  function lum(c) { return (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255; }
  function couleurs(chaine) {
    var re = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/g, m, liste = [];
    while ((m = re.exec(chaine || ''))) { liste.push({ r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] }); }
    return liste;
  }
  // Nature d'un dégradé : « texture » (quadrillage, points : couleurs presque transparentes),
  // « clair » (fond très pâle, ex. #f8fafc → #f1f5f9) ou « fonce » (vrai bandeau coloré)
  function natureDegrade(chaine) {
    var toutes = couleurs(chaine), opaques = toutes.filter(function (c) { return c.a >= 0.35; });
    if (!toutes.length) { return 'fonce'; }
    if (!opaques.length) { return 'texture'; }
    return opaques.every(function (c) { return lum(c) > 0.8; }) ? 'clair' : 'fonce';
  }
  // Couleur qui porte le sens d'un dégradé : la plus foncée de ses couleurs opaques
  function couleurPrincipale(chaine) {
    var opaques = couleurs(chaine).filter(function (c) { return c.a >= 0.35; });
    if (!opaques.length) { return null; }
    return opaques.reduce(function (a, b) { return lum(b) < lum(a) ? b : a; });
  }
  // Couleur assez foncée pour servir de texte sur fond pâle
  function lisible(c) {
    var k = lum(c) > 0.55 ? 0.55 / lum(c) : 1;
    return 'rgb(' + Math.round(c.r * k) + ',' + Math.round(c.g * k) + ',' + Math.round(c.b * k) + ')';
  }
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
      if (degrade) {
        var nature = natureDegrade(cs.backgroundImage);
        // quadrillage ou trame de points (zone de dessin) : on n'y touche pas
        if (nature === 'texture') { continue; }
        // fond pâle en dégradé avec texte foncé : simple fond clair uni, jamais une bande marine
        if (nature === 'clair' && !texteClair) {
          var pale = couleurs(cs.backgroundImage).filter(function (c) { return c.a >= 0.35; })[0];
          el.style.setProperty('background-image', 'none', 'important');
          if (pale && !enSombre()) { el.style.setProperty('background-color', 'rgb(' + pale.r + ',' + pale.g + ',' + pale.b + ')', 'important'); }
          continue;
        }
      }
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
          var r = couleurPrincipale(cs.backgroundImage) || rgb(styleEcrit);
          if (r && lum(r) > 0.25 && lum(r) < 0.85) {
            el.style.setProperty('box-shadow', 'inset 3px 0 0 rgb(' + r.r + ',' + r.g + ',' + r.b + ')', 'important');
          }
        } else if (degrade) {
          // petit élément (pastille, icône, avatar) : teinte claire de la couleur d'origine, icône dans cette couleur
          var c = couleurPrincipale(cs.backgroundImage) || rgb(styleEcrit);
          el.classList.add('eg-teinte');
          el.style.setProperty('background-image', 'none', 'important');
          if (c && lum(c) > 0.8) {
            // dégradé très pâle : fond uni de cette couleur, le texte garde sa couleur (sinon blanc sur blanc)
            el.style.setProperty('background-color', 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')', 'important');
          } else if (el.matches('.action-btn, [class*="btn-action"], [class*="btn-icon"]')) {
            // petit bouton d'action de ligne : la feuille de style le met en blanc, texte gris (rien à poser ici)
          } else if (c && el.matches('.btn, [class*="btn-"], button') && lum(c) < 0.75) {
            // bouton en dégradé : couleur unie (la première du dégradé), texte blanc conservé
            el.style.setProperty('background-color', 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')', 'important');
            el.style.setProperty('border-color', 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')', 'important');
          } else if (c) {
            var plein = lisible(c);                       // texte toujours assez foncé sur la teinte pâle
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
  // écart de contraste (WCAG) entre deux couleurs : 1 = identiques, 21 = noir sur blanc
  function ecart(a, b) {
    var l = function (c) {
      var f = function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
    };
    var x = l(a), y = l(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  }
  // même teinte, assez foncée pour être lue sur fond clair
  function fonce(c) {
    var k = Math.min(1, 0.36 / Math.max(lum(c), 0.01));
    return 'rgb(' + Math.round(c.r * k) + ',' + Math.round(c.g * k) + ',' + Math.round(c.b * k) + ')';
  }
  function aDuTexteDirect(el) {
    return Array.prototype.some.call(el.childNodes, function (n) { return n.nodeType === 3 && n.textContent.trim(); });
  }
  function enSombre() { return document.documentElement.getAttribute('data-bs-theme') === 'dark'; }
  function contraste(racine) {
    if (enSombre()) { return; }                 // en mode sombre, c'est egalyx-sombre.js qui règle la lisibilité
    var tous = racine.querySelectorAll('*');
    for (var i = 0; i < tous.length; i++) {
      var el = tous[i];
      if (el.dataset.egC || el.closest(IGNORER + ', .navbar, .dropdown-menu')) { continue; }
      el.dataset.egC = '1';
      var cs = getComputedStyle(el);
      var couleur = rgb(cs.color);
      if (couleur && lum(couleur) < 0.45) {
        var f0 = fondEffectif(el);
        // texte foncé posé sur un fond foncé (bande marine, bouton recoloré…) : il passe en blanc si c'est plus lisible
        if (f0 && (el.closest('.eg-bandeau, .pg-entete') || aDuTexteDirect(el)) && ecart(couleur, f0) < 3 && ecart({ r: 255, g: 255, b: 255 }, f0) > ecart(couleur, f0)) {
          el.style.setProperty('color', '#FFFFFF', 'important');
        }
        continue;
      }
      if (!clair(couleur)) {
        // couleur intermédiaire (jaune, doré, cyan…) posée sur un fond clair : on la fonce en gardant sa teinte
        var f1 = couleur && aDuTexteDirect(el) ? fondEffectif(el) : null;
        if (f1 && clair(f1) && ecart(couleur, f1) < 2.2) {
          el.classList.add('eg-contraste');
          el.style.setProperty('color', Math.max(couleur.r, couleur.g, couleur.b) - Math.min(couleur.r, couleur.g, couleur.b) > 40 ? fonce(couleur) : '#14202E', 'important');
        }
        continue;
      }
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
    // retour du mode sombre au mode clair : les textes que le mode sombre laissait de côté sont revérifiés
    new MutationObserver(function () { if (!enSombre()) { plusTard(); } })
      .observe(document.documentElement, { attributes: true, attributeFilter: ['data-bs-theme'] });
  } catch (e) { /* navigateur ancien : la page reste lisible */ }
})();
