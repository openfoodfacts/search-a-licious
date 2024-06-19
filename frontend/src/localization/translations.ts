import {msg} from '@lit/localize';

/**
 * Utility functions to take the appropriate translation based on the value
 * If value is <= 1 or null or undefined, it will return the singleTranslation, otherwise the pluralTranslation
 * @param value
 * @param singleTranslation
 * @param pluralTranslation
 * @returns
 * @example
 * getPluralTranslation(1, 'product', 'products') // 'product'
 */

export const getPluralTranslation = (
  value: number | undefined | null,
  singleTranslation: string,
  pluralTranslation: string
) => {
  return (value ?? 0) <= 1 ? singleTranslation : pluralTranslation;
};

export type DynamicTranslation = () => string;
export type DynamicTranslations = Record<string, DynamicTranslation>;

/**
 * Get a dynamic translation based on the key, usefull to takes element from external sources and translate them
 * @param key
 */
export const getDynamicTranslation = (key: string): string | undefined => {
  return TRANSLATIONS[key]?.();
};

/**
 * Get a dynamic translation based on the key, if not found, return the default value
 * With store in function for reactivity
 * @param key
 */
export const FACETS_TRANSLATIONS: DynamicTranslations = {
  brands_tags: () => msg('Brands'),
  categories_tags: () => msg('Categories'),
  nutrition_grades: () => msg('Nutrition grades'),
  ecoscore_grade: () => msg('Ecoscore grade'),
};

/**
 * Contains all translations, I separate by categories (facets, etc...) to better understand the source of the translations
 * It allows to get the translation by key with getDynamicTranslation function
 */
const TRANSLATIONS: DynamicTranslations = {
  ...FACETS_TRANSLATIONS,
};
