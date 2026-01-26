// static/js/fixed-translate.js
class FixedTranslator {
    constructor() {
        this.translations = {};
        this.currentLang = this.detectLanguage();
        this.init();
    }
    
    detectLanguage() {
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');
        if (urlLang === 'en' || urlLang === 'fr') {
            this.savePreference(urlLang);
            return urlLang;
        }
        
        return localStorage.getItem('app_lang') || 'fr';
    }
    
    savePreference(lang) {
        localStorage.setItem('app_lang', lang);
    }
    
    init() {
        console.log('🚀 Traducteur initialisé - Langue:', this.currentLang);
        
        // Charger les traductions
        this.loadTranslations();
        
        // Traduire si anglais
        if (this.currentLang === 'en') {
            setTimeout(() => this.translatePage(), 100);
        }
        
        // Événements
        this.setupEvents();
    }
    
    loadTranslations() {
        if (window.APP_TRANSLATIONS) {
            this.translations = window.APP_TRANSLATIONS;
            console.log(`✅ ${Object.keys(this.translations).length} traductions chargées`);
        }
    }
    
    shouldTranslateElement(element) {
        // Éléments à NE PAS traduire
        const skipSelectors = [
            // Liens avec URLs spécifiques
            'a[href*="/"]',
            'a[href*="."]',
            'a[href*="#"]',
            // Inputs et formulaires
            'input',
            'textarea',
            'select',
            'option',
            // Code
            'code',
            'pre',
            'kbd',
            // Scripts et styles
            'script',
            'style',
            // Images
            'img',
            // Éléments avec classes d'exclusion
            '.no-translate',
            '[data-no-translate]',
            // URLs et emails
            '[href^="http"]',
            '[href^="mailto:"]',
            '[href^="tel:"]',
            // Données JSON
            '[data-json]',
            '[data-url]'
        ];
        
        // Vérifier les sélecteurs
        for (const selector of skipSelectors) {
            if (element.matches(selector)) {
                return false;
            }
        }
        
        // Vérifier le contenu
        const text = element.textContent.trim();
        
        // Ne pas traduire les URLs
        if (text.includes('://') || 
            text.includes('www.') || 
            text.includes('.com') || 
            text.includes('.fr') ||
            text.includes('.org') ||
            text.match(/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/) ||
            text.match(/^https?:\/\//) ||
            text.match(/^\/[a-zA-Z0-9_\-/]+$/)) {
            return false;
        }
        
        // Ne pas traduire les IDs, noms de fichiers, etc.
        if (text.match(/^[A-Z_]+$/) || // CONSTANTES
            text.match(/^[a-z]+_[a-z]+$/) || // snake_case
            text.match(/^[a-z]+[A-Z][a-z]+$/) || // camelCase
            text.match(/^[A-Z][a-z]+[A-Z][a-z]+$/)) { // PascalCase
            return false;
        }
        
        return true;
    }
    
    translateText(text) {
        if (this.currentLang === 'fr' || !text || typeof text !== 'string') {
            return text;
        }
        
        text = text.trim();
        if (!text || text.length < 2) return text;
        
        // Ne pas traduire les URLs ou codes
        if (text.includes('://') || text.includes('/') || text.match(/^[.#@]/)) {
            return text;
        }
        
        // Traduction exacte
        if (this.translations[text]) {
            return this.translations[text];
        }
        
        return text;
    }
    
    translatePage() {
        console.log('🌐 Traduction sélective de la page...');
        
        // Éléments à traduire (seulement les textes purs)
        const selectors = [
            // Titres
            'h1:not(a)', 'h2:not(a)', 'h3:not(a)', 'h4:not(a)', 'h5:not(a)', 'h6:not(a)',
            // Paragraphes
            'p:not(a)',
            // Labels
            'label:not([for*="."])',
            // Boutons (sans liens)
            'button:not([href]):not([onclick*="window.location"])',
            // Spans (sauf ceux dans les liens)
            'span:not(a span):not(.no-translate)',
            // Éléments de navigation (uniquement texte)
            '.nav-text:not(a)',
            '.breadcrumb-item:not(:last-child)',
            // Cards
            '.card-title:not(a)',
            '.card-text:not(a)',
            // Modals
            '.modal-title:not(a)',
            // Alerts
            '.alert p:not(a)',
            // Badges (sans liens)
            '.badge:not(a)',
            // List items (sans liens)
            'li:not(a):not(.dropdown-item a)'
        ].join(', ');
        
        const elements = document.querySelectorAll(selectors);
        let translatedCount = 0;
        
        elements.forEach(element => {
            // Vérifier si l'élément doit être traduit
            if (!this.shouldTranslateElement(element)) {
                return;
            }
            
            const original = element.textContent.trim();
            if (!original || original.length < 2) return;
            
            const translated = this.translateText(original);
            
            if (translated && translated !== original) {
                // Vérifier que ce n'est pas une URL
                if (!translated.match(/^(http|https|ftp|mailto|tel):|\/\/|\.(com|fr|org|net|io)$/i)) {
                    element.setAttribute('data-original', original);
                    element.textContent = translated;
                    translatedCount++;
                }
            }
        });
        
        // Traduire les attributs spéciaux (avec précaution)
        this.translateAttributes();
        
        console.log(`✅ ${translatedCount} éléments traduits (sélectif)`);
    }
    
    translateAttributes() {
        // Placeholders (uniquement si ce n'est pas une URL)
        document.querySelectorAll('input[placeholder], textarea[placeholder]').forEach(el => {
            const original = el.getAttribute('placeholder');
            if (original && !original.includes('/') && !original.includes('://')) {
                const translated = this.translateText(original);
                if (translated && translated !== original) {
                    el.setAttribute('data-original-placeholder', original);
                    el.setAttribute('placeholder', translated);
                }
            }
        });
        
        // Titres (title)
        document.querySelectorAll('[title]').forEach(el => {
            const original = el.getAttribute('title');
            if (original && !original.includes('/') && !original.includes('://')) {
                const translated = this.translateText(original);
                if (translated && translated !== original) {
                    el.setAttribute('data-original-title', original);
                    el.setAttribute('title', translated);
                }
            }
        });
        
        // Titre de la page
        const pageTitle = document.title;
        if (pageTitle && !pageTitle.includes('/')) {
            const translatedTitle = this.translateText(pageTitle);
            if (translatedTitle && translatedTitle !== pageTitle) {
                document.title = translatedTitle;
            }
        }
    }
    
    setupEvents() {
        document.addEventListener('click', (e) => {
            const langBtn = e.target.closest('[data-lang]');
            if (langBtn) {
                e.preventDefault();
                const lang = langBtn.getAttribute('data-lang');
                this.switchLanguage(lang);
            }
        });
    }
    
    switchLanguage(lang) {
        if (!['fr', 'en'].includes(lang) || lang === this.currentLang) {
            return;
        }
        
        this.currentLang = lang;
        this.savePreference(lang);
        
        if (lang === 'en') {
            this.translatePage();
        } else {
            this.restoreFrench();
        }
        
        this.updateURL(lang);
    }
    
    restoreFrench() {
        // Restaurer le texte
        document.querySelectorAll('[data-original]').forEach(el => {
            el.textContent = el.getAttribute('data-original');
            el.removeAttribute('data-original');
        });
        
        // Restaurer les placeholders
        document.querySelectorAll('[data-original-placeholder]').forEach(el => {
            el.setAttribute('placeholder', el.getAttribute('data-original-placeholder'));
            el.removeAttribute('data-original-placeholder');
        });
        
        // Restaurer les titres
        document.querySelectorAll('[data-original-title]').forEach(el => {
            el.setAttribute('title', el.getAttribute('data-original-title'));
            el.removeAttribute('data-original-title');
        });
        
        console.log('🇫🇷 Texte restauré');
    }
    
    updateURL(lang) {
        const url = new URL(window.location);
        url.searchParams.set('lang', lang);
        window.history.replaceState({}, '', url);
    }
}

// Initialisation
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.fixedTranslator = new FixedTranslator();
    });
} else {
    window.fixedTranslator = new FixedTranslator();
}