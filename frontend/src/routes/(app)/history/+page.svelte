<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { api } from '$lib/api';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import Button from '$lib/components/ui/button/button.svelte';
	import { Trash2 } from '@lucide/svelte';

	type SessionSummary = { id: string; title: string; last_update: number };
	let sessions = $state<SessionSummary[] | null>(null);

	$effect(() => {
		(async () => {
			await auth.load();
			const uid = auth.user?.id ?? 'default';
			const res = await api(`/sessions?user_id=${uid}`);
			sessions = res.ok ? await res.json() : [];
		})();
	});

	async function removeSession(id: string) {
		if (!confirm('Delete this conversation? This cannot be undone.')) return;
		const res = await api(`/sessions/${id}`, { method: 'DELETE' });
		if (res.ok) {
			sessions = (sessions ?? []).filter((s) => s.id !== id);
		} else {
			alert('Failed to delete conversation.');
		}
	}
</script>

<div class="mx-auto w-full max-w-2xl p-6">
	<h1 class="mb-4 text-lg font-semibold">Chat history</h1>
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
