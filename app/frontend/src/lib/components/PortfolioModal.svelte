<script lang="ts">
  import type { PortfolioState } from "../types";
  import PortfolioForm from "./PortfolioForm.svelte";

  type Props = {
    open: boolean;
    portfolio: PortfolioState;
    universeTickers: string[];
    spotByTicker: Record<string, number>;
    onChange: (p: PortfolioState) => void;
    onClose: () => void;
  };

  let { open, portfolio, universeTickers, spotByTicker, onChange, onClose }: Props = $props();

  function onBackdropKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }
</script>

<svelte:window onkeydown={onBackdropKey} />

{#if open}
  <div
    class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
    onclick={onClose}
    role="button"
    tabindex="-1"
    aria-label="Close portfolio"
    onkeydown={(e) => {
      if (e.key === "Enter" || e.key === " ") onClose();
    }}
  ></div>
  <aside
    class="fixed left-0 top-0 bottom-0 z-50 flex w-[560px] max-w-[90vw] flex-col border-r border-tv-border bg-tv-panel shadow-2xl"
    role="dialog"
    aria-label="Portfolio"
  >
    <header class="flex items-center justify-between border-b border-tv-border px-6 py-4">
      <h2 class="text-lg font-semibold text-tv-text">Portfolio</h2>
      <button
        type="button"
        onclick={onClose}
        class="rounded border border-tv-border px-3 py-1 text-sm text-tv-text transition-colors hover:border-tv-accent hover:bg-tv-accent/15"
        aria-label="Close"
      >
        Close
      </button>
    </header>
    <div class="flex-1 overflow-y-auto overflow-x-hidden p-6">
      <PortfolioForm {portfolio} {universeTickers} {spotByTicker} {onChange} />
    </div>
  </aside>
{/if}
