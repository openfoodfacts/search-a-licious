export const isTheSameSearchName = (
  searchName: string,
  event: Event
): boolean => {
  return searchName === (event as CustomEvent).detail?.searchName;
};
