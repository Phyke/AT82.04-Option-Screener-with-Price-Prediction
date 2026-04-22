<script lang="ts">
  import type { Holding, PortfolioState } from "../types";
  import { formatMoney } from "../format";

  type Props = {
    portfolio: PortfolioState;
    universeTickers: string[];
    spotByTicker: Record<string, number>;
    onChange: (p: PortfolioState) => void;
  };

  let { portfolio, universeTickers, spotByTicker, onChange }: Props = $props();

  function liveValue(ticker: string, shares: number, avgCost: number): number {
    const spot = spotByTicker[ticker] ?? avgCost;
    return spot * shares;
  }

  function unrealizedPnl(ticker: string, shares: number, avgCost: number): number | null {
    const spot = spotByTicker[ticker];
    if (spot === undefined) return null;
    return (spot - avgCost) * shares;
  }

  function unrealizedPct(ticker: string, avgCost: number): number | null {
    const spot = spotByTicker[ticker];
    if (spot === undefined || avgCost <= 0) return null;
    return (spot - avgCost) / avgCost;
  }

  const holdingsValue = $derived(
    portfolio.holdings.reduce((acc, h) => acc + liveValue(h.ticker, h.shares, h.avg_cost), 0),
  );
  const holdingsCost = $derived(
    portfolio.holdings.reduce((acc, h) => acc + h.avg_cost * h.shares, 0),
  );
  const unrealizedTotal = $derived(holdingsValue - holdingsCost);
  const unrealizedTotalPct = $derived(holdingsCost > 0 ? unrealizedTotal / holdingsCost : 0);
  const totalValue = $derived(portfolio.cash + holdingsValue);

  let draftTicker = $state("");
  let draftShares = $state<number | null>(null);
  let draftAvg = $state<number | null>(null);

  const usedTickers = $derived(new Set(portfolio.holdings.map((h) => h.ticker)));
  const availableTickers = $derived(universeTickers.filter((t) => !usedTickers.has(t)));

  function updateCash(value: number) {
    if (!Number.isFinite(value) || value < 0) return;
    onChange({ ...portfolio, cash: value });
  }

  function updateHolding(ticker: string, patch: Partial<Holding>) {
    const next = portfolio.holdings.map((h) => (h.ticker === ticker ? { ...h, ...patch } : h));
    onChange({ ...portfolio, holdings: next });
  }

  function updateShares(ticker: string, value: number) {
    if (!Number.isFinite(value) || value <= 0) return;
    updateHolding(ticker, { shares: Math.floor(value) });
  }

  function updateAvgCost(ticker: string, value: number) {
    if (!Number.isFinite(value) || value <= 0) return;
    updateHolding(ticker, { avg_cost: value });
  }

  function addHolding() {
    if (!draftTicker) return;
    if (!draftShares || draftShares <= 0) return;
    if (!draftAvg || draftAvg <= 0) return;
    const h: Holding = { ticker: draftTicker, shares: draftShares, avg_cost: draftAvg };
    onChange({ ...portfolio, holdings: [...portfolio.holdings, h] });
    draftTicker = "";
    draftShares = null;
    draftAvg = null;
  }

  function removeHolding(ticker: string) {
    onChange({ ...portfolio, holdings: portfolio.holdings.filter((h) => h.ticker !== ticker) });
  }
</script>

