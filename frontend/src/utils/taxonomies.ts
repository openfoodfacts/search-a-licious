/**
 * Get the taxonomy name from the taxonomy string
 * @param taxonomy
 */
export const getTaxonomyName = (taxonomy: string): string => {
  return `${taxonomy}`.replace('s_tags', '').replace('ies_tags', 'y');
};
