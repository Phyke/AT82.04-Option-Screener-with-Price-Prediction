<script lang="ts">
  import { onMount } from "svelte";
  import { fetchPrediction, fetchScreener, fetchUniverse } from "$lib/api";
  import type {
    ContractRequest,
    DataSource,
    ExplanationMode,
    Pick,
    PortfolioState,
    Prediction,
    ScreenerResponse,
    Selection,
    SkippedTicker,
    StrategyState,
    UniverseResponse,
  } from "$lib/types";
  import {
    loadDataSource,
    loadExplanationMode,
    loadPortfolio,
    loadStrategy,
    saveDataSource,
    saveExplanationMode,
    savePortfolio,
    saveStrategy,
  } from "$lib/storage";
  import PortfolioModal from "$lib/components/PortfolioModal.svelte";
  import StrategyControls from "$lib/components/StrategyControls.svelte";
  import PickTable from "$lib/components/PickTable.svelte";
  import SelectionSummary from "$lib/components/SelectionSummary.svelte";
  import TickerDetail from "$lib/components/TickerDetail.svelte";

  let universe = $state<UniverseResponse | null>(null);
  let portfolio = $state<PortfolioState>(loadPortfolio());
  let strategy = $state<StrategyState>(loadStrategy());
  let screener = $state<ScreenerResponse | null>(null);
  let screenerLoading = $state(false);
  let screenerError = $state<string | null>(null);
  let focused = $state<Pick | null>(null);
  let selections = $state<Map<string, Selection>>(new Map());
  let predictions = $state<Map<string, Prediction>>(new Map());
  let predictionLoading = $state(false);
  let predictionError = $state<string | null>(null);
  let portfolioOpen = $state(false);
  let cspFrac = $state(0.55);
  let explanationMode = $state<ExplanationMode>(loadExplanationMode());
  let dataSource = $state<DataSource>(loadDataSource());

  function setExplanationMode(m: ExplanationMode) {
    explanationMode = m;
    saveExplanationMode(m);
  }

  async function setDataSource(s: DataSource) {
    if (s === dataSource) return;
    dataSource = s;
    saveDataSource(s);
    screener = null;
    selections = new Map();
    predictions = new Map();
    focused = null;
    try {
      universe = await fetchUniverse(dataSource);
    } catch (e) {
      screenerError = `Failed to load universe: ${e}`;
      return;
    }
    runScreener();
  }

  let screenerTimer: ReturnType<typeof setTimeout> | null = null;

  onMount(async () => {
    try {
      universe = await fetchUniverse(dataSource);
    } catch (e) {
      screenerError = `Failed to load universe: ${e}`;
      return;
    }
    scheduleScreener();
  });

  function scheduleScreener() {
    if (screenerTimer) clearTimeout(screenerTimer);
    screenerTimer = setTimeout(() => runScreener(), 500);
  }

  function rowKey(p: { ticker: string; strike: number; type: string }): string {
    return `${p.type}:${p.ticker}:${p.strike}`;
  }

  async function runScreener(refresh = false) {
    if (!universe) return;
    screenerLoading = true;
    screenerError = null;
    try {
      const resp = await fetchScreener(portfolio, strategy, { refresh, source: dataSource });
      screener = resp;
      selections = new Map();
      predictions = new Map();
      if (focused) {
        const present = [...resp.cc_picks, ...resp.csp_picks].find(
          (p) => p.ticker === focused!.ticker && p.strike === focused!.strike && p.type === focused!.type,
        );
        if (!present) focused = null;
      }
    } catch (e) {
      screenerError = `Screener failed: ${e}`;
    } finally {
      screenerLoading = false;
    }
  }

  function onPortfolioChange(p: PortfolioState) {
    portfolio = p;
    savePortfolio(p);
    scheduleScreener();
  }

  function onStrategyChange(s: StrategyState) {
    strategy = s;
    saveStrategy(s);
    scheduleScreener();
  }

  function focusPick(p: Pick) {
    focused = p;
  }

  function toggleSelect(p: Pick, checked: boolean) {
    const k = rowKey(p);
    const next = new Map(selections);
    if (checked) {
      const kind = p.type === "call" ? "cc" : "csp";
      next.set(k, { kind, pick: p, contracts: 1 });
    } else {
      next.delete(k);
    }
    selections = next;
  }

  function setContracts(p: Pick, n: number) {
    const k = rowKey(p);
    const sel = selections.get(k);
    if (!sel) return;
    const capped = Math.max(1, Math.min(n, p.max_contracts || 1));
    const next = new Map(selections);
    next.set(k, { ...sel, contracts: capped });
    selections = next;
  }

  async function runPrediction() {
    const list = [...selections.values()];
    if (list.length === 0) return;
    predictionLoading = true;
    predictionError = null;
    const contracts: ContractRequest[] = list.map((s) => ({
      ticker: s.pick.ticker,
      strike: s.pick.strike,
      type: s.pick.type,
    }));
    try {
      const resp = await fetchPrediction(contracts, dataSource);
      const next = new Map(predictions);
      for (const p of resp.predictions) {
        next.set(`${p.type}:${p.ticker}:${p.strike}`, p);
      }
      predictions = next;
    } catch (e) {
      predictionError = `${e}`;
    } finally {
      predictionLoading = false;
    }
  }

  function startDrag(e: MouseEvent) {
    e.preventDefault();
    const target = e.currentTarget as HTMLElement;
    const container = target.parentElement as HTMLElement;
    const rect = container.getBoundingClientRect();
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    const onMove = (ev: MouseEvent) => {
      const y = ev.clientY - rect.top;
      cspFrac = Math.max(0.15, Math.min(0.85, y / rect.height));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function groupSkipped(items: SkippedTicker[]): [string, string[]][] {
    const m = new Map<string, string[]>();
    for (const s of items) {
      if (!m.has(s.reason)) m.set(s.reason, []);
      m.get(s.reason)!.push(s.ticker);
    }
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }

  const cspPicks = $derived<Pick[]>(
    screener ? [...screener.csp_picks].sort((a, b) => b.yield_actual - a.yield_actual) : [],
  );
  const ccPicks = $derived<Pick[]>(
    screener ? [...screener.cc_picks].sort((a, b) => b.yield_actual - a.yield_actual) : [],
  );
  const avgCostByTicker = $derived<Record<string, number>>(
    Object.fromEntries(portfolio.holdings.map((h) => [h.ticker, h.avg_cost])),
  );
  const sharesByTicker = $derived<Record<string, number>>(
    Object.fromEntries(portfolio.holdings.map((h) => [h.ticker, h.shares])),
  );
  const spotByTicker = $derived<Record<string, number>>(screener?.spots ?? {});
  const holdingsValue = $derived.by(() => {
    let total = 0;
    for (const h of portfolio.holdings) {
      const spot = spotByTicker[h.ticker] ?? h.avg_cost;
      total += h.shares * spot;
    }
    return total;
  });
  const holdingsCost = $derived(
    portfolio.holdings.reduce((acc, h) => acc + h.avg_cost * h.shares, 0),
  );
  const unrealizedTotal = $derived(holdingsValue - holdingsCost);
  const unrealizedTotalPct = $derived(holdingsCost > 0 ? unrealizedTotal / holdingsCost : 0);
  const totalValue = $derived(portfolio.cash + holdingsValue);
  const fmtUsd = (n: number) => `$${Math.round(n).toLocaleString()}`;
  const hasHoldings = $derived(portfolio.holdings.length > 0);
  const selectionList = $derived<Selection[]>([...selections.values()]);
</script>

<div class="flex h-screen flex-col bg-tv-bg text-tv-text">
  <header class="flex items-center justify-between border-b border-tv-border bg-tv-panel px-4 py-2 text-sm">
    <div class="flex items-center gap-3">
      <h1 class="text-base font-bold text-tv-text">Options Wheel Advisor</h1>
      <button
        type="button"
        onclick={() => (portfolioOpen = true)}
        class="rounded border border-tv-border bg-tv-card px-3 py-1 text-xs text-tv-text transition-colors hover:border-tv-accent hover:bg-tv-accent/15"
      >
        Portfolio
      </button>
      <div class="flex items-center gap-3 text-xs">
        <span class="text-tv-muted">
          Cash <span class="font-mono text-tv-text">{fmtUsd(portfolio.cash)}</span>
        </span>
        {#if hasHoldings}
          <span class="text-tv-muted">
            Cost <span class="font-mono text-tv-text">{fmtUsd(holdingsCost)}</span>
          </span>
          <span class="text-tv-muted">
            Value <span class="font-mono text-tv-text">{fmtUsd(holdingsValue)}</span>
          </span>
          <span class="text-tv-muted">
            P&L
            <span class="font-mono font-semibold {unrealizedTotal >= 0 ? 'text-tv-up' : 'text-tv-down'}">
              {unrealizedTotal >= 0 ? "+" : "-"}{fmtUsd(Math.abs(unrealizedTotal))}
              ({unrealizedTotal >= 0 ? "+" : ""}{(unrealizedTotalPct * 100).toFixed(2)}%)
            </span>
          </span>
          <span class="text-tv-muted">
            Total <span class="font-mono font-semibold text-tv-text">{fmtUsd(totalValue)}</span>
          </span>
        {/if}
      </div>
    </div>
    <div class="flex items-center gap-3 text-xs text-tv-muted">
      <span>Today: {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}</span>
      {#if screener}
        <span>Expiry: {screener.expiry}</span>
        <span>As of: {new Date(screener.as_of).toLocaleString()}</span>
        {#if !screener.upstream_healthy}
          <span class="rounded bg-tv-down/20 px-2 py-0.5 text-tv-down">market data unavailable</span>
        {/if}
      {/if}
      <div class="inline-flex overflow-hidden rounded border border-tv-border">
        <button
          type="button"
          onclick={() => setDataSource("live")}
          class="px-3 py-1 transition-colors {dataSource === 'live' ? 'bg-tv-accent text-white' : 'bg-tv-card text-tv-text hover:bg-tv-accent/15'}"
        >
          Live
        </button>
        <button
          type="button"
          onclick={() => setDataSource("demo")}
          class="border-l border-tv-border px-3 py-1 transition-colors {dataSource === 'demo' ? 'bg-tv-accent text-white' : 'bg-tv-card text-tv-text hover:bg-tv-accent/15'}"
        >
          Demo
        </button>
      </div>
      <button
        type="button"
        onclick={() => runScreener(true)}
        disabled={screenerLoading}
        class="rounded border border-tv-border bg-tv-card px-3 py-1 text-tv-text transition-colors hover:border-tv-accent hover:bg-tv-accent/15 disabled:opacity-50 disabled:hover:border-tv-border disabled:hover:bg-tv-card"
      >
        {screenerLoading ? "..." : "Refresh"}
      </button>
    </div>
  </header>

  <div class="grid min-h-0 flex-1 grid-cols-[minmax(560px,3fr)_minmax(420px,2fr)]">
    <div class="flex min-h-0 flex-col border-r border-tv-border bg-tv-panel">
      <div class="border-b border-tv-border bg-tv-panel px-3 py-1.5">
        {#if universe}
          <StrategyControls
            {strategy}
            policies={universe.policies}
            yieldTargets={universe.yield_targets}
            researchByTier={screener?.research_by_tier ?? {}}
            onChange={onStrategyChange}
          />
        {/if}
        {#if screenerError}
          <div class="mt-1 rounded border border-tv-down/50 bg-tv-down/10 p-1.5 text-xs text-tv-down">
            {screenerError}
          </div>
        {/if}
      </div>

      <div class="flex min-h-0 flex-1 flex-col">
        <section
          style="flex: {cspFrac} 1 0%;"
          class="flex min-h-0 flex-col border-b border-tv-border"
        >
          <div class="flex items-center justify-between border-b border-tv-border bg-tv-panel px-3 py-1.5 text-xs uppercase tracking-wider text-tv-muted">
            <span>CSP opportunities (your cash)</span>
            <span class="rounded bg-tv-card px-2 py-0.5 font-mono text-[10px] text-tv-text">
              {cspPicks.length}
            </span>
          </div>
          <div class="min-h-0 flex-1">
            <PickTable
              picks={cspPicks}
              {focused}
              {selections}
              onFocus={focusPick}
              onToggleSelect={toggleSelect}
              onContractsChange={setContracts}
              emptyMessage="No CSP picks. Increase cash or lower the yield target."
            />
          </div>
        </section>

        <div
          role="separator"
          aria-orientation="horizontal"
          tabindex="-1"
          onmousedown={startDrag}
          class="group relative flex h-1.5 shrink-0 cursor-row-resize items-center justify-center bg-tv-border hover:bg-tv-accent"
        >
          <div class="pointer-events-none h-0.5 w-10 rounded bg-tv-muted/40 group-hover:bg-white/60"></div>
        </div>

        <section
          style="flex: {1 - cspFrac} 1 0%;"
          class="flex min-h-0 flex-col"
        >
          <div class="flex items-center justify-between border-b border-tv-border bg-tv-panel px-3 py-1.5 text-xs uppercase tracking-wider text-tv-muted">
            <span>CC opportunities (your shares)</span>
            <span class="rounded bg-tv-card px-2 py-0.5 font-mono text-[10px] text-tv-text">
              {ccPicks.length}
            </span>
          </div>
          <div class="min-h-0 flex-1">
            <PickTable
              picks={ccPicks}
              {focused}
              {selections}
              onFocus={focusPick}
              onToggleSelect={toggleSelect}
              onContractsChange={setContracts}
              emptyMessage="No CC picks. Add a holding of 100+ shares of a universe ticker."
            />
          </div>
        </section>
      </div>

      <SelectionSummary
        selections={selectionList}
        cash={portfolio.cash}
      />

      {#if screener?.skipped?.length}
        <details class="border-t border-tv-border bg-tv-panel text-xs">
          <summary class="flex cursor-pointer items-center gap-2 px-3 py-2 text-tv-muted hover:bg-tv-card">
            <span class="rounded bg-tv-card px-2 py-0.5 font-mono text-tv-text">
              {screener.skipped.length}
            </span>
            <span>ticker{screener.skipped.length === 1 ? "" : "s"} skipped</span>
            <span class="ml-auto text-tv-muted">grouped by reason</span>
          </summary>
          <div class="max-h-48 space-y-3 overflow-y-auto border-t border-tv-border bg-tv-bg p-3">
            {#each groupSkipped(screener.skipped) as [reason, tickers] (reason)}
              <div>
                <div class="mb-1.5 flex items-center gap-2">
                  <span class="rounded bg-tv-card px-1.5 py-0.5 font-mono text-[10px] text-tv-text">
                    {tickers.length}
                  </span>
                  <span class="text-tv-muted">{reason}</span>
                </div>
                <div class="flex flex-wrap gap-1 pl-1">
                  {#each tickers as t}
                    <span class="rounded border border-tv-border bg-tv-card px-2 py-0.5 font-mono text-[11px] text-tv-text">
                      {t}
                    </span>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        </details>
      {/if}
    </div>

    <div class="min-h-0 bg-tv-bg">
      <TickerDetail
        pick={focused}
        expiry={screener?.expiry ?? null}
        {avgCostByTicker}
        {sharesByTicker}
        selections={selectionList}
        {predictions}
        {predictionLoading}
        {predictionError}
        onRunPrediction={runPrediction}
        mode={explanationMode}
        onModeChange={setExplanationMode}
        {dataSource}
      />
    </div>
  </div>
</div>

<PortfolioModal
  open={portfolioOpen}
  {portfolio}
  universeTickers={universe?.tickers ?? []}
  {spotByTicker}
  onChange={onPortfolioChange}
  onClose={() => (portfolioOpen = false)}
/>
