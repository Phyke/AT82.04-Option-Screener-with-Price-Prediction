<script lang="ts">
  import type { Policy, StrategyState, ToleranceMode } from "../types";
  import { formatPercent } from "../format";

  type Props = {
    strategy: StrategyState;
    policies: Policy[];
    yieldTargets: number[];
    onChange: (s: StrategyState) => void;
  };

  let { strategy, policies, yieldTargets, onChange }: Props = $props();

  function cap(s: string): string {
    return s.length === 0 ? s : s[0].toUpperCase() + s.slice(1);
  }

  function toleranceHint(mode: ToleranceMode, target: number): string {
    const rel = target * 0.25;
    const applied = mode === "tight" ? Math.min(rel, 0.005) : rel;
    return `±${(applied * 100).toFixed(2)}pp`;
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
</div>
