import {LitElement} from 'lit';
import {Constructor} from './utils';
import {SearchaliciousSort} from '../search-sort';
import {SearchaliciousFacets} from '../search-facets';
import {ChartSearchParam} from '../interfaces/chart-interfaces';
import {
  SearchaliciousDistributionChart,
  SearchaliciousScatterChart,
} from '../search-chart';
import {QueryOperator} from '../utils/enums';
import {SearchaliciousStateInterface} from './search-ctl-state';
import {SearchaliciousHistoryInterface} from '../interfaces/history-interfaces';

export declare class SearchaliciousDomInterface {
  _facetsNames(): string[];
  _chartParams(isGetRequest: boolean): ChartSearchParam[] | string | undefined;
  resetFacets(launchSearch?: boolean): void;
}

export const SearchaliciousDomMixin = <T extends Constructor<LitElement & SearchaliciousStateInterface & SearchaliciousHistoryInterface>>(
  superClass: T
) => {
  class SearchaliciousDomMixinClass extends superClass {
    override _sortElement = (): SearchaliciousSort | null => {
      let sortElement: SearchaliciousSort | null = null;
      document.querySelectorAll(`searchalicious-sort`).forEach((item) => {
        const sortElementItem = item as SearchaliciousSort;
        if (sortElementItem.searchName == this.name) {
          if (sortElement !== null) {
            console.warn(
              `searchalicious-sort element with search-name ${this.name} already exists, ignoring`
            );
          } else {
            sortElement = sortElementItem;
          }
        }
      });
      return sortElement;
    };

    override relatedFacets = (): SearchaliciousFacets[] => {
      const allNodes: SearchaliciousFacets[] = [];
      document.querySelectorAll(`searchalicious-facets`).forEach((item) => {
        const facetElement = item as SearchaliciousFacets;
        if (facetElement.searchName == this.name) {
          allNodes.push(facetElement);
        }
      });
      return allNodes;
    };

    _facetsNames(): string[] {
      const names = this.relatedFacets()
        .map((facets) => facets.getFacetsNames())
        .flat();
      return [...new Set(names)];
    }

    _chartParams(
      isGetRequest: boolean
    ): ChartSearchParam[] | string | undefined {
      const chartsParams: ChartSearchParam[] = [];

      document
        .querySelectorAll(
          `searchalicious-distribution-chart[search-name=${this.name}]`
        )
        .forEach((item) => {
          const chartItem = item as SearchaliciousDistributionChart;
          chartsParams.push(chartItem.getSearchParam(isGetRequest));
        });

      document
        .querySelectorAll(
          `searchalicious-scatter-chart[search-name=${this.name}]`
        )
        .forEach((item) => {
          const chartItem = item as SearchaliciousScatterChart;
          chartsParams.push(chartItem.getSearchParam(isGetRequest));
        });

      if (chartsParams.length === 0) return undefined;

      if (isGetRequest) return chartsParams.join(',');

      return chartsParams;
    }

    override _facetsFilters = (): string => {
      const allFilters: string[] = this.relatedFacets()
        .map((facets) => facets.getSearchFilters())
        .flat();
      return allFilters.join(QueryOperator.AND);
    };

    resetFacets(launchSearch = true) {
      this.relatedFacets().forEach((facets) => facets.reset(launchSearch));
    }
  }

  return SearchaliciousDomMixinClass as unknown as Constructor<SearchaliciousDomInterface> & T;
};
