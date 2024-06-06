export const getTaxonomyName = (taxonomy: string): string => {
  return `${taxonomy}`.replace('s_tags', '').replace('ies_tags', 'y');
};
