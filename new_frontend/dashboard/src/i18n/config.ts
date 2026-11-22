import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en } from './locales/en/translation';
import { it } from './locales/it/translation';

const savedLanguage = localStorage.getItem('appLanguage') || 'en';

i18n.use(initReactI18next).init({
  fallbackLng: 'en',
  lng: savedLanguage,
  resources: {
    en: {
      translations: en
    },
    it: {
      translations: it
    }
  },
  ns: ['translations'],
  defaultNS: 'translations',
  interpolation: {
    // React already escapes output — disable i18next's double-escaping
    // so that interpolated values like /dev/sdc are not mangled to &#x2F;dev&#x2F;sdc
    escapeValue: false
  }
});

export default i18n;
