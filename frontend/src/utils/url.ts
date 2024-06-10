export const setURLHistory = (
  url: string,
  params: Record<string, string | undefined>
): string => {
  const urlObj = new URL(url);
  for (const key in params) {
    if (params[key] === undefined) {
      urlObj.searchParams.delete(key);
      continue;
    }
    urlObj.searchParams.set(key, params[key]!);
  }
  const newUrl = urlObj.toString();
  window.history.pushState({}, '', newUrl);
  return newUrl;
};

export const setCurrentURLHistory = (
  params: Record<string, string | undefined>
): string => {
  const url = window.location.href;
  return setURLHistory(url, params);
};

export const removeParenthesis = (value: string): string => {
  if (value.startsWith('(') && value.endsWith(')')) {
    return value.slice(1, -1);
  } else {
    return value;
  }
};

export const addParamPrefix = (value: string, prefix: string): string => {
  return `${prefix}_${value}`;
};

export const addParamPrefixes = (
  obj: Record<string, unknown>,
  prefix: string
): Record<string, unknown> => {
  const newObj: Record<string, unknown> = {};
  for (const key in obj) {
    newObj[addParamPrefix(key, prefix)] = obj[key];
  }
  return newObj;
};

export const removeParamPrefix = (value: string, prefix: string): string => {
  return value.replace(`${prefix}_`, '');
};

export const removeParamPrefixes = (
  obj: Record<string, string>,
  prefix: string
): Record<string, string> => {
  const newObj: Record<string, string> = {};
  for (const key in obj) {
    newObj[removeParamPrefix(key, prefix)] = obj[key];
  }
  return newObj;
};
