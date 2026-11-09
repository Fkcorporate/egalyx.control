import json, re
from playwright.sync_api import sync_playwright
from captures_v4 import local
html = local(open('rendu/egalyx__bibliotheque.html').read())
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--allow-file-access-from-files'])
    pg = b.new_page(viewport={'width': 1400, 'height': 900}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    def router(r):
        u = r.request.url
        if '/api/recherche' in u:
            q = re.search(r'q=([^&]*)', u).group(1)
            return r.fulfill(status=200, content_type='application/json', body=json.dumps({'resultats': [
                {'type': 'Risque', 'titre': 'Blanchiment de capitaux via les comptes clients', 'sous_titre': 'R-BQ-004', 'url': '/r/4'},
                {'type': 'Tiers', 'titre': 'Sahara Trading <b>FZE</b>', 'sous_titre': 'TRS-0004', 'url': '/t/4'}] if q.startswith('bla') else []}))
        if u.startswith('http://egalyx.test/page'):
            return r.fulfill(status=200, content_type='text/html', body=html)
        return r.abort()
    pg.route(re.compile(r"^https?://.*"), router)
    pg.goto('http://egalyx.test/page'); pg.wait_for_timeout(300)
    pg.keyboard.press('Control+k'); pg.wait_for_timeout(100); print('ouvert', pg.locator('#rgFond').evaluate("e => e.classList.contains('ouvert')")); pg.keyboard.type('blanch'); pg.wait_for_timeout(600); print('saisie', pg.input_value('#rgSaisie'), '| liste', pg.inner_html('#rgListe')[:200])
    n = pg.locator('a.rg-item').count()
    gras = pg.locator('.rg-liste b').count()   # le HTML des résultats doit être échappé
    pg.screenshot(path='captures/recherche.png')
    pg.keyboard.press('ArrowDown'); actif = pg.locator('a.rg-item.actif .rg-type').inner_text()
    pg.keyboard.press('Escape'); ferme = not pg.locator('#rgFond').evaluate("e => e.classList.contains('ouvert')")
    print('résultats', n, '| HTML injecté', gras, '| actif après ↓', actif, '| fermé par Échap', ferme, '| erreurs', errs)
    b.close()
