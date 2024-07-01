import {getDefaultSearchResultDetail, searchResultDetail} from '../signals';
import {DEFAULT_SEARCH_NAME} from '../utils/constants';

export const resetSignalToDefault = () => {
  searchResultDetail(DEFAULT_SEARCH_NAME).value =
    getDefaultSearchResultDetail();
};
