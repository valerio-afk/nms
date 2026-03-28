import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en } from './locales/en/translation';
import { it } from './locales/it/translation';

const savedLanguage = localStorage.getItem('appLanguage') || 'en';

i18n.use(initReactI18next).init({
  fallbackLng: 'en',
  lng: savedLanguage, // default to saved language or english
  resources: {
    en: {
      translations: en
    },
    it: {
      translations: it
    }
  },
  ns: ['translations'],
  defaultNS: 'translations'
});

export default i18n;
