<script lang="ts">
  import { onMount, untrack } from "svelte";
  import {
    CandlestickSeries,
    createChart,
    type IChartApi,
    type ISeriesApi,
  } from "lightweight-charts";
  import { fetchHistory } from "../api";
  import type {
    CCPick,
    CSPPick,
    Candle,
    ExplanationMode,
    Pick,
    Prediction,
    Selection,
  } from "../types";
  import { formatMoney, formatPercent } from "../format";

  type Props = {
    pick: Pick | null;
    expiry: string | null;
    avgCostByTicker: Record<string, number>;
    sharesByTicker: Record<string, number>;
    selections: Selection[];
    predictions: Map<string, Prediction>;
    predictionLoading: boolean;
    predictionError: string | null;
    onRunPrediction: () => void;
    mode: ExplanationMode;
    onModeChange: (m: ExplanationMode) => void;
  };

  let {
    pick,
    expiry,
    avgCostByTicker,
    sharesByTicker,
    selections,
    predictions,
    predictionLoading,
    predictionError,
    onRunPrediction,
    mode,
    onModeChange,
  }: Props = $props();

  let chartContainer: HTMLDivElement;
  let chart: IChartApi | undefined;
  let series: ISeriesApi<"Candlestick"> | undefined;
  let candles = $state<Candle[]>([]);
  let lastLoadedTicker: string | null = null;
  let historyLoading = $state(false);
  let chartFrac = $state(0.5);

  function startDrag(e: MouseEvent) {
    e.preventDefault();
    const target = e.currentTarget as HTMLElement;
    const container = target.parentElement as HTMLElement;
    const rect = container.getBoundingClientRect();
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    const onMove = (ev: MouseEvent) => {
      const y = ev.clientY - rect.top;
      chartFrac = Math.max(0.2, Math.min(0.8, y / rect.height));
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

  onMount(() => {
    chart = createChart(chartContainer, {
      width: chartContainer.clientWidth || 400,
      height: chartContainer.clientHeight || 320,
      layout: {
        background: { color: "#0b0f18" },
        textColor: "#eef1f7",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#262b38" },
        horzLines: { color: "#262b38" },
      },
      timeScale: { timeVisible: false, secondsVisible: false, borderColor: "#4b5160" },
      rightPriceScale: { borderColor: "#4b5160" },
      crosshair: { mode: 0 },
    });
    series = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });

    const ro = new ResizeObserver(() => {
      if (!chart || !chartContainer) return;
      chart.applyOptions({
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
      });
    });
    ro.observe(chartContainer);

    return () => {
      ro.disconnect();
      chart?.remove();
      chart = undefined;
      series = undefined;
    };
  });

  async function loadHistory(ticker: string) {
    historyLoading = true;
    try {
      const resp = await fetchHistory(ticker);
      candles = resp.candles;
      if (series) {
        series.setData(
          resp.candles.slice(-126).map((c) => ({
            time: c.date,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          })),
        );
        chart?.timeScale().fitContent();
      }
      lastLoadedTicker = ticker;
    } catch (e) {
      console.error("history load failed", e);
    } finally {
      historyLoading = false;
    }
  }

  $effect(() => {
    const t = pick?.ticker;
    if (!t) return;
    if (t === untrack(() => lastLoadedTicker)) return;
    loadHistory(t);
  });

  function isCC(p: Pick): p is CCPick {
    return p.type === "call";
  }

  function rowKey(p: Pick): string {
    return `${p.type}:${p.ticker}:${p.strike}`;
  }

  const spotDelta = $derived.by(() => {
    if (!pick || candles.length < 2) return null;
    const last = candles[candles.length - 1];
    const prev = candles[candles.length - 2];
    const abs = last.close - prev.close;
    const pct = abs / prev.close;
    return { abs, pct, last: last.close };
  });

  function expiryHeader(iso: string | null): string {
    if (!iso) return "";
    const d = new Date(`${iso}T16:00:00-04:00`);
    const friday = d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
    return `by ${friday}`;
  }

  function summary(p: Pick, n: number, expIso: string | null, m: ExplanationMode): string {
    const exp = expiryHeader(expIso);
    const premium = p.bid * 100 * n;
    if (isCC(p)) {
      const ab = (p.strike - p.spot) / p.spot;
      if (m === "layman") {
        return (
          `You agree to sell **${100 * n} shares** of **${p.ticker}** at **$${p.strike.toFixed(2)}** ${exp} - ` +
          `that's ${formatPercent(Math.abs(ab), 1)} ${ab >= 0 ? "above" : "below"} today's **$${p.spot.toFixed(2)}**. ` +
          `In return, you collect **${formatMoney(premium)} cash today**.`
        );
      }
      const sign = ab >= 0 ? "above" : "below";
      return (
        `You get paid **${formatMoney(premium)}** upfront to agree to sell **${p.ticker}** at ` +
        `**$${p.strike.toFixed(2)}** - ${formatPercent(Math.abs(ab), 1)} ${sign} today's ` +
        `**$${p.spot.toFixed(2)}**, ${exp}.`
      );
    }
    const ab = (p.spot - p.strike) / p.spot;
    if (m === "layman") {
      return (
        `You agree to buy **${100 * n} shares** of **${p.ticker}** at **$${p.strike.toFixed(2)}** ${exp} - ` +
        `that's ${formatPercent(ab, 1)} cheaper than today's **$${p.spot.toFixed(2)}**. ` +
        `In return, you collect **${formatMoney(premium)} cash today**.`
      );
    }
    return (
      `You get paid **${formatMoney(premium)}** upfront to wait to buy **${p.ticker}** at ` +
      `**$${p.strike.toFixed(2)}** - ${formatPercent(ab, 1)} cheaper than today's ` +
      `**$${p.spot.toFixed(2)}**, ${exp}.`
    );
  }

  function yieldLine(p: Pick, m: ExplanationMode): string {
    const y = p.yield_actual;
    const annual = (Math.pow(1 + y, 52) - 1) * 100;
    if (m === "layman") {
      return `That's about **${formatPercent(y, 2)}** on your money in one week, or roughly **${annual.toFixed(0)}%** per year if you repeat it weekly.`;
    }
    return `Yield: **${formatPercent(y, 2)}** weekly (~**${annual.toFixed(0)}%**/yr compounded).`;
  }

  function requirementLine(p: Pick, n: number, m: ExplanationMode): string {
    if (isCC(p)) {
      const required = 100 * n;
      const owned = sharesByTicker[p.ticker] ?? 0;
      const avgCost = avgCostByTicker[p.ticker] ?? 0;
      const ofYours =
        owned > 0 && avgCost > 0
          ? ` (out of your **${owned} shares** at average of **$${avgCost.toFixed(2)}/share**)`
          : owned > 0
            ? ` (out of your **${owned} shares** total)`
            : "";
      if (m === "layman") {
        return `You lock up **${required} shares** of **${p.ticker}**${ofYours} until the offer ends Friday.`;
      }
      return `Needs **${required} shares** of **${p.ticker}** as collateral${ofYours}.`;
    }
    const capital = (p as CSPPick).collateral_required * n;
    if (m === "layman") {
      return `You set aside **${formatMoney(capital)}** in case you end up buying the shares.`;
    }
    return `Needs **${formatMoney(capital)}** cash as collateral.`;
  }

  function outcomeLine(p: Pick, n: number, m: ExplanationMode): { text: string; isLoss: boolean } {
    const premium = p.bid * 100 * n;
    if (isCC(p)) {
      const avgCost = avgCostByTicker[p.ticker] ?? 0;
      const stockPnl = (p.strike - avgCost) * 100 * n;
      const net = premium + stockPnl;
      if (avgCost <= 0) {
        const text =
          m === "layman"
            ? `If ${p.ticker} stays below **$${p.strike.toFixed(2)}** Friday, you keep your shares and the **${formatMoney(premium)}**. Otherwise your shares get sold at **$${p.strike.toFixed(2)}**, you still keep the **${formatMoney(premium)}**.`
            : `If called away: your shares are sold at **$${p.strike.toFixed(2)}** and you keep **${formatMoney(premium)}** premium.`;
        return { text, isLoss: false };
      }
      const stockWord = stockPnl >= 0 ? "gain" : "loss";
      const netSign = net >= 0 ? "+" : "-";
      if (m === "layman") {
        const happyPath = `If ${p.ticker} stays below **$${p.strike.toFixed(2)}** Friday, you keep your shares AND the **${formatMoney(premium)}** cash.`;
        const calledAway =
          stockPnl >= 0
            ? `Otherwise your shares are sold at **$${p.strike.toFixed(2)}**, giving you **${formatMoney(premium)}** cash + **${formatMoney(Math.abs(stockPnl))}** stock profit = **net ${netSign}${formatMoney(Math.abs(net))}**.`
            : `Otherwise your shares are sold at **$${p.strike.toFixed(2)}**, below your cost - that's a **${formatMoney(Math.abs(stockPnl))}** stock loss, softened by the **${formatMoney(premium)}** premium = **net ${netSign}${formatMoney(Math.abs(net))}**.`;
        return { text: `${happyPath} ${calledAway}`, isLoss: net < 0 };
      }
      return {
        text:
          `If called away: **+${formatMoney(premium)}** premium ${stockPnl >= 0 ? "+" : "-"} ` +
          `**${formatMoney(Math.abs(stockPnl))}** stock ${stockWord} → net **${netSign}${formatMoney(Math.abs(net))}**.`,
        isLoss: net < 0,
      };
    }
    const effectiveBasis = p.strike - p.bid;
    const discount = (p.spot - effectiveBasis) / p.spot;
    if (m === "layman") {
      return {
        text:
          `If ${p.ticker} stays above **$${p.strike.toFixed(2)}** Friday, nothing happens and you keep the **${formatMoney(premium)}**. ` +
          `Otherwise you buy **${100 * n} shares** at **$${p.strike.toFixed(2)}** - but since you already collected **${formatMoney(premium)}**, ` +
          `your real cost per share is only **$${effectiveBasis.toFixed(2)}**, which is ${formatPercent(discount, 1)} below today's price.`,
        isLoss: false,
      };
    }
    return {
      text:
        `If assigned: you hold **${100 * n} shares** of **${p.ticker}** at an effective ` +
        `**$${effectiveBasis.toFixed(2)}/share** (${formatPercent(discount, 1)} below today's spot).`,
      isLoss: false,
    };
  }

  function predictionLine(p: Pick, pred: Prediction | undefined, m: ExplanationMode): string | null {
    if (!pred) return null;
    if (pred.error) return `Model: ${pred.error}`;
    if (pred.p_assigned === undefined || pred.p_assigned === null) return null;
    const ood = pred.ood ? ' <span class="text-tv-warn">(out of model training range)</span>' : "";
    if (m === "layman") {
      const outcome = isCC(p) ? "actually end up selling your shares" : "actually end up buying the shares";
      return `Our prediction model says there's a **${formatPercent(pred.p_assigned, 1)}** chance you'll ${outcome}.${ood}`;
    }
    const label = isCC(p) ? "being called away" : "assignment";
    return `Model estimates **${formatPercent(pred.p_assigned, 1)}** chance of ${label}.${ood}`;
  }

  function renderMd(s: string): string {
    return s.replace(/\*\*(.+?)\*\*/g, '<strong class="text-tv-text">$1</strong>');
  }

  const cardList = $derived.by(() => {
    if (selections.length > 0) {
      return selections.map((s) => ({ pick: s.pick, contracts: s.contracts }));
    }
    if (pick) {
      return [{ pick, contracts: 1 }];
    }
    return [];
  });
