// static/js/auto-translate.js
class AutoTranslator {
    constructor() {
        this.translations = {};
        this.currentLang = 'fr';
        this.init();
    }
    
    async init() {
        // Charger les traductions
        await this.loadTranslations();
        
        // Détecter la langue
        this.detectLanguage();
        
        // Si anglais, traduire
        if (this.currentLang === 'en') {
            this.translatePage();
        }
        
        // Écouter les changements de langue
        this.setupEventListeners();
    }
    
    async loadTranslations() {
        try {
            const response = await fetch('/api/translations');
            if (response.ok) {
                this.translations = await response.json();
                console.log(`🌐 ${Object.keys(this.translations).length} traductions chargées`);
            }
        } catch (error) {
            console.warn('⚠️ Impossible de charger les traductions, utilisation du cache local');
            this.loadFromCache();
        }
    }
    
    loadFromCache() {
        // Traductions essentielles
        this.translations = {
            // Navigation
            "Tableau de bord": "Dashboard",
            "Gestion des risques": "Risk Management",
            "Audit": "Audit",
            "Paramètres": "Settings",
            "Utilisateurs": "Users",
            "Déconnexion": "Logout",
            "Connexion": "Login",
            "Menu": "Menu",
            
            // Actions
            "Enregistrer": "Save",
            "Modifier": "Edit",
            "Supprimer": "Delete",
            "Ajouter": "Add",
            "Rechercher": "Search",
            "Filtrer": "Filter",
            "Exporter": "Export",
            "Importer": "Import",
            
            // Messages
            "Opération réussie": "Operation successful",
            "Erreur": "Error",
            "Succès": "Success",
            "Attention": "Warning",
            "Information": "Information",
            
            // Statuts
            "Actif": "Active",
            "Inactif": "Inactive",
            "Terminé": "Completed",
            "En cours": "In Progress",
            "En attente": "Pending",
            
            // Ajoutez plus selon votre CSV...
        };
    }
    
    detectLanguage() {
        // Depuis l'URL
        const urlParams = new URLSearchParams(window.location.search);
        const lang = urlParams.get('lang');
        if (lang && (lang === 'fr' || lang === 'en')) {
            this.currentLang = lang;
            this.setCookie('lang', lang, 7);
            return;
        }
        
        // Depuis les cookies
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'lang' && (value === 'fr' || value === 'en')) {
                this.currentLang = value;
                return;
            }
        }
        
        // Par défaut
        this.currentLang = 'fr';
    }
    
    setCookie(name, value, days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = `${name}=${value};expires=${date.toUTCString()};path=/`;
    }
    
    translateText(text) {
        if (this.currentLang === 'fr' || !text || typeof text !== 'string') {
            return text;
        }
        
        // Nettoyer le texte
        text = text.trim();
        if (!text) return text;
        
        // Traduction exacte
        if (this.translations[text]) {
            return this.translations[text];
        }
        
        // Traduction partielle (recherche insensible à la casse)
        let translated = text;
        for (const [fr, en] of Object.entries(this.translations)) {
            const regex = new RegExp(fr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
            if (regex.test(translated)) {
                translated = translated.replace(regex, en);
            }
        }
        
        return translated !== text ? translated : text;
    }
    
    translatePage() {
        console.log('🌐 Traduction de la page en cours...');
        
        // Éléments à traduire
        const selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'p', 'span', 'a', 'button', 'label',
            'th', 'td', 'li',
            'div.title', 'div.label', 'div.header',
            'nav a', '.navbar a', '.nav-link',
            '.btn', '.card-title', '.modal-title'
        ].join(', ');
        
        const elements = document.querySelectorAll(selectors);
        console.log(`🔍 ${elements.length} éléments trouvés`);
        
        let translatedCount = 0;
        
        elements.forEach(element => {
            // Éviter certains éléments
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || 
                element.tagName === 'CODE' || element.tagName === 'PRE' ||
                element.classList.contains('no-translate')) {
                return;
            }
            
            // Traduire le texte principal
            const original = element.textContent;
            const translated = this.translateText(original);
            
            if (translated !== original) {
                element.setAttribute('data-original-text', original);
                element.textContent = translated;
                translatedCount++;
            }
            
            // Traduire les attributs
            this.translateAttributes(element);
        });
        
        // Traduire les placeholders
        document.querySelectorAll('input[placeholder], textarea[placeholder]').forEach(el => {
            const original = el.getAttribute('placeholder');
            const translated = this.translateText(original);
            if (translated !== original) {
                el.setAttribute('data-original-placeholder', original);
                el.setAttribute('placeholder', translated);
                translatedCount++;
            }
        });
        
        // Traduire les titres
        const originalTitle = document.title;
        const translatedTitle = this.translateText(originalTitle);
        if (translatedTitle !== originalTitle) {
            document.title = translatedTitle;
            translatedCount++;
        }
        
        // Traduire les tooltips
        document.querySelectorAll('[title]').forEach(el => {
            const original = el.getAttribute('title');
            const translated = this.translateText(original);
            if (translated !== original) {
                el.setAttribute('data-original-title', original);
                el.setAttribute('title', translated);
                translatedCount++;
            }
        });
        
        console.log(`✅ ${translatedCount} éléments traduits`);
    }
    
    translateAttributes(element) {
        const attributes = ['title', 'alt', 'aria-label', 'data-tooltip'];
        
        attributes.forEach(attr => {
            if (element.hasAttribute(attr)) {
                const original = element.getAttribute(attr);
                const translated = this.translateText(original);
                if (translated !== original) {
                    element.setAttribute(`data-original-${attr}`, original);
                    element.setAttribute(attr, translated);
                }
            }
        });
    }
    
    setupEventListeners() {
        // Boutons de changement de langue
        document.addEventListener('click', (e) => {
            const langBtn = e.target.closest('[data-lang]');
            if (langBtn) {
                e.preventDefault();
                const lang = langBtn.getAttribute('data-lang');
                this.changeLanguage(lang);
            }
        });
        
        // Observer les changements du DOM (pour les pages dynamiques)
        if (typeof MutationObserver !== 'undefined') {
            this.observer = new MutationObserver((mutations) => {
                if (this.currentLang === 'en') {
                    this.translatePage();
                }
            });
            
            this.observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    }
    
    changeLanguage(lang) {
        if (lang !== 'fr' && lang !== 'en') return;
        
        this.currentLang = lang;
        this.setCookie('lang', lang, 7);
        
        if (lang === 'en') {
            this.translatePage();
        } else {
            this.restoreOriginalText();
        }
        
        // Mettre à jour l'URL sans recharger
        const url = new URL(window.location);
        url.searchParams.set('lang', lang);
        window.history.pushState({}, '', url);
        
        // Émettre un événement
        document.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang } }));
        
        console.log(`🌍 Langue changée: ${lang}`);
    }
    
    restoreOriginalText() {
        // Restaurer le texte original
        document.querySelectorAll('[data-original-text]').forEach(el => {
            el.textContent = el.getAttribute('data-original-text');
            el.removeAttribute('data-original-text');
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
        
        // Restaurer le titre de la page
        if (document.title.includes('[EN]')) {
            document.title = document.title.replace('[EN] ', '');
        }
    }
}

// Initialiser quand la page est chargée
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.translator = new AutoTranslator();
    });
} else {
    window.translator = new AutoTranslator();
}