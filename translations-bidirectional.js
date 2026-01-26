// translations-bidirectional.js
class BidirectionalTranslator {
    constructor() {
        this.currentLang = this.detectLanguage();
        this.translationsToEn = {};  // FR → EN
        this.translationsToFr = {};  // EN → FR
        this.originalTexts = new Map();  // Stocke les textes originaux
        this.initialized = false;
        
        console.log('🌐 Traducteur bidirectionnel - Langue actuelle:', this.currentLang);
        
        this.init();
    }
    
    detectLanguage() {
        // 1. URL parameter (highest priority)
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');
        if (urlLang && ['fr', 'en'].includes(urlLang)) {
            return urlLang;
        }
        
        // 2. Local storage
        const storedLang = localStorage.getItem('app_lang');
        if (storedLang && ['fr', 'en'].includes(storedLang)) {
            return storedLang;
        }
        
        // 3. Cookie
        const cookieLang = document.cookie
            .split('; ')
            .find(row => row.startsWith('lang='))
            ?.split('=')[1];
        if (cookieLang && ['fr', 'en'].includes(cookieLang)) {
            return cookieLang;
        }
        
        // 4. Default to French
        return 'fr';
    }
    
    async init() {
        await this.loadTranslations();
        
        // Apply translation if needed
        if (this.currentLang === 'en') {
            this.translatePageToEnglish();
        }
        
        this.setupEventListeners();
        this.initialized = true;
        
        console.log('✅ Traducteur initialisé');
    }
    
