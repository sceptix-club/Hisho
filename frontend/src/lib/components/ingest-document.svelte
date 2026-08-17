<script lang="ts">
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import Button from '$lib/components/ui/button/button.svelte';
	import Input from '$lib/components/ui/input/input.svelte';
	import { Upload, Loader2, CheckCircle, AlertCircle, FileText } from '@lucide/svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';

	let open = $state(false);
	let docId = $state('');
	let ingesting = $state(false);
	let result = $state<{
		status: 'accepted' | 'skipped' | 'error';
		message: string;
		tabs_found?: number;
		documents_prepared?: number;
	} | null>(null);

	async function handleIngest() {
		if (!docId.trim()) return;

		ingesting = true;
		result = null;

		const token = localStorage.getItem('access_token');
		if (!token) {
			result = { status: 'error', message: 'You must be logged in to ingest documents.' };
			ingesting = false;
			return;
		}

		try {
			const res = await fetch('http://localhost:8000/datastore/ingest', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${token}`
				},
				body: JSON.stringify({ doc_id: docId.trim() })
			});

			if (!res.ok) {
				const err = await res.json().catch(() => ({ detail: 'Request failed' }));
				result = { status: 'error', message: err.detail || `Error ${res.status}` };
			} else {
				const data = await res.json();
				result = data;
			}
		} catch (e: any) {
			result = { status: 'error', message: e.message || 'Network error' };
		} finally {
			ingesting = false;
		}
	}

	function handleClose() {
		open = false;
		// Reset state after sheet close animation
		setTimeout(() => {
			docId = '';
			result = null;
		}, 300);
	}

	function extractDocId(input: string): string {
		// Support pasting full Google Docs URLs
		const match = input.match(/\/document\/d\/([a-zA-Z0-9_-]+)/);
		return match ? match[1] : input;
	}

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		docId = extractDocId(target.value);
	}
</script>

<Sheet.Root bind:open>
	<Sidebar.MenuItem>
		<Sidebar.MenuButton
			tooltipContent="Ingest Document"
			onclick={() => (open = true)}
		>
			<Upload class="size-4" />
			<span>Ingest Document</span>
		</Sidebar.MenuButton>
	</Sidebar.MenuItem>

	<Sheet.Content side="left" class="w-[400px] sm:w-[440px]">
		<Sheet.Header>
			<Sheet.Title class="flex items-center gap-2">
				<FileText class="size-5" />
				Ingest Google Doc
			</Sheet.Title>
			<Sheet.Description>
				Enter a Google Doc ID or paste a URL to ingest its letter tabs into the datastore.
			</Sheet.Description>
		</Sheet.Header>

		<div class="flex flex-col gap-4 px-1 py-6">
			<div class="space-y-2">
				<label for="doc-id-input" class="text-sm font-medium text-foreground">
					Document ID or URL
				</label>
				<Input
					id="doc-id-input"
					placeholder="Paste Google Doc URL or document ID..."
					value={docId}
					oninput={handleInput}
					disabled={ingesting}
				/>
				{#if docId}
					<p class="text-xs text-muted-foreground font-mono truncate">
						ID: {docId}
					</p>
				{/if}
			</div>

			<Button
				onclick={handleIngest}
				disabled={!docId.trim() || ingesting}
				class="w-full"
			>
				{#if ingesting}
					<Loader2 class="size-4 mr-2 animate-spin" />
					Ingesting...
				{:else}
					<Upload class="size-4 mr-2" />
					Start Ingestion
				{/if}
			</Button>

			{#if result}
				<div
					class="rounded-lg border p-4 text-sm {result.status === 'error'
						? 'border-destructive/50 bg-destructive/10 text-destructive'
						: result.status === 'skipped'
							? 'border-yellow-500/50 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400'
							: 'border-green-500/50 bg-green-500/10 text-green-700 dark:text-green-400'}"
				>
					<div class="flex items-start gap-2">
						{#if result.status === 'error'}
							<AlertCircle class="size-4 mt-0.5 shrink-0" />
						{:else}
							<CheckCircle class="size-4 mt-0.5 shrink-0" />
						{/if}
						<div class="space-y-1">
							<p class="font-medium">{result.message}</p>
							{#if result.tabs_found !== undefined}
								<p class="text-xs opacity-80">
									Tabs found: {result.tabs_found} · Documents queued: {result.documents_prepared}
								</p>
							{/if}
						</div>
					</div>
				</div>
			{/if}
		</div>

		<Sheet.Footer>
			<Sheet.Close>
				<Button variant="outline" onclick={handleClose}>Close</Button>
			</Sheet.Close>
		</Sheet.Footer>
	</Sheet.Content>
</Sheet.Root>
