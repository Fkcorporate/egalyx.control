import os, re, json
from playwright.sync_api import sync_playwright
from captures_v4 import local
os.makedirs('captures', exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--allow-file-access-from-files'])
    def ouvrir(f, w=1400, h=1000):
        fp = os.path.abspath('captures/' + f); open(fp, 'w').write(local(open('rendu/' + f).read()))
        pg = b.new_page(viewport={'width': w, 'height': h}); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.route(re.compile(r".*/api/recherche.*"), lambda r: r.fulfill(status=200, content_type='application/json',
                 body=json.dumps({'resultats': [{'type': 'Risque', 'titre': 'Blanchiment de capitaux via les comptes clients', 'sous_titre': 'R-BQ-004', 'url': '/r/4'},
                                                {'type': 'Tiers', 'titre': 'Sahara Trading FZE', 'sous_titre': 'TRS-0004', 'url': '/t/4'}]})))
        pg.goto('file://' + fp); pg.wait_for_timeout(400)
        return pg, errs
    pg, errs = ouvrir('egalyx__rapport_comite.html', 1000, 1300)
    pages = pg.locator('.page')
    print('rapport : pages =', pages.count(), 'erreurs JS =', errs)
    for i in (1, 2):
        pages.nth(i).screenshot(path=f'captures/rapport_p{i + 1}.png')
    pg.emulate_media(media='print'); pg.pdf(path='captures/rapport.pdf', format='A4', print_background=True)
    pg.close()
    pg, errs = ouvrir('egalyx__bibliotheque.html')
    pg.keyboard.press('Control+k'); pg.keyboard.type('blanch'); pg.wait_for_timeout(500)
    print('palette : résultats =', pg.locator('.rg-item').count(), 'erreurs JS =', errs)
    pg.screenshot(path='captures/recherche.png'); pg.keyboard.press('Escape'); pg.close()
    pg, errs = ouvrir('egalyx__ma_semaine.html'); pg.screenshot(path='captures/ma_semaine.png'); print('ma semaine', errs); pg.close()
    b.close()
