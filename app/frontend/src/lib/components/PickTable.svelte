<script lang="ts">
  import type { CCPick, CSPPick, Pick, Prediction, Selection } from "../types";
  import { formatPercent } from "../format";

  type Props = {
    picks: Pick[];
    focused: Pick | null;
    selections: Map<string, Selection>;
    predictions: Map<string, Prediction>;
    onFocus: (p: Pick) => void;
    onToggleSelect: (p: Pick, checked: boolean) => void;
    onContractsChange: (p: Pick, n: number) => void;
    emptyMessage: string;
  };

  let {
    picks,
    focused,
    selections,
    predictions,
    onFocus,
    onToggleSelect,
    onContractsChange,
    emptyMessage,
  }: Props = $props();

  function isCC(p: Pick): p is CCPick {
    return p.type === "call";
  }

  function rowKey(p: Pick): string {
    return `${p.type}:${p.ticker}:${p.strike}`;
  }

  function ssPct(p: Pick): number {
    return (p.strike - p.spot) / p.spot;
  }

  function isFocused(p: Pick): boolean {
    return focused !== null && focused.ticker === p.ticker && focused.strike === p.strike && focused.type === p.type;
  }

  function stop(e: Event) {
    e.stopPropagation();
  }
</script>

<div class="h-full overflow-y-auto">
  <table class="w-full border-collapse text-sm">
    <thead class="sticky top-0 z-10 bg-tv-bg">
      <tr class="text-left text-[10px] uppercase tracking-wider text-tv-muted">
        <th class="px-3 py-2">Ticker</th>
        <th class="px-1 py-2">T</th>
        <th class="px-1 py-2 text-right">Strike</th>
        <th class="px-1 py-2 text-right">Spot</th>
        <th class="px-1 py-2 text-right">S/S %</th>
        <th class="px-1 py-2 text-right">Bid</th>
        <th class="px-1 py-2 text-right">Bid %</th>
        <th class="px-1 py-2 text-right">IV</th>
        <th class="px-1 py-2 text-right">Δ</th>
        <th class="px-1 py-2 text-right">P(asn)</th>
        <th class="px-1 py-2 text-right">Max</th>
        <th class="px-1 py-2 text-right">#</th>
        <th class="w-8 px-2 py-2 pr-3 text-center"></th>
      </tr>
    </thead>
    <tbody>
      {#each picks as p (rowKey(p))}
        {@const key = rowKey(p)}
        {@const sel = selections.get(key)}
        {@const pred = predictions.get(key)}
        {@const ss = ssPct(p)}
        {@const below = isCC(p) && (p as CCPick).below_cost_basis}
        <tr
          class="cursor-pointer border-b border-tv-border/50 leading-tight transition-colors hover:bg-tv-card {isFocused(p)
            ? 'bg-tv-card'
            : ''}"
          onclick={() => onFocus(p)}
        >
          <td class="px-3 py-1 font-mono text-base font-semibold text-tv-text">{p.ticker}</td>
          <td class="px-1 py-1">
            <span
              class="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold text-white {isCC(p)
                ? 'bg-tv-up'
                : 'bg-tv-down'}"
            >
              {isCC(p) ? "C" : "P"}
            </span>
          </td>
          <td class="px-1 py-1 text-right font-mono text-tv-text">{p.strike.toFixed(2)}</td>
          <td class="px-1 py-1 text-right font-mono text-tv-muted">{p.spot.toFixed(2)}</td>
          <td class="px-1 py-1 text-right font-mono {ss >= 0 ? 'text-tv-up' : 'text-tv-down'}">
            {ss >= 0 ? "+" : ""}{(ss * 100).toFixed(1)}%
          </td>
          <td class="px-1 py-1 text-right font-mono text-tv-text">{p.bid.toFixed(2)}</td>
          <td class="px-1 py-1 text-right font-mono text-tv-text">{formatPercent(p.yield_actual, 1)}</td>
          <td class="px-1 py-1 text-right font-mono text-tv-muted">
            {(p.implied_volatility * 100).toFixed(0)}%
            {#if below}
              <span class="ml-1 text-[10px] text-tv-down" title="Below cost basis">!</span>
            {/if}
          </td>
          <td class="px-1 py-1 text-right font-mono text-tv-muted">
            {p.delta >= 0 ? "+" : ""}{p.delta.toFixed(2)}
          </td>
          <td class="px-1 py-1 text-right font-mono">
            {#if pred?.error}
              <span class="text-[10px] text-tv-down" title={pred.error}>err</span>
            {:else if pred?.p_assigned !== undefined && pred?.p_assigned !== null}
              <span
                class="{pred.ood ? 'text-tv-dim italic' : 'text-tv-warn'}"
                title={pred.ood ? "Out of training range - extrapolated" : ""}
              >
                {formatPercent(pred.p_assigned, 0)}{pred.ood ? "*" : ""}
              </span>
            {:else}
              <span class="text-tv-dim">-</span>
            {/if}
          </td>
          <td class="px-1 py-1 text-right font-mono text-tv-muted">{p.max_contracts}</td>
          <td class="px-1 py-1 text-right">
            <input
              type="number"
              min="1"
              max={p.max_contracts || 1}
              value={sel?.contracts ?? 1}
              disabled={sel === undefined}
              onclick={stop}
              oninput={(e) => onContractsChange(p, Number((e.target as HTMLInputElement).value))}
              class="w-11 min-w-0 rounded border border-tv-border bg-tv-card px-1 py-0.5 text-right font-mono font-semibold text-white focus:border-tv-accent focus:outline-none disabled:opacity-40"
            />
          </td>
          <td class="px-2 py-1 pr-3 text-center">
            <input
              type="checkbox"
              checked={sel !== undefined}
              onclick={stop}
              onchange={(e) => onToggleSelect(p, (e.target as HTMLInputElement).checked)}
              class="accent-tv-accent"
            />
          </td>
        </tr>
      {/each}
      {#if picks.length === 0}
        <tr>
          <td colspan="13" class="px-4 py-6 text-center text-sm text-tv-muted">
            {emptyMessage}
          </td>
        </tr>
      {/if}
    </tbody>
  </table>
</div>
