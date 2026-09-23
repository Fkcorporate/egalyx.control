"""
Service de génération SVG pour les logigrammes
Version professionnelle avec gestion des sauts de page
"""

class LogigrammeSVGService:
    """Génère un SVG propre et vectoriel pour le logigramme"""
    
    COULEURS = {
        'debut':        {'c1': '#10b981', 'c2': '#059669', 'text': '#ffffff'},
        'action':       {'c1': '#3b82f6', 'c2': '#2563eb', 'text': '#ffffff'},
        'controle':     {'c1': '#f59e0b', 'c2': '#d97706', 'text': '#ffffff'},
        'risque':       {'c1': '#ef4444', 'c2': '#dc2626', 'text': '#ffffff'},
        'fin':          {'c1': '#6b7280', 'c2': '#4b5563', 'text': '#ffffff'},
        'titre':        {'c1': '#ffffff', 'c2': '#f8fafc', 'text': '#1e293b'},
        'organisation': {'c1': '#1e293b', 'c2': '#0f172a', 'text': '#ffffff'},
    }
    
    # 🔥 FIX : Séparateur beaucoup plus fin
    SEPARATEUR_WIDTH = 2       # ← était 4
    SEPARATEUR_MIN_HEIGHT = 80
    
    # 🔥 FIX : Taille max d'une page SVG (en pixels)
    PAGE_MAX_WIDTH = 1600
    PAGE_MAX_HEIGHT = 1000
    
    @classmethod
    def generer_svg(cls, elements, liens, padding=30):
        """
        Génère un SVG vectoriel propre
        🔥 FIX : Ajuste les dimensions pour que tout rentre
        """
        if not elements:
            return cls._svg_vide(), {'width': 400, 'height': 100}
        
        # 🔥 FIX : Normaliser les séparateurs avant calcul
        cls._normaliser_separateurs(elements)
        
        bounds = cls._calculer_bounds(elements)
        
        # 🔥 FIX : Calculer les dimensions en respectant les limites de page
        content_width = bounds['maxX'] - bounds['minX']
        content_height = bounds['maxY'] - bounds['minY']
        
        # Taille finale avec padding
        width = content_width + 2 * padding
        height = content_height + 2 * padding
        
        # Limiter à la taille max d'une page
        max_w = cls.PAGE_MAX_WIDTH
        max_h = cls.PAGE_MAX_HEIGHT
        
        # Si trop grand, on scale
        if width > max_w or height > max_h:
            scale_w = max_w / width if width > max_w else 1
            scale_h = max_h / height if height > max_h else 1
            scale = min(scale_w, scale_h)
            
            width = int(width * scale)
            height = int(height * scale)
        
        viewBox = f"{bounds['minX'] - padding} {bounds['minY'] - padding} {content_width + 2*padding} {content_height + 2*padding}"
        
        svg_parts = []
        svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewBox}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;max-width:100%;display:block;">')
        
        svg_parts.append(cls._generer_defs())
        
        # Liens
        for lien in liens:
            source = next((e for e in elements if e.id == lien.element_source_id), None)
            cible = next((e for e in elements if e.id == lien.element_cible_id), None)
            if source and cible:
                svg_parts.append(cls._dessiner_lien(source, cible, lien))
        
        # Éléments
        for element in elements:
            svg_parts.append(cls._dessiner_element(element))
        
        svg_parts.append('</svg>')
        
        return ''.join(svg_parts), {'width': width, 'height': height}
    
    @classmethod
    def _normaliser_separateurs(cls, elements):
        """
        🔥 FIX : Force la largeur des séparateurs à une valeur fixe très fine
        """
        for el in elements:
            if el.type_element == 'organisation':
                # Forcer dans le style
                if not el.style:
                    el.style = {}
                el.style['width'] = cls.SEPARATEUR_WIDTH
                
                # Hauteur minimum
                current_h = el.style.get('height') or el.height or 200
                if current_h < cls.SEPARATEUR_MIN_HEIGHT:
                    el.style['height'] = cls.SEPARATEUR_MIN_HEIGHT
                
                # 🔥 FIX : Retirer le libellé "Séparateur" par défaut
                if el.libelle and el.libelle.strip().lower() in ('séparateur', 'separateur', 'separator', ''):
                    el.libelle = ''  # ← Vide = pas de label affiché
    
    @classmethod
    def _calculer_bounds(cls, elements):
        minX, minY = float('inf'), float('inf')
        maxX, maxY = float('-inf'), float('-inf')
        
        for el in elements:
            w, h = cls._get_dimensions(el)
            x, y = el.position_x or 0, el.position_y or 0
            minX = min(minX, x)
            minY = min(minY, y)
            maxX = max(maxX, x + w)
            maxY = max(maxY, y + h)
        
        return {
            'minX': int(minX),
            'minY': int(minY),
            'maxX': int(maxX),
            'maxY': int(maxY)
        }
    
    @classmethod
    def _get_dimensions(cls, element):
        """Retourne (width, height) — séparateur forcé à SEPARATEUR_WIDTH"""
        style = element.style or {}
        
        if element.type_element == 'organisation':
            # 🔥 FIX : Toujours utiliser SEPARATEUR_WIDTH
            w = cls.SEPARATEUR_WIDTH
            h = style.get('height') or getattr(element, 'height', None) or 200
            return int(w), int(h)
        
        default_w = 200 if element.type_element == 'titre' else 120
        default_h = 60 if element.type_element == 'titre' else 70
        
        w = style.get('width') if 'width' in style else (getattr(element, 'width', None) or default_w)
        h = style.get('height') if 'height' in style else (getattr(element, 'height', None) or default_h)
        
        return int(w), int(h)
    
    @classmethod
    def _generer_defs(cls):
        return '''
            <defs>
                <marker id="arrow-normal" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">
                    <polygon points="0 0, 10 5, 0 10" fill="#94a3b8"/>
                </marker>
                <marker id="arrow-oui" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">
                    <polygon points="0 0, 10 5, 0 10" fill="#10b981"/>
                </marker>
                <marker id="arrow-non" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">
                    <polygon points="0 0, 10 5, 0 10" fill="#ef4444"/>
                </marker>
            </defs>
        '''
    
    @classmethod
    def _dessiner_lien(cls, source, cible, lien):
        sw, sh = cls._get_dimensions(source)
        cw, ch = cls._get_dimensions(cible)
        
        sx, sy = source.position_x or 0, source.position_y or 0
        cx, cy = cible.position_x or 0, cible.position_y or 0
        
        scx, scy = sx + sw / 2, sy + sh / 2
        ccx, ccy = cx + cw / 2, cy + ch / 2
        
        dx = ccx - scx
        dy = ccy - scy
        
        if abs(dx) > abs(dy):
            if dx > 0:
                x1, y1 = sx + sw, scy
                x2, y2 = cx, ccy
            else:
                x1, y1 = sx, scy
                x2, y2 = cx + cw, ccy
        else:
            if dy > 0:
                x1, y1 = scx, sy + sh
                x2, y2 = ccx, cy
            else:
                x1, y1 = scx, sy
                x2, y2 = ccx, cy + ch
        
        type_lien = 'normal'
        if lien.style and isinstance(lien.style, dict):
            type_lien = lien.style.get('type', 'normal')
        elif lien.type_lien:
            type_lien = lien.type_lien
        
        couleurs = {'oui': '#10b981', 'non': '#ef4444', 'normal': '#94a3b8'}
        color = couleurs.get(type_lien, '#94a3b8')
        dash = 'stroke-dasharray="8 4"' if type_lien == 'non' else ''
        
        parts = []
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2.5" fill="none" {dash} marker-end="url(#arrow-{type_lien})" />')
        
        if type_lien in ('oui', 'non'):
            midX = (x1 + x2) / 2
            midY = (y1 + y2) / 2
            label = '✓ OUI' if type_lien == 'oui' else '✗ NON'
            parts.append(f'<text x="{midX}" y="{midY - 8}" fill="{color}" font-size="11" font-weight="700" text-anchor="middle" font-family="Arial, sans-serif">{label}</text>')
        
        return ''.join(parts)
    
    @classmethod
    def _dessiner_element(cls, element):
        w, h = cls._get_dimensions(element)
        x = element.position_x or 0
        y = element.position_y or 0
        type_el = element.type_element
        
        parts = []
        parts.append('<g>')
        
        # 🔥 FIX : SÉPARATEUR — ligne fine SANS label si vide
        if type_el == 'organisation':
            # Rectangle ultra fin (pas de rx → angle droit)
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#1e293b" rx="0"/>')
            
            # 🔥 FIX : N'afficher le label QUE si non vide et non par défaut
            libelle = (element.libelle or '').strip()
            if libelle and libelle.lower() not in ('séparateur', 'separateur', 'separator'):
                parts.append(f'<text x="{x + w + 10}" y="{y + h/2}" fill="#1e293b" font-size="11" font-weight="600" dominant-baseline="middle" font-family="Arial, sans-serif">{cls._escape(libelle)}</text>')
        else:
            colors = cls.COULEURS.get(type_el, {'c1': '#94a3b8', 'c2': '#64748b', 'text': '#ffffff'})
            gradient_id = f"grad-{element.id}"
            
            parts.append(f'''<linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="{colors['c1']}"/>
                <stop offset="100%" stop-color="{colors['c2']}"/>
            </linearGradient>''')
            
            rx = '35' if type_el in ('debut', 'fin') else '8'
            stroke = 'stroke="#e2e8f0" stroke-width="2"' if type_el == 'titre' else ''
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{gradient_id})" rx="{rx}" {stroke}/>')
            
            text_color = colors['text']
            has_desc = bool(element.description)
            title_y = y + h/2 + (-5 if has_desc else 5)
            font_size = "14" if type_el == "titre" else "12"
            
            libelle = cls._tronquer(element.libelle or "", 30)
            
            parts.append(f'<text x="{x + w/2}" y="{title_y}" fill="{text_color}" font-size="{font_size}" font-weight="600" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif">{cls._escape(libelle)}</text>')
            
            if has_desc:
                desc = cls._tronquer(cls._escape(element.description), 30)
                parts.append(f'<text x="{x + w/2}" y="{y + h/2 + 12}" fill="{text_color}" font-size="10" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" opacity="0.85">{desc}</text>')
        
        parts.append('</g>')
        return ''.join(parts)
    
    @classmethod
    def _tronquer(cls, text, max_len):
        if len(text) > max_len:
            return text[:max_len-3] + '...'
        return text
    
    @classmethod
    def _escape(cls, text):
        if not text:
            return ''
        return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;')
        )
    
    @classmethod
    def _svg_vide(cls):
        return '''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100" viewBox="0 0 400 100">
            <text x="200" y="50" text-anchor="middle" font-family="Arial" font-size="14" fill="#94a3b8">Aucun élément dans ce logigramme</text>
        </svg>'''
    @classmethod
    def calculer_strategie_affichage(cls, svg_width, svg_height):
        """
        🔥 Calcule la stratégie d'affichage optimale
        Retourne un dict avec toutes les infos nécessaires au template
        """
        # Dimensions utiles d'une page A4 (en pixels à 96 DPI)
        # Avec marges 0.8cm et en-têtes :
        A4_PORTRAIT_W = 720
        A4_PORTRAIT_H = 1000
        A4_LANDSCAPE_W = 1000
        A4_LANDSCAPE_H = 720
        
        # Hauteur approximative consommée par :
        # - En-tête : 80px
        # - Statistiques : 100px
        # - Tableau risques : 150px
        # - Pied de page : 40px
        HEADER_HEIGHT = 80
        STATS_HEIGHT = 100
        TABLE_HEIGHT = 150
        FOOTER_HEIGHT = 40
        
        ratio = svg_width / svg_height
        
        # Choisir l'orientation
        if ratio > 1.3:
            page_w, page_h = A4_LANDSCAPE_W, A4_LANDSCAPE_H
            orientation = 'landscape'
        else:
            page_w, page_h = A4_PORTRAIT_W, A4_PORTRAIT_H
            orientation = 'portrait'
        
        # Hauteur disponible pour le diagramme
        available_height = page_h - HEADER_HEIGHT - STATS_HEIGHT - TABLE_HEIGHT - FOOTER_HEIGHT
        available_height = max(available_height, 400)
        
        # Calculer le débordement
        ratio_w = svg_width / page_w
        ratio_h = svg_height / available_height
        max_ratio = max(ratio_w, ratio_h)
        
        # Décision
        if max_ratio <= 1.0:
            return {
                'pages': 1,
                'scale': 1.0,
                'mode': 'single',
                'orientation': orientation,
                'page_w': page_w,
                'page_h': page_h,
                'available_height': available_height
            }
        elif max_ratio <= 1.5:
            scale = 1.0 / max_ratio
            scale = max(scale, 0.65)
            return {
                'pages': 1,
                'scale': scale,
                'mode': 'single',
                'orientation': orientation,
                'page_w': page_w,
                'page_h': page_h,
                'available_height': available_height
            }
        else:
            return {
                'pages': 2,
                'scale': 0.75,
                'mode': 'split',
                'orientation': 'landscape' if svg_width > svg_height else 'portrait',
                'page_w': page_w,
                'page_h': page_h,
                'available_height': available_height
            }
