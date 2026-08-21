<script lang="ts">
	import { Database, FileSignature, BookType, BadgeCheck, Loader2, AlertCircle, RefreshCw } from '@lucide/svelte';

	type Tab = 'letter-nodes' | 'signatures' | 'letter-type-memory' | 'designations';

	let activeTab = $state<Tab>('letter-nodes');
	let loading = $state(false);
	let error = $state<string | null>(null);

	let letterNodes = $state<any[]>([]);
	let signatures = $state<any[]>([]);
	let letterTypeMemory = $state<any[]>([]);
	let designations = $state<any[]>([]);

	const tabs: { id: Tab; label: string; icon: any }[] = [
		{ id: 'letter-nodes', label: 'Letter Nodes', icon: Database },
		{ id: 'signatures', label: 'Signatures', icon: FileSignature },
		{ id: 'letter-type-memory', label: 'Letter Type Memory', icon: BookType },
		{ id: 'designations', label: 'Designations', icon: BadgeCheck }
	];

	async function fetchData(tab: Tab) {
		loading = true;
		error = null;
		const token = localStorage.getItem('access_token');
		try {
			const res = await fetch(`/datastore/${tab}`, {
				headers: token ? { Authorization: `Bearer ${token}` } : {}
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({ detail: `Error ${res.status}` }));
				throw new Error(err.detail || `Request failed with status ${res.status}`);
			}
			const data = await res.json();
			switch (tab) {
				case 'letter-nodes':
					letterNodes = data;
					break;
				case 'signatures':
					signatures = data;
					break;
				case 'letter-type-memory':
					letterTypeMemory = data;
					break;
				case 'designations':
					designations = data;
					break;
			}
		} catch (e: any) {
			error = e.message || 'Failed to fetch data';
		} finally {
			loading = false;
		}
	}

	function switchTab(tab: Tab) {
		activeTab = tab;
		fetchData(tab);
	}

	function getCurrentData(): any[] {
		switch (activeTab) {
			case 'letter-nodes':
				return letterNodes;
			case 'signatures':
				return signatures;
			case 'letter-type-memory':
				return letterTypeMemory;
			case 'designations':
				return designations;
		}
	}

	function formatDate(dateStr: string): string {
		if (!dateStr) return '—';
		return new Date(dateStr).toLocaleDateString('en-IN', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function truncate(str: string | null | undefined, len = 80): string {
		if (!str) return '—';
		return str.length > len ? str.slice(0, len) + '…' : str;
	}

	// Fetch initial tab data on mount
	$effect(() => {
		fetchData('letter-nodes');
	});
</script>

<div class="flex h-full flex-col overflow-hidden">
	<!-- Header -->
	<div class="border-b border-border bg-card/50 px-6 py-4">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div
					class="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary"
				>
					<Database class="size-5" />
				</div>
				<div>
					<h1 class="text-lg font-semibold text-foreground">DataStore</h1>
					<p class="text-xs text-muted-foreground">Browse ingested data across all stores</p>
				</div>
			</div>
			<button
				onclick={() => fetchData(activeTab)}
				disabled={loading}
				class="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
			>
				<RefreshCw class="size-3.5 {loading ? 'animate-spin' : ''}" />
				Refresh
			</button>
		</div>
	</div>

	<!-- Tab Bar -->
	<div class="border-b border-border bg-card/30 px-6">
		<div class="-mb-px flex gap-1">
			{#each tabs as tab (tab.id)}
				<button
					onclick={() => switchTab(tab.id)}
					class="flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors
						{activeTab === tab.id
						? 'border-primary text-foreground'
						: 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'}"
				>
					<tab.icon class="size-4" />
					{tab.label}
				</button>
			{/each}
		</div>
	</div>

	<!-- Content Area -->
	<div class="flex-1 overflow-auto p-6">
		{#if loading}
			<div class="flex flex-col items-center justify-center gap-3 py-20 text-muted-foreground">
				<Loader2 class="size-8 animate-spin" />
				<p class="text-sm">Loading data…</p>
			</div>
		{:else if error}
			<div
				class="mx-auto flex max-w-md flex-col items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center"
			>
				<AlertCircle class="size-8 text-destructive" />
				<p class="text-sm font-medium text-destructive">{error}</p>
				<button
					onclick={() => fetchData(activeTab)}
					class="mt-2 rounded-lg bg-destructive/10 px-4 py-1.5 text-sm text-destructive transition-colors hover:bg-destructive/20"
				>
					Try Again
				</button>
			</div>
		{:else if getCurrentData().length === 0}
			<div class="flex flex-col items-center justify-center gap-2 py-20 text-muted-foreground">
				<Database class="size-10 opacity-30" />
				<p class="text-sm">No records found</p>
				<p class="text-xs opacity-60">Ingest a Google Doc to populate this store</p>
			</div>
		{:else}
			<!-- Letter Nodes Table -->
			{#if activeTab === 'letter-nodes'}
				<div class="overflow-hidden rounded-xl border border-border">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border bg-muted/50">
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Subject</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Ref No</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Date</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Source Doc</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Tab Title</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Metadata</th>
							</tr>
						</thead>
						<tbody>
							{#each letterNodes as node, i (node.id)}
								<tr
									class="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/30"
								>
									<td class="max-w-xs px-4 py-3">
										<span class="block truncate" title={node.text}>{truncate(node.text, 60)}</span>
									</td>
									<td class="px-4 py-3 font-mono text-xs text-muted-foreground">
										{node.metadata_?.ref_no || '—'}
									</td>
									<td class="whitespace-nowrap px-4 py-3 text-muted-foreground">
										{node.metadata_?.date || '—'}
									</td>
									<td class="px-4 py-3 font-mono text-xs text-muted-foreground">
										{truncate(node.metadata_?.source_doc_id, 20)}
									</td>
									<td class="px-4 py-3 text-muted-foreground">
										{truncate(node.metadata_?.tab_title, 30)}
									</td>
									<td class="px-4 py-3 text-muted-foreground">
										<button
											class="inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
											onclick={() => navigator.clipboard.writeText(JSON.stringify(node.metadata_, null, 2))}
										>
											Copy JSON
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="mt-3 text-xs text-muted-foreground">
					{letterNodes.length} node{letterNodes.length !== 1 ? 's' : ''} found
				</p>
			{/if}

			<!-- Signatures Table -->
			{#if activeTab === 'signatures'}
				<div class="overflow-hidden rounded-xl border border-border">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border bg-muted/50">
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Name</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Image</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Source Doc</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Created</th>
							</tr>
						</thead>
						<tbody>
							{#each signatures as sig (sig.id)}
								<tr
									class="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/30"
								>
									<td class="px-4 py-3 font-medium">{sig.name || '—'}</td>
									<td class="px-4 py-3">
										{#if sig.image_url}
											<a
												href={sig.image_url}
												target="_blank"
												rel="noopener noreferrer"
												class="inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
											>
												View Image
											</a>
										{:else}
											<span class="text-muted-foreground">—</span>
										{/if}
									</td>
									<td class="px-4 py-3 font-mono text-xs text-muted-foreground">
										{truncate(sig.source_doc_id, 24)}
									</td>
									<td class="whitespace-nowrap px-4 py-3 text-muted-foreground">
										{formatDate(sig.created_at)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="mt-3 text-xs text-muted-foreground">
					{signatures.length} signature{signatures.length !== 1 ? 's' : ''} found
				</p>
			{/if}

			<!-- Letter Type Memory Table -->
			{#if activeTab === 'letter-type-memory'}
				<div class="overflow-hidden rounded-xl border border-border">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border bg-muted/50">
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Letter Type</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Domain</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Description</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground"
									>Approval Chain</th
								>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Template</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Created</th>
							</tr>
						</thead>
						<tbody>
							{#each letterTypeMemory as ltm (ltm.id)}
								<tr
									class="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/30"
								>
									<td class="px-4 py-3 font-medium">{ltm.letter_type}</td>
									<td class="px-4 py-3">
										<span
											class="inline-block rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
										>
											{ltm.primary_domain}
										</span>
									</td>
									<td class="max-w-xs px-4 py-3 text-muted-foreground">
										<span class="block truncate" title={ltm.description}
											>{truncate(ltm.description, 60)}</span
										>
									</td>
									<td class="px-4 py-3 text-xs text-muted-foreground">
										{ltm.approval_chain?.length || 0} step{(ltm.approval_chain?.length || 0) !== 1 ? 's' : ''}
									</td>
									<td class="px-4 py-3">
										{#if ltm.template_url}
											<a
												href={ltm.template_url}
												target="_blank"
												rel="noopener"
												class="text-xs text-primary underline-offset-2 hover:underline"
											>
												Open
											</a>
										{:else}
											<span class="text-xs text-muted-foreground">—</span>
										{/if}
									</td>
									<td class="whitespace-nowrap px-4 py-3 text-muted-foreground">
										{formatDate(ltm.created_at)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="mt-3 text-xs text-muted-foreground">
					{letterTypeMemory.length} record{letterTypeMemory.length !== 1 ? 's' : ''} found
				</p>
			{/if}

			<!-- Designations Table -->
			{#if activeTab === 'designations'}
				<div class="overflow-hidden rounded-xl border border-border">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border bg-muted/50">
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Title</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Incumbent</th>
								<th class="px-4 py-3 text-left font-medium text-muted-foreground">Created</th>
							</tr>
						</thead>
						<tbody>
							{#each designations as des (des.id)}
								<tr
									class="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/30"
								>
									<td class="px-4 py-3 font-medium">{des.title}</td>
									<td class="px-4 py-3 text-muted-foreground">{des.incumbent || '—'}</td>
									<td class="whitespace-nowrap px-4 py-3 text-muted-foreground">
										{formatDate(des.created_at)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="mt-3 text-xs text-muted-foreground">
					{designations.length} designation{designations.length !== 1 ? 's' : ''} found
				</p>
			{/if}
		{/if}
	</div>
</div>
