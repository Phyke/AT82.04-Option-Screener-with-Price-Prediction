import type {
  ContractRequest,
  HistoryResponse,
  PortfolioState,
  PredictResponse,
  ScreenerResponse,
  StrategyState,
  UniverseResponse,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export async function fetchUniverse(): Promise<UniverseResponse> {
  return json<UniverseResponse>(await fetch(`${BASE}/universe`));
}

export async function fetchScreener(
  portfolio: PortfolioState,
  strategy: StrategyState,
  { refresh = false }: { refresh?: boolean } = {},
): Promise<ScreenerResponse> {
  const path = refresh ? "/screener/refresh" : "/screener";
  const body = {
    cash: portfolio.cash,
    holdings: portfolio.holdings,
    policy: strategy.policy,
    yield_target: strategy.yield_target,
    tolerance_mode: strategy.tolerance_mode,
    iv_tiers: strategy.iv_tiers,
  };
  return json<ScreenerResponse>(
    await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function fetchPrediction(contracts: ContractRequest[]): Promise<PredictResponse> {
  return json<PredictResponse>(
    await fetch(`${BASE}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contracts }),
    }),
  );
}

export async function fetchHistory(ticker: string): Promise<HistoryResponse> {
  return json<HistoryResponse>(await fetch(`${BASE}/history/${ticker}`));
}
