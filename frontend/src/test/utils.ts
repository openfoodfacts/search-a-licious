import {getDefaultSearchResultDetail, searchResultDetail} from '../signals';
import {DEFAULT_SEARCH_NAME} from '../utils/constants';

/**
 * Utility function for test to reset signal state
 */
export const resetSignalToDefault = () => {
  searchResultDetail(DEFAULT_SEARCH_NAME).value =
    getDefaultSearchResultDetail();
};
