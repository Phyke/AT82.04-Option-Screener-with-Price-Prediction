export type Policy = "strict" | "safe" | "aggressive";
export type ToleranceMode = "research" | "tight";
export type OptionType = "call" | "put";
export type IVTier = "low" | "mid" | "high";

export type Holding = {
  ticker: string;
  shares: number;
  avg_cost: number;
};

export type PortfolioState = {
  cash: number;
  holdings: Holding[];
};

export type StrategyState = {
  policy: Policy;
  yield_target: number;
  tolerance_mode: ToleranceMode;
  iv_tiers: IVTier[];
};

export type ExplanationMode = "trader" | "layman";

export type UniverseResponse = {
  tickers: string[];
  policies: Policy[];
  yield_targets: number[];
  expiry: string;
  as_of: string;
};

export type CCPick = {
  ticker: string;
  type: "call";
  strike: number;
  spot: number;
  bid: number;
  ask: number;
  mark: number;
  implied_volatility: number;
  delta: number;
  open_interest: number;
  volume: number;
  yield_actual: number;
  yield_gap: number;
  premium_dollars: number;
  shares_required: number;
  max_contracts: number;
  cost_basis_gap: number;
  below_cost_basis: boolean;
  iv_tier: IVTier | null;
};

export type CSPPick = {
  ticker: string;
  type: "put";
  strike: number;
  spot: number;
  bid: number;
  ask: number;
  mark: number;
  implied_volatility: number;
  delta: number;
  open_interest: number;
  volume: number;
  yield_actual: number;
  yield_gap: number;
  premium_dollars: number;
  collateral_required: number;
  max_contracts: number;
  fits_cash: boolean;
  iv_tier: IVTier | null;
};

export type ResearchHint = {
  policy: "strict" | "safe" | "aggressive" | "skip";
  total_return: number;
  sharpe: number;
  stable: boolean;
  alt_policy_2020: string | null;
  yield_rounded: number;
};

export type Pick = CCPick | CSPPick;

export type SkippedTicker = {
  ticker: string;
  reason: string;
};

export type ScreenerResponse = {
  expiry: string;
  as_of: string;
  upstream_healthy: boolean;
  cc_picks: CCPick[];
  csp_picks: CSPPick[];
  skipped: SkippedTicker[];
  spots: Record<string, number>;
  research_by_tier: Partial<Record<IVTier, ResearchHint>>;
};

export type ContractRequest = {
  ticker: string;
  strike: number;
  type: OptionType;
};

export type Prediction = {
  ticker: string;
  strike: number;
  type: OptionType;
  pred_friday_close?: number;
  spot_used?: number;
  error?: string;
};

export type PredictResponse = {
  as_of: string;
  model_input_date: string;
  predictions: Prediction[];
};

export type Candle = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type HistoryResponse = {
  ticker: string;
  candles: Candle[];
};
