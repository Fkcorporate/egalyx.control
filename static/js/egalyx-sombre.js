/* Egalyx — lisibilité en MODE SOMBRE (interface actuelle et interface harmonisée).
   Beaucoup de pages ont leurs propres couleurs écrites pour le mode clair : cartes blanches, titres bleu marine…
   En mode sombre, le texte général devient clair : on obtient du clair sur blanc ou du foncé sur fond sombre.
   Ce script ne fait rien en mode clair. En mode sombre, il vérifie chaque texte visible et, s'il se lit mal :
     - grand bloc resté clair (carte, encadré, ligne de tableau) → le bloc passe en surface sombre ;
     - petit élément clair (pastille, bouton, code)             → il garde son fond, le texte passe en foncé ;
     - texte foncé ou trop pâle sur fond sombre                  → texte éclairci (même teinte s'il est coloré).
   Tout ce qu'il change est noté et rétabli dès que l'on repasse en mode clair. Il ne touche jamais aux données. */
(function () {
  'use strict';
  var IGNORER = 'svg, canvas, video, img, picture, iframe, script, style, noscript, input, select, textarea, option, ' +
    '#editeur-logigramme, .minimap, .oc-vue, .ed-cadre, .orga-cadre, [data-garder-style], [data-garder-couleurs], ' +
    '.select2-container, .eg-chat, .leaflet-container, .apexcharts-canvas, .cot-matrice, .matrice, .heatmap, .risk-matrix';
  var PETIT = 'button, .btn, .badge, [class*="badge"], [class*="pill"], [class*="tag"], [class*="chip"], [class*="statut"], ' +
    '[class*="status"], code, kbd, mark, samp, .progress, .etat-h, .cot-badge, .cot-pastille, label.btn';
  var SURFACE = '#1E293B', SURFACE_RGB = { r: 30, g: 41, b: 59 }, TEXTE = '#E2E8F0', TEXTE_FONCE = '#14202E';
  var MARQUE = 'egSombre';
  var touches = [];                                   // éléments modifiés, pour tout rétablir en mode clair

  function sombre() { return document.documentElement.getAttribute('data-bs-theme') === 'dark'; }
  function rgb(s) {
    var m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/.exec(s || '');
    return m ? { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] } : null;
  }
  function couleurs(s) {
    var re = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/g, m, l = [];
    while ((m = re.exec(s || ''))) { l.push({ r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] }); }
    return l;
  }
  function lin(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
  function lum(c) { return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b); }
  function ecart(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function clair(c) { return lum(c) > 0.35; }
  function vif(c) { return Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b) > 45; }
  function css(c) { return 'rgb(' + Math.round(c.r) + ',' + Math.round(c.g) + ',' + Math.round(c.b) + ')'; }
  // même teinte, éclaircie jusqu'à être lisible sur le fond
  function eclaircir(c, fond) {
    for (var t = 0.15; t <= 1.001; t += 0.05) {
      var x = { r: c.r + (255 - c.r) * t, g: c.g + (255 - c.g) * t, b: c.b + (255 - c.b) * t };
      if (ecart(x, fond) >= 4.5) { return css(x); }
    }
    return TEXTE;
  }
  function assombrir(c, fond) {
    for (var t = 0.15; t <= 1.001; t += 0.05) {
      var x = { r: c.r * (1 - t), g: c.g * (1 - t), b: c.b * (1 - t) };
      if (ecart(x, fond) >= 4.5) { return css(x); }
    }
    return TEXTE_FONCE;
  }

  function poser(el, prop, valeur) {
    if (!el.dataset[MARQUE]) { el.dataset[MARQUE] = JSON.stringify({}); touches.push(el); }
    var avant = JSON.parse(el.dataset[MARQUE]);
    if (!(prop in avant)) { avant[prop] = [el.style.getPropertyValue(prop), el.style.getPropertyPriority(prop)]; }
    el.dataset[MARQUE] = JSON.stringify(avant);
    el.style.setProperty(prop, valeur, 'important');
  }
  function retablir() {
    touches.forEach(function (el) {
      try {
        var avant = JSON.parse(el.dataset[MARQUE] || '{}');
        Object.keys(avant).forEach(function (p) {
          if (avant[p][0]) { el.style.setProperty(p, avant[p][0], avant[p][1]); } else { el.style.removeProperty(p); }
        });
      } catch (e) { /* élément retiré de la page */ }
      delete el.dataset[MARQUE];
    });
    touches = [];
  }

  // fond réellement visible derrière un élément : les couches semi-transparentes sont composées entre elles.
  // « el » = la couche qui porte le fond (la plus haute assez couvrante), celle qu'on assombrira si besoin.
  function fond(el) {
    var couches = [], degrade = false;
    for (var x = el; x && x.nodeType === 1; x = x.parentElement) {
      var cs = getComputedStyle(x);
      if (cs.backgroundImage && cs.backgroundImage.indexOf('gradient') !== -1) {
        var l = couleurs(cs.backgroundImage).filter(function (c) { return c.a >= 0.5; });
        if (l.length) {
          var m = l.reduce(function (s, c) { return { r: s.r + c.r / l.length, g: s.g + c.g / l.length, b: s.b + c.b / l.length, a: 1 }; }, { r: 0, g: 0, b: 0, a: 1 });
          couches.push({ c: m, el: x }); degrade = couches.length === 1; break;
        }
      }
      var c = rgb(cs.backgroundColor);
      if (c && c.a > 0.02) { couches.push({ c: c, el: x }); if (c.a >= 0.95) { break; } }
    }
    if (!couches.length || couches[couches.length - 1].c.a < 0.95) { couches.push({ c: { r: 15, g: 23, b: 42, a: 1 }, el: document.body }); }
    var res = couches[couches.length - 1].c;
    for (var i = couches.length - 2; i >= 0; i--) {
      var k = couches[i].c, a = k.a;
      res = { r: k.r * a + res.r * (1 - a), g: k.g * a + res.g * (1 - a), b: k.b * a + res.b * (1 - a), a: 1 };
    }
    var porteur = couches.filter(function (q) { return q.c.a >= 0.3; })[0] || couches[couches.length - 1];
    return { c: res, el: porteur.el, propre: porteur.c, degrade: degrade && porteur === couches[0] };
  }
  function aDuTexte(el) {
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3 && n.textContent.trim().length > 0) { return true; }
    }
    return el.tagName === 'I' && el.className && /\bfa/.test(el.className);   // icônes Font Awesome
  }

  function verifier(racine) {
    // un bloc assombri peut rendre illisible un texte déjà vérifié : on repasse tant qu'un bloc change (3 fois au plus)
    for (var tour = 0; tour < 3 && passe(racine); tour++) { /* rien */ }
  }
  function passe(racine) {
    if (!sombre()) { return false; }
    var blocs = 0;
    var tous = (racine || document.body).querySelectorAll('*');
    for (var i = 0; i < tous.length; i++) {
      var el = tous[i];
      if (!aDuTexte(el) || el.closest(IGNORER)) { continue; }
      var cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.3) { continue; }
      var fg = rgb(cs.color);
      if (!fg) { continue; }
      var f = fond(el);
      if (ecart(fg, f.c) >= 3) { continue; }                                  // déjà lisible
      // fond intermédiaire créé par un voile clair (blanc à 50 %…) sur un fond sombre : le voile passe en surface sombre
      var voile = !clair(f.c) && lum(f.c) > 0.08 && f.propre && f.propre.a < 0.95 && clair(f.propre) && f.el !== document.body
        && !f.el.matches(PETIT) && !f.el.closest(PETIT);
      if (clair(f.c) || voile) {
        var porteur = f.el, r = porteur.getBoundingClientRect();
        var grand = porteur !== document.body && r.width >= 160 && r.height >= 30 && !porteur.matches(PETIT) && !porteur.closest(PETIT);
        if (grand) {
          // bloc resté clair (carte, encadré…) : il passe en surface sombre
          poser(porteur, 'background-color', SURFACE); blocs++;
          if (f.degrade) { poser(porteur, 'background-image', 'none'); }
          if (porteur.matches('.card, [class*="card"], [class*="box"], [class*="panel"], [class*="carte"], .alert, [class*="alert"], table, tr, td, th, li')) {
            poser(porteur, 'border-color', 'rgba(255,255,255,.10)');
          }
          f = { c: SURFACE_RGB };
          if (ecart(fg, f.c) >= 3) { continue; }
          poser(el, 'color', vif(fg) ? eclaircir(fg, f.c) : TEXTE);
        } else {
          // petit élément pâle (pastille, bouton…) : on garde son fond, le texte devient foncé
          poser(el, 'color', vif(fg) ? assombrir(fg, f.c) : TEXTE_FONCE);
        }
      } else {
        poser(el, 'color', vif(fg) ? eclaircir(fg, f.c) : TEXTE);
      }
    }
    return blocs > 0;
  }

  var attente = null;
  function plusTard() { clearTimeout(attente); attente = setTimeout(function () { verifier(document.body); }, 150); }
  function demarrer() {
    verifier(document.body);
    window.addEventListener('load', plusTard);
    document.addEventListener('shown.bs.modal', plusTard);
    document.addEventListener('shown.bs.tab', plusTard);
    document.addEventListener('shown.bs.collapse', plusTard);
    try {
      new MutationObserver(function (ch) {
        for (var i = 0; i < ch.length; i++) { if (ch[i].addedNodes.length) { plusTard(); return; } }
      }).observe(document.body, { childList: true, subtree: true });
      // bascule clair ↔ sombre : on rétablit tout, puis on revérifie si on est en sombre
      new MutationObserver(function () { retablir(); if (sombre()) { setTimeout(function () { verifier(document.body); }, 60); } })
        .observe(document.documentElement, { attributes: true, attributeFilter: ['data-bs-theme'] });
    } catch (e) { /* navigateur ancien */ }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', demarrer); } else { demarrer(); }
})();
