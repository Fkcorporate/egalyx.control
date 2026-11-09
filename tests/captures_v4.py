"""Captures d'écran des pages v4 rendues par test_v4_rendu.py + test interactif de l'éditeur d'organigramme."""
import json, os, re
from playwright.sync_api import sync_playwright
M = '/usr/local/lib/python3.13/dist-packages/mkdocs/themes/mkdocs'
def local(html):
    html = re.sub(r'<link[^>]+href="https://cdn\.jsdelivr\.net/npm/bootstrap@[^"]+/css/bootstrap\.min\.css"[^>]*>', f'<link rel="stylesheet" href="file://{M}/css/bootstrap.min.css">', html)
    html = re.sub(r'<link[^>]+href="https://cdnjs\.cloudflare\.com/ajax/libs/font-awesome[^"]+"[^>]*>', f'<link rel="stylesheet" href="file://{M}/css/fontawesome.min.css"><link rel="stylesheet" href="file://{M}/css/solid.min.css">', html)
    return html
os.makedirs('captures', exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--allow-file-access-from-files'])
    for f in ('egalyx__tiers_detail.html', 'egalyx__organigramme_editeur.html', 'egalyx__parametres_risque.html', 'egalyx__signature.html'):
        fp = os.path.abspath('captures/' + f); open(fp, 'w').write(local(open('rendu/' + f).read()))
        pg = b.new_page(viewport={'width': 1400, 'height': 1000}); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        envois = []
        if 'organigramme' in f:
            pg.route(re.compile(r".*/api/processus/9/organigramme$"), lambda r: (envois.append(json.loads(r.request.post_data)),
                     r.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'etapes': 3, 'liens': 3, 'donnees': envois[-1]}))))
        pg.goto('file://' + fp); pg.wait_for_timeout(500)
        if 'organigramme' in f:
            # glisser l'étape 3 vers le bas, relier 3 -> 1, enregistrer
            n3 = pg.locator('#gNoeuds g').nth(2); bb = n3.bounding_box()
            pg.mouse.move(bb['x'] + 20, bb['y'] + 20); pg.mouse.down(); pg.mouse.move(bb['x'] + 20, bb['y'] + 220, steps=8); pg.mouse.up()
            pg.click('#btnLien'); pg.locator('#gNoeuds g').nth(2).click(); pg.locator('#gNoeuds g').nth(0).click(); pg.click('#btnLien')
            etat_avant = pg.inner_text('#etat')
            pg.click('#btnEnregistrer'); pg.wait_for_timeout(400)
            e = envois[-1] if envois else None
            print('éditeur : état avant =', etat_avant, '| après =', pg.inner_text('#etat'))
            print('   étape 3 y =', [x['y'] for x in e['etapes'] if x['id'] == 3], '| liens =', [(l['source'], l['cible']) for l in e['liens']])
            pg.click('#btnLien')  # quitte proprement
        pg.screenshot(path='captures/' + f.replace('.html', '.png'), full_page=False)
        print(f, 'erreurs JS :', [x for x in errs if 'bootstrap' not in x.lower()][:3])
        pg.close()
    b.close()