<div class="rounded-lg border border-tv-border bg-tv-panel p-5">
  <label class="mb-4 flex items-center gap-3">
    <span class="text-xs uppercase tracking-wider text-tv-muted">Cash</span>
    <div class="relative">
      <span class="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-sm text-tv-muted">$</span>
      <input
        type="number"
        min="0"
        step="100"
        value={portfolio.cash}
        class="w-40 rounded border border-tv-border bg-tv-card py-1 pr-2 pl-5 text-right text-sm text-tv-text focus:border-tv-accent focus:outline-none"
        oninput={(e) => updateCash(Number((e.target as HTMLInputElement).value))}
      />
    </div>
  </label>

  <div class="mb-2 text-xs uppercase tracking-wider text-tv-muted">Holdings</div>
  {#if portfolio.holdings.length > 0}
    <div class="mb-2 grid grid-cols-[72px_1fr_1fr_auto] gap-2 px-1 text-[10px] uppercase tracking-wider text-tv-muted">
      <span>Ticker</span>
      <span class="text-right">Shares</span>
      <span class="text-right">Avg cost</span>
      <span></span>
    </div>
  {/if}
  <div class="space-y-1.5">
    {#each portfolio.holdings as h (h.ticker)}
      {@const spot = spotByTicker[h.ticker]}
      {@const value = liveValue(h.ticker, h.shares, h.avg_cost)}
      {@const pnl = unrealizedPnl(h.ticker, h.shares, h.avg_cost)}
      {@const pnlPct = unrealizedPct(h.ticker, h.avg_cost)}
      <div class="rounded border border-tv-border bg-tv-card px-2 py-1.5">
        <div class="grid grid-cols-[72px_1fr_1fr_auto] items-center gap-2">
          <span class="font-mono text-sm font-semibold text-tv-text">{h.ticker}</span>
          <input
            type="number"
            min="1"
            step="1"
            value={h.shares}
            class="w-full min-w-0 rounded border border-tv-border bg-tv-bg px-2 py-1 text-right text-sm font-mono text-tv-text focus:border-tv-accent focus:outline-none"
            oninput={(e) => updateShares(h.ticker, Number((e.target as HTMLInputElement).value))}
          />
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={h.avg_cost}
            class="w-full min-w-0 rounded border border-tv-border bg-tv-bg px-2 py-1 text-right text-sm font-mono text-tv-text focus:border-tv-accent focus:outline-none"
            oninput={(e) => updateAvgCost(h.ticker, Number((e.target as HTMLInputElement).value))}
          />
          <button
            type="button"
            class="rounded px-1.5 text-tv-muted transition-colors hover:bg-tv-down/15 hover:text-tv-down"
            onclick={() => removeHolding(h.ticker)}
            aria-label="Remove {h.ticker}"
          >
            x
          </button>
        </div>
        <div class="mt-1 flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 px-[2px] text-[11px]">
          <span class="text-tv-muted">
            {#if spot}
              Spot <span class="font-mono text-tv-text">${spot.toFixed(2)}</span>
            {:else}
              <span class="text-tv-dim">spot unavailable</span>
            {/if}
          </span>
          <span class="text-tv-muted">
            Value <span class="font-mono text-tv-text">{formatMoney(value)}</span>
          </span>
          {#if pnl !== null}
            <span class="text-tv-muted">
              P&L
              <span class="font-mono font-semibold {pnl >= 0 ? 'text-tv-up' : 'text-tv-down'}">
                {pnl >= 0 ? "+" : "-"}{formatMoney(Math.abs(pnl))}{pnlPct !== null ? ` (${pnl >= 0 ? "+" : ""}${(pnlPct * 100).toFixed(2)}%)` : ""}
              </span>
            </span>
          {/if}
        </div>
      </div>
    {/each}
    {#if portfolio.holdings.length === 0}
      <div class="rounded border border-dashed border-tv-border px-3 py-3 text-center text-xs text-tv-muted">
        No holdings yet.
      </div>
    {/if}
  </div>

  {#if portfolio.holdings.length > 0}
    <div class="mt-3 space-y-1 rounded border border-tv-border bg-tv-card px-3 py-2 text-sm">
      <div class="flex justify-between">
        <span class="text-tv-muted">Cash</span>
        <span class="font-mono text-tv-text">{formatMoney(portfolio.cash)}</span>
      </div>
      <div class="flex justify-between">
        <span class="text-tv-muted">Holdings cost</span>
        <span class="font-mono text-tv-text">{formatMoney(holdingsCost)}</span>
      </div>
      <div class="flex justify-between">
        <span class="text-tv-muted">Holdings value</span>
        <span class="font-mono text-tv-text">{formatMoney(holdingsValue)}</span>
      </div>
      <div class="flex justify-between">
        <span class="text-tv-muted">Unrealized P&L</span>
        <span class="font-mono font-semibold {unrealizedTotal >= 0 ? 'text-tv-up' : 'text-tv-down'}">
          {unrealizedTotal >= 0 ? "+" : "-"}{formatMoney(Math.abs(unrealizedTotal))}
          ({unrealizedTotal >= 0 ? "+" : ""}{(unrealizedTotalPct * 100).toFixed(2)}%)
        </span>
      </div>
      <div class="flex justify-between border-t border-tv-border pt-1">
        <span class="font-semibold text-tv-text">Total portfolio</span>
        <span class="font-mono text-base font-semibold text-tv-up">{formatMoney(totalValue)}</span>
      </div>
    </div>
  {/if}

  <div class="mt-4 grid grid-cols-[1fr_1fr_1fr_auto] gap-2">
    <select
      bind:value={draftTicker}
      class="min-w-0 rounded border border-tv-border bg-tv-card px-2 py-2 text-sm text-tv-text transition-colors hover:border-tv-accent hover:bg-tv-accent/15 focus:border-tv-accent focus:outline-none"
    >
      <option value="">Ticker</option>
      {#each availableTickers as t}
        <option value={t}>{t}</option>
      {/each}
    </select>
    <input
      type="number"
      min="1"
      placeholder="Shares"
      bind:value={draftShares}
      class="min-w-0 rounded border border-tv-border bg-tv-card px-2 py-2 text-right text-sm text-tv-text focus:border-tv-accent focus:outline-none"
    />
    <input
      type="number"
      min="0.01"
      step="0.01"
      placeholder="Avg $"
      bind:value={draftAvg}
      class="min-w-0 rounded border border-tv-border bg-tv-card px-2 py-2 text-right text-sm text-tv-text focus:border-tv-accent focus:outline-none"
    />
    <button
      type="button"
      onclick={addHolding}
      class="rounded bg-tv-accent px-3 text-sm font-semibold text-white shadow-sm transition-all hover:brightness-125 hover:shadow-tv-accent/40"
    >
      Add
    </button>
  </div>
</div>
