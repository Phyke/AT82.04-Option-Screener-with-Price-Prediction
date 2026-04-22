<script lang="ts">
  import type { IVTier, Policy, ResearchHint, StrategyState, ToleranceMode } from "../types";
  import { formatPercent } from "../format";

  type Props = {
    strategy: StrategyState;
    policies: Policy[];
    yieldTargets: number[];
    researchByTier: Partial<Record<IVTier, ResearchHint>>;
    onChange: (s: StrategyState) => void;
  };

  let { strategy, policies, yieldTargets, researchByTier, onChange }: Props = $props();

  const ALL_TIERS: IVTier[] = ["low", "mid", "high"];
  const TIER_LABEL: Record<IVTier, string> = {
    low: "Low",
    mid: "Mid",
    high: "High",
  };

  function cap(s: string): string {
    return s.length === 0 ? s : s[0].toUpperCase() + s.slice(1);
  }

  function toleranceHint(mode: ToleranceMode, target: number): string {
    const rel = target * 0.25;
    const applied = mode === "tight" ? Math.min(rel, 0.005) : rel;
    return `±${(applied * 100).toFixed(2)}pp`;
  }

  function toggleTier(tier: IVTier) {
    const set = new Set(strategy.iv_tiers);
    if (set.has(tier)) {
      if (set.size === 1) return;
      set.delete(tier);
    } else {
      set.add(tier);
    }
    const ordered = ALL_TIERS.filter((t) => set.has(t));
    onChange({ ...strategy, iv_tiers: ordered });
  }
</script>

<div class="flex flex-wrap items-center gap-4 text-tv-text">
  <label class="flex items-center gap-2 text-sm">
    <span class="text-tv-muted">Policy</span>
    <select
      value={strategy.policy}
      onchange={(e) => onChange({ ...strategy, policy: (e.target as HTMLSelectElement).value as Policy })}
      class="rounded border border-tv-border bg-tv-card px-2 py-1 transition-colors hover:border-tv-accent hover:bg-tv-accent/15 focus:border-tv-accent focus:outline-none"
    >
      {#each policies as p}
        <option value={p}>{cap(p)}</option>
      {/each}
    </select>
  </label>

  <label class="flex items-center gap-2 text-sm">
    <span class="text-tv-muted">Target yield</span>
    <select
      value={strategy.yield_target}
      onchange={(e) => onChange({ ...strategy, yield_target: Number((e.target as HTMLSelectElement).value) })}
      class="rounded border border-tv-border bg-tv-card px-2 py-1 transition-colors hover:border-tv-accent hover:bg-tv-accent/15 focus:border-tv-accent focus:outline-none"
    >
      {#each yieldTargets as y}
        <option value={y}>{formatPercent(y, 1)}</option>
      {/each}
    </select>
  </label>

  <label class="flex items-center gap-2 text-sm">
    <span class="text-tv-muted">Tolerance</span>
    <div class="inline-flex overflow-hidden rounded border border-tv-border">
      <button
        type="button"
        onclick={() => onChange({ ...strategy, tolerance_mode: "research" })}
        class="px-2 py-1 text-xs transition-colors {strategy.tolerance_mode === 'research' ? 'bg-tv-accent text-white' : 'bg-tv-card text-tv-muted hover:bg-tv-border hover:text-tv-text'}"
        title="Match research (±25% relative; may be wide at high yields)"
      >
        Research
      </button>
      <button
        type="button"
        onclick={() => onChange({ ...strategy, tolerance_mode: "tight" })}
        class="border-l border-tv-border px-2 py-1 text-xs transition-colors {strategy.tolerance_mode === 'tight' ? 'bg-tv-accent text-white' : 'bg-tv-card text-tv-muted hover:bg-tv-border hover:text-tv-text'}"
        title="Cap at 0.5pp absolute (tighter at high yields)"
      >
        Tight
      </button>
    </div>
    <span class="font-mono text-xs text-tv-muted">{toleranceHint(strategy.tolerance_mode, strategy.yield_target)}</span>
  </label>

  <label class="flex items-center gap-2 text-sm">
    <span class="text-tv-muted">IV tier</span>
    <div class="inline-flex overflow-hidden rounded border border-tv-border">
      {#each ALL_TIERS as tier, i (tier)}
        {@const active = strategy.iv_tiers.includes(tier)}
        {@const hint = researchByTier[tier]}
        <button
          type="button"
          onclick={() => toggleTier(tier)}
          title={hint
            ? `Research: ${hint.policy} · ${(hint.total_return * 100).toFixed(0)}% · S=${hint.sharpe.toFixed(2)}${hint.stable ? "" : " (regime-sensitive)"}`
            : `${TIER_LABEL[tier]}-IV tier`}
          class="px-2 py-1 text-xs transition-colors {i > 0 ? 'border-l border-tv-border' : ''} {active ? 'bg-tv-accent text-white' : 'bg-tv-card text-tv-muted hover:bg-tv-border hover:text-tv-text'}"
        >
          {TIER_LABEL[tier]}
        </button>
      {/each}
    </div>
  </label>
</div>

{#if strategy.iv_tiers.length > 0}
  <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-tv-muted">
    {#each strategy.iv_tiers as tier (tier)}
      {@const hint = researchByTier[tier]}
      {#if hint}
        <span class="flex items-center gap-1">
          <span class="font-semibold text-tv-text">{TIER_LABEL[tier]}</span>
          <span>·</span>
          {#if hint.policy === "skip"}
            <span class="text-tv-warn">skip (no edge at {formatPercent(hint.yield_rounded, 0)})</span>
          {:else}
            <span class="text-tv-text">{hint.policy}</span>
            <span class="font-mono">{hint.total_return >= 0 ? "+" : ""}{(hint.total_return * 100).toFixed(0)}%</span>
            <span class="font-mono">S={hint.sharpe.toFixed(2)}</span>
          {/if}
          {#if !hint.stable}
            <span class="rounded bg-tv-warn/20 px-1 text-tv-warn" title="since_2020 and since_2024 windows disagree">⚠</span>
          {/if}
        </span>
      {/if}
    {/each}
  </div>
{/if}
