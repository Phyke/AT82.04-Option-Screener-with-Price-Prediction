<script lang="ts">
  import type { CSPPick, Selection } from "../types";
  import { formatMoney } from "../format";

  type Props = {
    selections: Selection[];
    cash: number;
  };

  let { selections, cash }: Props = $props();

  const count = $derived(selections.reduce((acc, s) => acc + s.contracts, 0));
  const premium = $derived(
    selections.reduce((acc, s) => acc + s.pick.bid * 100 * s.contracts, 0),
  );
  const cashUsed = $derived(
    selections.reduce(
      (acc, s) => (s.kind === "csp" ? acc + (s.pick as CSPPick).collateral_required * s.contracts : acc),
      0,
    ),
  );
  const remaining = $derived(cash - cashUsed);
  const overAllocated = $derived(remaining < 0);
  const sharesByTicker = $derived.by(() => {
    const m: Record<string, number> = {};
    for (const s of selections) {
      if (s.kind === "cc") {
        m[s.pick.ticker] = (m[s.pick.ticker] ?? 0) + 100 * s.contracts;
      }
    }
    return m;
  });
</script>

<div class="border-t border-tv-border bg-tv-panel px-4 py-3">
  <div class="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
    <div>
      <span class="text-tv-muted">Selected:</span>
      <span class="ml-1 font-mono text-base font-semibold text-tv-text">{count}</span>
    </div>
    <div>
      <span class="text-tv-muted">Premium:</span>
      <span class="ml-1 font-mono text-base font-semibold text-tv-up">{formatMoney(premium)}</span>
    </div>
    <div>
      <span class="text-tv-muted">Cash used:</span>
      <span class="ml-1 font-mono text-base text-tv-text">{formatMoney(cashUsed)}</span>
    </div>
    <div>
      <span class="text-tv-muted">Remaining:</span>
      <span class="ml-1 font-mono text-base font-semibold {overAllocated ? 'text-tv-down' : 'text-tv-text'}">
        {formatMoney(remaining)}
      </span>
    </div>
    {#if Object.keys(sharesByTicker).length > 0}
      <div class="flex items-center gap-2">
        <span class="text-tv-muted">Shares:</span>
        {#each Object.entries(sharesByTicker) as [t, n]}
          <span class="rounded bg-tv-card px-2 py-0.5 font-mono text-sm text-tv-text">{n} {t}</span>
        {/each}
      </div>
    {/if}
  </div>
  {#if overAllocated}
    <div class="mt-1 text-[11px] text-tv-down">Warning: selected CSPs need more collateral than your cash.</div>
  {/if}
</div>