</script>

<div class="flex h-full flex-col bg-tv-bg text-tv-text">
  <div class="flex items-start justify-between border-b border-tv-border p-4 pb-3">
    {#if pick}
      <div class="flex items-baseline gap-3">
        <h2 class="text-2xl font-bold text-tv-text">{pick.ticker}</h2>
        <span class="text-xl font-semibold text-tv-text">${pick.spot.toFixed(2)}</span>
        {#if spotDelta}
          <span class="text-sm {spotDelta.abs >= 0 ? 'text-tv-up' : 'text-tv-down'}">
            {spotDelta.abs >= 0 ? "+" : ""}{spotDelta.abs.toFixed(2)} ({spotDelta.abs >= 0 ? "+" : ""}{formatPercent(spotDelta.pct, 2)})
          </span>
        {/if}
      </div>
    {:else}
      <h2 class="text-lg font-semibold text-tv-muted">No selection</h2>
    {/if}
    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={onRunPrediction}
        disabled={predictionLoading || selections.length === 0}
        class="rounded bg-tv-accent px-3 py-1 text-xs font-semibold text-white shadow-sm transition-all hover:brightness-125 hover:shadow-tv-accent/40 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100 disabled:hover:shadow-none"
        title={selections.length === 0 ? "Check contracts on the left first" : `Predict ${selections.length} selected`}
      >
        {predictionLoading ? "Predicting..." : `Run prediction${selections.length > 0 ? ` (${selections.length})` : ""}`}
      </button>
      <span class="rounded border border-tv-border px-2 py-0.5 text-xs text-tv-muted">6mo - Daily</span>
    </div>
  </div>

  {#if predictionError}
    <div class="border-b border-tv-border bg-tv-down/10 px-4 py-1 text-xs text-tv-down">
      {predictionError}
    </div>
  {/if}

  <div class="flex min-h-0 flex-1 flex-col">
    <section
      style="flex: {chartFrac} 1 0%;"
      class="relative min-h-0"
    >
      <div bind:this={chartContainer} class="absolute inset-0"></div>
      {#if !pick}
        <div class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-tv-muted">
          Click a row on the left to see the chart.
        </div>
      {/if}
      {#if historyLoading}
        <div class="pointer-events-none absolute top-2 right-2 rounded bg-tv-panel/80 px-2 py-1 text-xs text-tv-muted">
          Loading chart...
        </div>
      {/if}
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
      style="flex: {1 - chartFrac} 1 0%;"
      class="flex min-h-0 flex-col overflow-y-auto bg-tv-panel"
    >
      {#if cardList.length > 0}
        <div class="space-y-2 p-3">
          <div class="flex items-center justify-between">
            <div class="text-[10px] uppercase tracking-wider text-tv-muted">
              {selections.length > 0 ? `Selected contracts (${selections.length})` : "Focused contract"}
            </div>
            <div class="inline-flex overflow-hidden rounded border border-tv-border text-[11px]">
              <button
                type="button"
                onclick={() => onModeChange("layman")}
                class="px-2 py-0.5 transition-colors {mode === 'layman' ? 'bg-tv-accent text-white' : 'bg-tv-card text-tv-muted hover:bg-tv-border hover:text-tv-text'}"
              >
                Beginner
              </button>
              <button
                type="button"
                onclick={() => onModeChange("trader")}
                class="border-l border-tv-border px-2 py-0.5 transition-colors {mode === 'trader' ? 'bg-tv-accent text-white' : 'bg-tv-card text-tv-muted hover:bg-tv-border hover:text-tv-text'}"
              >
                Trader
              </button>
            </div>
          </div>
          {#each cardList as { pick: p, contracts } (rowKey(p))}
            {@const pred = predictions.get(rowKey(p))}
            {@const predLine = predictionLine(p, pred, mode)}
            {@const outcome = outcomeLine(p, contracts, mode)}
            <div class="rounded border border-tv-border bg-tv-bg p-3 text-sm">
              <div class="mb-1 flex items-center gap-2">
                <span class="font-mono text-sm font-semibold text-tv-text">{p.ticker}</span>
                <span class="rounded px-1 py-[1px] text-[10px] font-bold text-white {isCC(p) ? 'bg-tv-up' : 'bg-tv-down'}">
                  {isCC(p) ? "CC" : "CSP"}
                </span>
                <span class="font-mono text-tv-muted">${p.strike.toFixed(2)}</span>
                <span class="ml-auto font-mono text-xs text-tv-muted">x {contracts}</span>
              </div>
              <p class="leading-relaxed text-tv-text">{@html renderMd(summary(p, contracts, expiry, mode))}</p>
              <p class="mt-1 leading-relaxed text-tv-muted">{@html renderMd(yieldLine(p, mode))}</p>
              <p class="mt-1 leading-relaxed text-tv-muted">{@html renderMd(requirementLine(p, contracts, mode))}</p>
              <p class="mt-1 leading-relaxed {outcome.isLoss ? 'text-tv-down' : 'text-tv-muted'}">
                {@html renderMd(outcome.text)}
              </p>
              {#if predLine}
                <p class="mt-1 text-tv-muted">{@html renderMd(predLine)}</p>
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <div class="flex h-full items-center justify-center p-4 text-sm text-tv-muted">
          Check rows on the left to list contract details here.
        </div>
      {/if}
    </section>
  </div>
</div>
