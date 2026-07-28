<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { Skeleton } from '$lib/components/ui/skeleton';

	type SessionSummary = { id: string; title: string; last_update: number };
	let sessions = $state<SessionSummary[] | null>(null);

	$effect(() => {
		(async () => {
			await auth.load();
			const uid = auth.user?.id ?? 'default';
			const res = await fetch(`http://localhost:8000/sessions?user_id=${uid}`);
			sessions = res.ok ? await res.json() : [];
		})();
	});
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
				<li>
					<a href="/chat?session={s.id}" class="hover:bg-muted block rounded-md px-3 py-2">
						<span class="block truncate text-sm">{s.title}</span>
						<span class="text-muted-foreground text-xs">
							{new Date(s.last_update * 1000).toLocaleString()}
						</span>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</div>
