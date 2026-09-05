<script lang="ts">
	import type { SessionSummary } from '$lib/types/chat';
	import { listSessions, deleteSession } from '$lib/api/sessions';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import Button from '$lib/components/ui/button/button.svelte';
	import { Trash2, SquarePen } from '@lucide/svelte';

	let sessions = $state<SessionSummary[] | null>(null);

	$effect(() => {
		(async () => {
			try {
				sessions = await listSessions();
			} catch {
				sessions = [];
			}
		})();
	});

	async function removeSession(id: string) {
		if (!confirm('Delete this conversation? This cannot be undone.')) return;
		try {
			await deleteSession(id);
			sessions = (sessions ?? []).filter((s) => s.id !== id);
		} catch {
			alert('Failed to delete conversation.');
		}
	}
</script>

<div class="mx-auto w-full max-w-2xl p-6">
	<div class="mb-4 flex items-center justify-between">
		<h1 class="text-lg font-semibold">Chat history</h1>
		<Button href="/chat" variant="outline" size="sm">
			<SquarePen class="mr-1 size-4" /> New chat
		</Button>
	</div>
	{#if sessions === null}
		<div class="flex flex-col gap-2">
			<Skeleton class="h-12 w-full" />
			<Skeleton class="h-12 w-full" />
			<Skeleton class="h-12 w-full" />
		</div>
	{:else if !sessions.length}
		<p class="text-muted-foreground text-sm">No conversations yet.</p>
	{:else}
		<ul class="flex flex-col gap-1">
			{#each sessions as s (s.id)}
				<li class="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-muted">
					<a href="/chat?session={s.id}" class="min-w-0 flex-1">
						<span class="block truncate text-sm">{s.title}</span>
						<span class="text-muted-foreground text-xs">
							{new Date(s.last_update * 1000).toLocaleString()}
						</span>
					</a>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						title="Delete conversation"
						onclick={() => removeSession(s.id)}
					>
						<Trash2 class="size-4" />
					</Button>
				</li>
			{/each}
		</ul>
	{/if}
</div>
