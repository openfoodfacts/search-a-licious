interface ChartSearchParamPOST {
  chart_type: string;
  field?: string;
  x?: string;
  y?: string;
}

export type ChartSearchParam = ChartSearchParamPOST | string;
