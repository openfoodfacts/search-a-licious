/**
 * Refresh vega charts by dispatching a resize event
 * This is needed because vega charts are not displayed correctly because of the hidden sidebar
 */
export const refreshCharts = () => {
  return setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
  }, 0);
};
