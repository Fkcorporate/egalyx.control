"""
egalyx/formation_visuels.py — identité visuelle de la formation à la conformité : une couleur et une illustration
originale (SVG dessiné pour Egalyx, sans image externe) par thème. Utilisé pour les couvertures des modules.
"""
from markupsafe import Markup

THEMES = {
    #  code               couleur    couleur claire  icône Font Awesome
    'controle_interne': ('#1D4ED8', '#60A5FA', 'fa-diagram-project'),
    'lcb_ft':           ('#0F766E', '#5EEAD4', 'fa-magnifying-glass-dollar'),
    'anticorruption':   ('#B45309', '#FCD34D', 'fa-hand-holding-dollar'),
    'donnees':          ('#4338CA', '#A5B4FC', 'fa-user-shield'),
    'cyber':            ('#6D28D9', '#C4B5FD', 'fa-shield-halved'),
    'ethique':          ('#BE185D', '#F9A8D4', 'fa-scale-balanced'),
    'autre':            ('#334155', '#94A3B8', 'fa-book-open'),
}

# Chaque dessin : viewBox 400 × 240, blanc translucide sur le dégradé de la couverture.
_DESSINS = {
    'controle_interne': '''
  <g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M118 84 H178 M222 84 H282 M200 106 V138 M200 182 V196" opacity=".55"/>
    <rect x="64" y="62" width="54" height="44" rx="10" fill="#fff" fill-opacity=".14"/>
    <rect x="178" y="62" width="44" height="44" rx="22" fill="#fff" fill-opacity=".22"/>
    <rect x="282" y="62" width="54" height="44" rx="10" fill="#fff" fill-opacity=".14"/>
    <path d="M200 138 L236 160 L200 182 L164 160 Z" fill="#fff" fill-opacity=".14"/>
    <path d="M78 84 l9 9 l17 -18" stroke-width="4"/>
    <path d="M296 84 l9 9 l17 -18" stroke-width="4"/>
    <circle cx="200" cy="208" r="11" fill="#fff" fill-opacity=".35"/>
  </g>''',
    'lcb_ft': '''
  <g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <ellipse cx="120" cy="170" rx="38" ry="11" fill="#fff" fill-opacity=".12"/>
    <path d="M82 170 v-16 M158 170 v-16" opacity=".7"/>
    <ellipse cx="120" cy="154" rx="38" ry="11" fill="#fff" fill-opacity=".18"/>
    <path d="M82 154 v-16 M158 154 v-16" opacity=".7"/>
    <ellipse cx="120" cy="138" rx="38" ry="11" fill="#fff" fill-opacity=".26"/>
    <path d="M176 120 C 210 90, 240 90, 252 104" stroke-dasharray="2 9" opacity=".8"/>
    <circle cx="282" cy="118" r="44" fill="#fff" fill-opacity=".14" stroke-width="5"/>
    <path d="M314 150 L350 186" stroke-width="10"/>
    <path d="M270 104 h22 a8 8 0 0 1 0 16 h-14 a8 8 0 0 0 0 16 h22 M282 96 v8 M282 136 v8" stroke-width="3.5"/>
  </g>''',
    'anticorruption': '''
  <g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <rect x="92" y="104" width="112" height="82" rx="8" fill="#fff" fill-opacity=".14"/>
    <rect x="84" y="86" width="128" height="22" rx="6" fill="#fff" fill-opacity=".22"/>
    <path d="M148 86 V186"/>
    <path d="M148 86 C 128 58, 104 70, 120 86 M148 86 C 168 58, 192 70, 176 86"/>
    <circle cx="282" cy="132" r="56" fill="#fff" fill-opacity=".12" stroke-width="7"/>
    <path d="M243 171 L321 93" stroke-width="7"/>
    <circle cx="282" cy="132" r="18" stroke-width="3.5" opacity=".7"/>
  </g>''',
    'donnees': '''
  <g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M106 52 h78 l26 26 v112 a8 8 0 0 1 -8 8 h-96 a8 8 0 0 1 -8 -8 v-130 a8 8 0 0 1 8 -8 z" fill="#fff" fill-opacity=".14"/>
    <path d="M184 52 v26 h26" opacity=".8"/>
    <circle cx="146" cy="104" r="13" fill="#fff" fill-opacity=".3"/>
    <path d="M122 142 c 4 -16 44 -16 48 0" />
    <path d="M118 164 h56 M118 178 h40" opacity=".6"/>
    <rect x="252" y="118" width="84" height="70" rx="12" fill="#fff" fill-opacity=".2"/>
    <path d="M268 118 v-18 a26 26 0 0 1 52 0 v18" stroke-width="6"/>
    <circle cx="294" cy="148" r="8" fill="#fff"/>
    <path d="M294 156 v14" stroke-width="5"/>
  </g>''',
    'cyber': '''
  <g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <rect x="70" y="72" width="132" height="92" rx="10" fill="#fff" fill-opacity=".14"/>
    <path d="M70 80 L136 126 L202 80" />
    <path d="M136 30 V92 a20 20 0 1 1 -20 20" stroke-width="5"/>
    <path d="M116 112 l-8 -10" stroke-width="5"/>
    <path d="M270 52 l50 18 v42 c0 34 -22 56 -50 70 c-28 -14 -50 -36 -50 -70 v-42 z" fill="#fff" fill-opacity=".18" stroke-width="4"/>
    <path d="M252 118 l13 13 l25 -27" stroke-width="5"/>
  </g>''',
    'ethique': '''
  <g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M200 48 V194 M156 194 h88" stroke-width="4"/>
    <path d="M112 78 H288" stroke-width="4"/>
    <circle cx="200" cy="64" r="9" fill="#fff" fill-opacity=".5"/>
    <path d="M112 78 L84 140 h56 z M288 78 L260 140 h56 z" opacity=".8"/>
    <path d="M84 140 a28 14 0 0 0 56 0 z M260 140 a28 14 0 0 0 56 0 z" fill="#fff" fill-opacity=".22"/>
    <path d="M300 34 h52 a8 8 0 0 1 8 8 v26 a8 8 0 0 1 -8 8 h-30 l-14 12 v-12 h-8 a8 8 0 0 1 -8 -8 v-26 a8 8 0 0 1 8 -8 z"
          fill="#fff" fill-opacity=".2"/>
    <path d="M318 55 h26" opacity=".8"/>
  </g>''',
    'autre': '''
  <g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M200 70 C 170 56, 128 56, 100 66 V184 C 128 174, 170 174, 200 188 Z" fill="#fff" fill-opacity=".14"/>
    <path d="M200 70 C 230 56, 272 56, 300 66 V184 C 272 174, 230 174, 200 188 Z" fill="#fff" fill-opacity=".22"/>
    <path d="M122 96 h52 M122 116 h52 M226 96 h52 M226 116 h40" opacity=".6"/>
  </g>''',
}


def theme(categorie):
    c = THEMES.get(categorie) or THEMES['autre']
    return {'couleur': c[0], 'clair': c[1], 'icone': c[2], 'code': categorie if categorie in THEMES else 'autre'}


def illustration(categorie, classe=''):
    """SVG décoratif (aria-hidden) à poser sur un fond de la couleur du thème."""
    dessin = _DESSINS.get(categorie) or _DESSINS['autre']
    return Markup(f'<svg class="{classe}" viewBox="0 0 400 240" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
                  f'focusable="false">{dessin}</svg>')


def enregistrer(app):
    app.jinja_env.globals['formation_theme'] = theme
    app.jinja_env.globals['formation_illustration'] = illustration
