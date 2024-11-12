/**
 * Get the taxonomy name from the taxonomy string
 * @param taxonomy
 */
export const getTaxonomyName = (taxonomy: string): string => {
  return `${taxonomy}`.replace('ies_tags', 'y').replace('s_tags', '');
};

/**
 * Remove the language from the term id
 * For exemple: en:termId => termId
 * @param termId
 */
export const removeLangFromTermId = (termId: string): string => {
  return termId.replace(/^[a-z]{2}:/, '');
};

/** unquote a term */
export const unquoteTerm = (term: string): string => {
  return term.replace(/^"(.*)"$/, '$1');
};
