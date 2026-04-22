import type { DataSource, ExplanationMode, IVTier, PortfolioState, StrategyState } from "./types";

const ALL_TIERS: IVTier[] = ["low", "mid", "high"];

const PORTFOLIO_KEY = "options-app/portfolio";
const STRATEGY_KEY = "options-app/strategy";
const EXPLANATION_KEY = "options-app/explanation-mode";
const DATA_SOURCE_KEY = "options-app/data-source";

const DEFAULT_PORTFOLIO: PortfolioState = { cash: 10000, holdings: [] };
const DEFAULT_STRATEGY: StrategyState = {
  policy: "aggressive",
  yield_target: 0.01,
  tolerance_mode: "research",
  iv_tiers: [...ALL_TIERS],
};
const DEFAULT_EXPLANATION: ExplanationMode = "layman";

export function loadPortfolio(): PortfolioState {
  if (typeof localStorage === "undefined") return DEFAULT_PORTFOLIO;
  const raw = localStorage.getItem(PORTFOLIO_KEY);
  if (!raw) return DEFAULT_PORTFOLIO;
  try {
    const parsed = JSON.parse(raw) as PortfolioState;
    if (typeof parsed.cash !== "number" || !Array.isArray(parsed.holdings)) {
      return DEFAULT_PORTFOLIO;
    }
    return parsed;
  } catch {
    return DEFAULT_PORTFOLIO;
  }
}

export function savePortfolio(state: PortfolioState): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(state));
}

export function loadStrategy(): StrategyState {
  if (typeof localStorage === "undefined") return DEFAULT_STRATEGY;
  const raw = localStorage.getItem(STRATEGY_KEY);
  if (!raw) return DEFAULT_STRATEGY;
  try {
    const parsed = JSON.parse(raw) as Partial<StrategyState>;
    if (!parsed.policy || typeof parsed.yield_target !== "number") {
      return DEFAULT_STRATEGY;
    }
    const tiers = Array.isArray(parsed.iv_tiers) && parsed.iv_tiers.length > 0
      ? parsed.iv_tiers.filter((t): t is IVTier => t === "low" || t === "mid" || t === "high")
      : [...ALL_TIERS];
    return {
      policy: parsed.policy,
      yield_target: parsed.yield_target,
      tolerance_mode: parsed.tolerance_mode ?? "research",
      iv_tiers: tiers.length > 0 ? tiers : [...ALL_TIERS],
    };
  } catch {
    return DEFAULT_STRATEGY;
  }
}

export function saveStrategy(state: StrategyState): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STRATEGY_KEY, JSON.stringify(state));
}

export function loadExplanationMode(): ExplanationMode {
  if (typeof localStorage === "undefined") return DEFAULT_EXPLANATION;
  const raw = localStorage.getItem(EXPLANATION_KEY);
  if (raw === "trader" || raw === "layman") return raw;
  return DEFAULT_EXPLANATION;
}

export function saveExplanationMode(mode: ExplanationMode): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(EXPLANATION_KEY, mode);
}

export function loadDataSource(): DataSource {
  if (typeof localStorage === "undefined") return "live";
  const raw = localStorage.getItem(DATA_SOURCE_KEY);
  return raw === "demo" ? "demo" : "live";
}

export function saveDataSource(source: DataSource): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(DATA_SOURCE_KEY, source);
}
