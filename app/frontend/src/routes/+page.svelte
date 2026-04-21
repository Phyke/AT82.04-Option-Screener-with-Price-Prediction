<script lang="ts">
	import {
		fetchHistory,
		fetchPrediction,
		fetchRecommendation,
		fetchUniverse,
		scanForUser,
	} from '$lib/api';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import OpportunityTable from '$lib/components/OpportunityTable.svelte';
	import PriceChart from '$lib/components/PriceChart.svelte';
	import RecommendationCard from '$lib/components/RecommendationCard.svelte';
	import StrategyConfig from '$lib/components/StrategyConfig.svelte';
	import TradeInsights from '$lib/components/TradeInsights.svelte';
	import type {
		Candle,
		Opportunity,
		Prediction,
		Recommendation,
		Universe,
	} from '$lib/types';
	import { onMount } from 'svelte';

	// ── User strategy config ──────────────────────────────────────────────────
	let cashBalance = $state(50000);
	let positionsText = $state('AAPL:200, NVDA:100');
	let targetWeeklyYieldPct = $state(0.5);

	// ── Scan state ────────────────────────────────────────────────────────────
	let universe = $state<Universe | null>(null);
	let scanning = $state(false);
	let scanError = $state('');
	let csps = $state<Opportunity[]>([]);
	let ccs = $state<Opportunity[]>([]);
	let scanSummary = $state<{
		n_csp_candidates: number;
		n_cc_candidates: number;
		n_contracts_scanned: number;
		n_model_trade: number;
		n_model_skip: number;
		n_tickers_predicted: number;
	} | null>(null);
	let mode = $state<'csp' | 'cc'>('csp');
	let selectedContract = $state<Opportunity | null>(null);

	// ── Display filters ───────────────────────────────────────────────────────
	let minDTE = $state(0);
	let maxDTE = $state(12);
	let sortBy = $state<keyof Opportunity>('edge_score');
	let sortDesc = $state(true);
	let tradeOnly = $state(false);

	// ── Chart state ───────────────────────────────────────────────────────────
	let selectedTicker = $state('');
	let chartHistory = $state<Candle[]>([]);

	// ── Prediction + Recommendation state ─────────────────────────────────────
	let prediction = $state<Prediction | null>(null);
	let recommendation = $state<Recommendation | null>(null);
	let predicting = $state(false);
	let predictError = $state('');

	// ── Derived ───────────────────────────────────────────────────────────────
	const activeList = $derived(mode === 'csp' ? csps : ccs);
	const filteredOpportunities = $derived(
		activeList
			.filter((o) => o.days_to_expiry >= minDTE && o.days_to_expiry <= maxDTE)
			.filter((o) => !tradeOnly || o.model_signal === 'TRADE')
			.sort((a, b) => {
				const va = (a[sortBy] as number) ?? -Infinity;
				const vb = (b[sortBy] as number) ?? -Infinity;
				return sortDesc ? vb - va : va - vb;
			}),
	);
	const lastClose = $derived(chartHistory.at(-1)?.close ?? null);

	// ── Helpers ───────────────────────────────────────────────────────────────
	function parsePositions(text: string): Record<string, number> {
		const result: Record<string, number> = {};
		for (const part of text.split(',')) {
			const [tk, qty] = part.split(':').map((x) => x.trim());
			if (tk && qty) {
				const n = parseInt(qty, 10);
				if (!isNaN(n) && n > 0) result[tk.toUpperCase()] = n;
			}
		}
		return result;
	}

	// ── Actions ───────────────────────────────────────────────────────────────
	async function loadUniverse() {
		try {
			universe = await fetchUniverse();
		} catch (e) {
			console.error('failed to load universe', e);
		}
	}

	async function runScan() {
		scanning = true;
		scanError = '';
		selectedContract = null;
		prediction = null;
		recommendation = null;
		try {
			const positions = parsePositions(positionsText);
			const resp = await scanForUser({
				cash_balance: cashBalance,
				positions,
				target_weekly_yield_pct: targetWeeklyYieldPct,
			});
			csps = resp.csps;
			ccs = resp.ccs;
			scanSummary = resp.summary;
		} catch (e: any) {
			scanError = e?.message ?? 'scan failed';
			csps = [];
			ccs = [];
		} finally {
			scanning = false;
		}
	}

	async function selectContract(opp: Opportunity) {
		selectedContract = opp;
		prediction = null;
		recommendation = null;
		predictError = '';
		if (opp.ticker !== selectedTicker) {
			selectedTicker = opp.ticker;
			try {
				chartHistory = await fetchHistory(opp.ticker);
			} catch (e) {
				console.error('chart load failed', e);
			}
		}
	}

	async function runPrediction() {
		if (!selectedContract) return;
		predicting = true;
		predictError = '';
		prediction = null;
		recommendation = null;
		try {
			const [pred, rec] = await Promise.all([
				fetchPrediction(selectedContract.ticker),
				fetchRecommendation(selectedContract.ticker, selectedContract),
			]);
			prediction = pred;
			recommendation = rec;
		} catch (e: any) {
			predictError = e?.message ?? 'prediction failed';
		} finally {
			predicting = false;
		}
	}

	onMount(() => {
		loadUniverse();
	});
</script>

<div class="app">
	<div class="workspace">
		<aside class="left-panel">
			<StrategyConfig
				bind:cashBalance
				bind:positionsText
				bind:targetWeeklyYieldPct
				{universe}
				{scanning}
				{scanError}
				{scanSummary}
				onScan={runScan}
			/>

			<FilterBar
				bind:mode
				cspCount={csps.length}
				ccCount={ccs.length}
				bind:minDTE
				bind:maxDTE
				bind:sortBy
				bind:sortDesc
				bind:tradeOnly
			/>

			<OpportunityTable
				opportunities={filteredOpportunities}
				selected={selectedContract}
				{mode}
				hasAnyResults={csps.length > 0 || ccs.length > 0}
				universeSize={universe?.n_tickers ?? 34}
				onSelect={selectContract}
			/>
		</aside>

		<div class="right-panel">
			<PriceChart {selectedTicker} {chartHistory} />

			<div class="insights">
				{#if selectedContract}
					<TradeInsights contract={selectedContract} {lastClose} />
					<RecommendationCard
						{prediction}
						{recommendation}
						{predicting}
						{predictError}
						onPredict={runPrediction}
					/>
				{:else}
					<p class="insight-empty">Select a trade from the table to see details.</p>
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.app {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}
	.workspace {
		display: grid;
		grid-template-columns: 56% 44%;
		flex: 1;
		overflow: hidden;
	}
	.left-panel {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		border-right: 1px solid #222;
	}
	.right-panel {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		background: #141414;
	}
	.insights {
		flex-shrink: 0;
		border-top: 1px solid #222;
		background: #111;
		padding: 18px 20px;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.insight-empty {
		font-size: 15px;
		color: #777;
	}
</style>
