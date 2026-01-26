// translations.js - Système de traduction UNIFIÉ et SIMPLE

class Translator {
    constructor() {
        this.translations = {};
        this.currentLang = 'fr';
        this.loaded = false;
    }

    // Initialiser
    async init() {
        if (this.loaded) return;
        
        // Déterminer la langue actuelle
        this.currentLang = this.getCurrentLanguage();
        console.log(`🌐 Langue initiale: ${this.currentLang}`);
        
        // Si anglais, charger les traductions
        if (this.currentLang === 'en') {
            await this.loadTranslations();
            this.translatePage();
        }
        
        this.loaded = true;
    }

    // Obtenir la langue actuelle
    getCurrentLanguage() {
        // URL paramètre
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');
        if (urlLang === 'fr' || urlLang === 'en') {
            return urlLang;
        }
        
        // LocalStorage
        const storageLang = localStorage.getItem('app_lang');
        if (storageLang === 'fr' || storageLang === 'en') {
            return storageLang;
        }
        
        // Cookie
        const cookieLang = this.getCookie('lang');
        if (cookieLang === 'fr' || cookieLang === 'en') {
            return cookieLang;
        }
        
        // Par défaut
        return 'fr';
    }

    // Charger les traductions depuis le serveur
    async loadTranslations() {
        try {
            const response = await fetch('/api/translations/all');
            const data = await response.json();
            
            if (data.success && data.translations) {
                this.translations = data.translations;
                console.log(`✅ ${data.count} traductions chargées`);
                return true;
            }
        } catch (error) {
            console.warn('⚠️ Impossible de charger les traductions:', error);
        }
        return false;
    }

    // Traduire un texte
    translate(text) {
        if (!text || this.currentLang === 'fr') {
            return text;
        }
        
        const textStr = String(text).trim();
        if (!textStr) return text;
        
        // 1. Recherche exacte
        if (this.translations[textStr]) {
            return this.translations[textStr];
        }
        
        // 2. Recherche insensible à la casse
        const lowerText = textStr.toLowerCase();
        for (const [french, english] of Object.entries(this.translations)) {
            if (french.toLowerCase() === lowerText) {
                return english;
            }
        }
        
        // 3. Recherche partielle
        for (const [french, english] of Object.entries(this.translations)) {
            if (textStr.includes(french)) {
                return textStr.replace(french, english);
            }
        }
        
        return textStr;
    }

    // Traduire toute la page
    translatePage() {
        if (this.currentLang === 'fr') return;
        
        console.log('🔄 Traduction de la page en cours...');
        
        // Traduire le texte des nœuds
        this.translateTextNodes(document.body);
        
        // Traduire les attributs
        this.translateAttributes();
        
        console.log('✅ Page traduite');
    }

    // Traduire les nœuds texte
    translateTextNodes(element) {
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    // Ignorer les scripts, styles et nœuds vides
                    if (node.parentElement && 
                       (node.parentElement.tagName === 'SCRIPT' || 
                        node.parentElement.tagName === 'STYLE' ||
                        node.parentElement.tagName === 'CODE' ||
                        node.textContent.trim() === '')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        let node;
        const nodes = [];
        while (node = walker.nextNode()) {
            nodes.push(node);
        }

        nodes.forEach(node => {
            const original = node.textContent;
            const translated = this.translate(original);
            if (translated !== original) {
                node.textContent = translated;
            }
        });
    }

    // Traduire les attributs
    translateAttributes() {
        // Placeholders
        document.querySelectorAll('[placeholder]').forEach(el => {
            const original = el.getAttribute('placeholder');
            const translated = this.translate(original);
            if (translated !== original) {
                el.setAttribute('placeholder', translated);
            }
        });

        // Titres
        document.querySelectorAll('[title]').forEach(el => {
            const original = el.getAttribute('title');
            const translated = this.translate(original);
            if (translated !== original) {
                el.setAttribute('title', translated);
            }
        });

        // Alt text
        document.querySelectorAll('[alt]').forEach(el => {
            const original = el.getAttribute('alt');
            const translated = this.translate(original);
            if (translated !== original) {
                el.setAttribute('alt', translated);
            }
        });
    }

    // Changer de langue
    async setLanguage(lang) {
        if (lang !== 'fr' && lang !== 'en') return;
        
        console.log(`🌐 Changement vers: ${lang}`);
        
        // Sauvegarder
        this.currentLang = lang;
        localStorage.setItem('app_lang', lang);
        document.cookie = `lang=${lang};path=/;max-age=31536000`;
        
        // Si on passe en anglais
        if (lang === 'en') {
            await this.loadTranslations();
            this.translatePage();
            // Ajouter paramètre URL sans recharger
            const url = new URL(window.location);
            url.searchParams.set('lang', 'en');
            window.history.replaceState({}, '', url);
        } 
        // Si on passe en français
        else {
            // Recharger la page pour tout remettre en français
            const url = new URL(window.location);
            url.searchParams.set('lang', 'fr');
            window.location.href = url.toString();
        }
        
        // Mettre à jour les boutons
        this.updateLanguageButtons();
    }

    // Mettre à jour l'apparence des boutons
    updateLanguageButtons() {
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeBtn = document.querySelector(`.lang-btn[onclick*="${this.currentLang}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
    }

    // Obtenir un cookie
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }
}

// Créer et exporter l'instance
window.translator = new Translator();

// Initialiser au chargement
document.addEventListener('DOMContentLoaded', function() {
    window.translator.init().then(() => {
        console.log('✅ Traducteur initialisé');
    });
});