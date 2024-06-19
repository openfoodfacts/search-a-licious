import {configureLocalization} from '@lit/localize';
import {sourceLocale, targetLocales} from './generated/locale-codes';

export const getBrowserLocale = () => {
  return (navigator.language || navigator.languages[0]).split('-')[0];
};
export const {getLocale, setLocale} = configureLocalization({
  sourceLocale,
  targetLocales,
  loadLocale: (locale: string) => import(`./generated/locales/${locale}.js`),
});

(async () => {
  try {
    // Defer first render until our initial locale is ready, to avoid a flash of
    // the wrong locale.
    // It sets the locale to the browser locale
    await setLocale(getBrowserLocale());
  } catch (e) {
    // Either the URL locale code was invalid, or there was a problem loading
    // the locale module.
    console.error(`Error loading locale: ${(e as Error).message}`);
  }
})();
