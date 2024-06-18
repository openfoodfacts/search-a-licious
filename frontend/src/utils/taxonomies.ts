/**
 * Get the taxonomy name from the taxonomy string
 * @param taxonomy
 */
export const getTaxonomyName = (taxonomy: string): string => {
  return `${taxonomy}`.replace('ies_tags', 'y').replace('s_tags', '');
};

export const removeLangFromTermId = (termId: string): string => {
  return termId.replace(/^[a-z]{2}:/, '');
};
