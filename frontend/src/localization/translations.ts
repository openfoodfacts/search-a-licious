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