    async loadTranslations() {
        try {
            const response = await fetch('/api/translations/data');
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.translations) {
                    // Create both direction dictionaries
                    Object.entries(data.translations).forEach(([french, english]) => {
                        this.translationsToEn[french] = english;
                        this.translationsToFr[english] = french;
                    });
                    
                    console.log(`📦 ${Object.keys(this.translationsToEn).length} traductions chargées (bidirectionnel)`);
                }
            }
        } catch (error) {
            console.warn('⚠️ Impossible de charger les traductions:', error);
            // Fallback to hardcoded translations
            this.loadFallbackTranslations();
        }
    }
    
    loadFallbackTranslations() {
        const fallback = {
            "Tableau de bord": "Dashboard",
            "Gestion des risques": "Risk Management",
            "Cartographie": "Cartography",
            "KRI Indicators": "Indicateurs KRI",
            "Regulatory Watch": "Veille règlementaire",
            "Flowcharts": "Logigrammes",
            "Internal Audit": "Audit Interne",
            "Questionnaires": "Questionnaires",
            "Administration": "Administration",
            "Paramètres": "Settings",
            "Utilisateurs": "Users",
            "Déconnexion": "Logout",
            "Quick Actions": "Actions rapides",
            "Configuration": "Configuration",
            "Notifications": "Notifications",
            "Client View": "Vue Client",
            "Profile": "Profil",
            "Super Admin": "Super Administrateur",
            "Client Management": "Gestion Clients",
            "Subscription Plans": "Formules d'abonnement",
            "All Users": "Tous les Utilisateurs"
        };
        
        Object.entries(fallback).forEach(([french, english]) => {
            this.translationsToEn[french] = english;
            this.translationsToFr[english] = french;
        });
    }
    
    translatePageToEnglish() {
        console.log('🔧 Traduction vers anglais...');
        
        // Store original texts before translation
        this.storeOriginalTexts();
        
        // Translate texts
        this.translateTexts('en');
        
        // Translate attributes
        this.translateAttributes('en');
        
        // Update document language
        document.documentElement.lang = 'en';
        
        console.log('✅ Page traduite en anglais');
    }
    
    restoreToFrench() {
        console.log('🔧 Restauration vers français...');
        
        // Restore texts from stored originals
        this.restoreOriginalTexts();
        
        // Restore attributes
        this.restoreAttributes();
        
        // Update document language
        document.documentElement.lang = 'fr';
        
        console.log('✅ Page restaurée en français');
    }
    
    storeOriginalTexts() {
        const selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'p', 'span', 'label',
            'th', 'td',
            '.card-title', '.card-header', '.card-text',
            '.modal-title', '.modal-body p',
            '.alert', '.badge',
            'legend',
            '.sidebar-heading',
            '.nav-link:not(.dropdown-toggle)',
            'button:not(.lang-btn):not(.lang-btn-simple)',
            '.btn:not(.lang-btn):not(.lang-btn-simple)',
            '.dropdown-item',
            '.navbar-brand span',
            '.sidebar-menu-expanded .nav-link',
            '.sidebar-menu-compact .logo-tooltip'
        ].join(', ');
        
        document.querySelectorAll(selectors).forEach(element => {
            const text = element.textContent.trim();
            if (text && text.length > 1) {
                this.originalTexts.set(element, text);
            }
        });
    }
    
    restoreOriginalTexts() {
        this.originalTexts.forEach((originalText, element) => {
            element.textContent = originalText;
        });
        this.originalTexts.clear();
    }
    
    translateTexts(targetLang) {
        const selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'p', 'span', 'label',
            'th', 'td',
            '.card-title', '.card-header', '.card-text',
            '.modal-title', '.modal-body p',
            '.alert', '.badge',
            'legend',
            '.sidebar-heading',
            '.nav-link:not(.dropdown-toggle)',
            'button:not(.lang-btn):not(.lang-btn-simple)',
            '.btn:not(.lang-btn):not(.lang-btn-simple)',
            '.dropdown-item',
            '.navbar-brand span',
            '.sidebar-menu-expanded .nav-link',
            '.sidebar-menu-compact .logo-tooltip'
        ].join(', ');
        
        document.querySelectorAll(selectors).forEach(element => {
            const text = element.textContent.trim();
            if (text && text.length > 1) {
                const translated = this.translate(text, targetLang);
                if (translated !== text) {
                    element.textContent = translated;
                }
            }
        });
    }
    
    translateAttributes(targetLang) {
        // Placeholders
        document.querySelectorAll('[placeholder]').forEach(el => {
            const original = el.getAttribute('placeholder');
            if (original) {
                const translated = this.translate(original, targetLang);
                if (translated !== original) {
                    el.setAttribute('data-original-placeholder', original);
                    el.setAttribute('placeholder', translated);
                }
            }
        });
        
        // Titles
        document.querySelectorAll('[title]').forEach(el => {
            const original = el.getAttribute('title');
            if (original) {
                const translated = this.translate(original, targetLang);
                if (translated !== original) {
                    el.setAttribute('data-original-title', original);
                    el.setAttribute('title', translated);
                }
            }
        });
        
        // Alt text
        document.querySelectorAll('[alt]').forEach(el => {
            const original = el.getAttribute('alt');
            if (original) {
                const translated = this.translate(original, targetLang);
                if (translated !== original) {
                    el.setAttribute('data-original-alt', original);
                    el.setAttribute('alt', translated);
                }
            }
        });
        
        // Page title
        const pageTitle = document.title;
        const translatedTitle = this.translate(pageTitle, targetLang);
        if (translatedTitle && translatedTitle !== pageTitle) {
            document.title = translatedTitle;
        }
    }
    
    restoreAttributes() {
        // Restore placeholders
        document.querySelectorAll('[data-original-placeholder]').forEach(el => {
            el.setAttribute('placeholder', el.getAttribute('data-original-placeholder'));
            el.removeAttribute('data-original-placeholder');
        });
        
        // Restore titles
        document.querySelectorAll('[data-original-title]').forEach(el => {
            el.setAttribute('title', el.getAttribute('data-original-title'));
            el.removeAttribute('data-original-title');
        });
        
        // Restore alt text
        document.querySelectorAll('[data-original-alt]').forEach(el => {
            el.setAttribute('alt', el.getAttribute('data-original-alt'));
            el.removeAttribute('data-original-alt');
        });
    }
    
    translate(text, targetLang) {
        if (!text || typeof text !== 'string') {
            return text;
        }
        
        const trimmed = text.trim();
        if (!trimmed) return text;
        
        if (targetLang === 'en') {
            // Translate from French to English
            if (this.translationsToEn[trimmed]) {
                return this.translationsToEn[trimmed];
            }
            
            // Try partial matches
            for (const [french, english] of Object.entries(this.translationsToEn)) {
                if (trimmed.includes(french)) {
                    return trimmed.replace(new RegExp(french, 'g'), english);
                }
            }
        } else if (targetLang === 'fr') {
            // Translate from English to French
            if (this.translationsToFr[trimmed]) {
                return this.translationsToFr[trimmed];
            }
            
            // Try partial matches
            for (const [english, french] of Object.entries(this.translationsToFr)) {
                if (trimmed.includes(english)) {
                    return trimmed.replace(new RegExp(english, 'g'), french);
                }
            }
        }
        
        return text;
    }
    
    switchLanguage(lang) {
        if (!['fr', 'en'].includes(lang) || lang === this.currentLang) {
            return;
        }
        
        console.log(`🔄 Changement de langue: ${this.currentLang} → ${lang}`);
        
        // Save preference
        this.savePreference(lang);
        
        // Apply translation
        if (lang === 'en') {
            this.translatePageToEnglish();
        } else {
            this.restoreToFrench();
        }
        
        // Update current language
        this.currentLang = lang;
        
        // Update UI
        this.updateLanguageWidget();
        
        // Show notification
        this.showNotification(lang);
        
        // Refresh dynamic content
        this.refreshDynamicContent();
    }
    
    savePreference(lang) {
        localStorage.setItem('app_lang', lang);
        document.cookie = `lang=${lang};path=/;max-age=31536000`;
        
        // Update URL without reloading
        const url = new URL(window.location);
        url.searchParams.set('lang', lang);
        window.history.replaceState({}, '', url);
    }
    
    updateLanguageWidget() {
        const btnFr = document.getElementById('btnFr');
        const btnEn = document.getElementById('btnEn');
        
        if (btnFr) btnFr.classList.toggle('active', this.currentLang === 'fr');
        if (btnEn) btnEn.classList.toggle('active', this.currentLang === 'en');
    }
    
    showNotification(lang) {
        const notification = document.createElement('div');
        notification.className = 'lang-notification';
        notification.innerHTML = `
            <span>${lang === 'fr' ? '🇫🇷' : '🇬🇧'}</span>
            <span>${lang === 'fr' ? 'Langue changée en Français' : 'Language changed to English'}</span>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }
    
    refreshDynamicContent() {
        // Refresh DataTables
        if (typeof $.fn.DataTable !== 'undefined') {
            $('.data-table').DataTable().draw();
        }
        
        // Refresh notifications
        if (typeof chargerNotificationsDropdown === 'function') {
            chargerNotificationsDropdown();
        }
    }
    
    setupEventListeners() {
        // Language buttons
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.lang-btn, .lang-btn-simple');
            if (btn) {
                e.preventDefault();
                const lang = btn.id === 'btnFr' || btn.classList.contains('fr') ? 'fr' : 'en';
                this.switchLanguage(lang);
            }
        });
        
        // URL changes
        window.addEventListener('popstate', () => {
            const newLang = this.detectLanguage();
            if (newLang !== this.currentLang) {
                this.switchLanguage(newLang);
            }
        });
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.bidiTranslator = new BidirectionalTranslator();
    
    // Expose functions for buttons
    window.switchToFrench = () => window.bidiTranslator.switchLanguage('fr');
    window.switchToEnglish = () => window.bidiTranslator.switchLanguage('en');
    window.switchToLanguage = (lang) => window.bidiTranslator.switchLanguage(lang);
});