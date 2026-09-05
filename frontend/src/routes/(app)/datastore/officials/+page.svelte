<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import Input from '$lib/components/ui/input/input.svelte';
	import Label from '$lib/components/ui/label/label.svelte';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import * as knowledge from '$lib/api/knowledge';

	let officials = $state<knowledge.Official[] | null>(null);
	let error = $state('');
	let showForm = $state(false);
	let editingId = $state<string | null>(null);
	let form = $state<knowledge.OfficialInput>({
		name: '',
		role: '',
		organization: '',
		address: '',
		signature: ''
	});

	async function load() {
		await auth.load();
		try {
			officials = await knowledge.listOfficials();
			error = '';
		} catch (e) {
			error = (e as Error).message;
			officials = [];
		}
	}

	function openNew() {
		editingId = null;
		form = { name: '', role: '', organization: '', address: '', signature: '' };
		showForm = true;
	}

	function openEdit(o: knowledge.Official) {
		editingId = o.id;
		form = {
			name: o.name,
			role: o.role,
			organization: o.organization,
			address: o.address,
			signature: o.signature
		};
		showForm = true;
	}

	async function save() {
		try {
			if (editingId) await knowledge.updateOfficial(editingId, form);
			else await knowledge.createOfficial(form);
			showForm = false;
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function remove(id: string) {
		if (!confirm('Delete this official?')) return;
		try {
			await knowledge.deleteOfficial(id);
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	onMount(load);
</script>

<div class="mx-auto w-full max-w-3xl p-6">
	<div class="mb-4 flex items-center justify-between">
		<h1 class="text-lg font-semibold">Officials</h1>
		<Button onclick={openNew}>Add official</Button>
	</div>

	{#if error}
		<p class="mb-3 text-sm text-red-500">{error}</p>
	{/if}

	{#if officials === null}
		<div class="flex flex-col gap-2">
			<Skeleton class="h-10 w-full" />
			<Skeleton class="h-10 w-full" />
		</div>
	{:else if !officials.length}
		<p class="text-muted-foreground text-sm">No officials yet.</p>
	{:else}
		<table class="w-full text-sm">
			<thead>
				<tr class="text-left text-muted-foreground">
					<th class="p-2">Name</th>
					<th class="p-2">Role</th>
					<th class="p-2">Organization</th>
					<th class="p-2"></th>
				</tr>
			</thead>
			<tbody>
				{#each officials as o (o.id)}
					<tr class="border-t">
						<td class="p-2">{o.name}</td>
						<td class="p-2">{o.role}</td>
						<td class="p-2">{o.organization}</td>
						<td class="p-2 text-right">
							<Button variant="secondary" size="sm" onclick={() => openEdit(o)}>Edit</Button>
							<Button variant="destructive" size="sm" onclick={() => remove(o.id)}>Delete</Button>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</div>

{#if showForm}
	<div
		class="fixed inset-0 flex items-center justify-center bg-black/40 p-4"
		onclick={() => (showForm = false)}
	>
		<div class="w-full max-w-md rounded-lg bg-background p-6" onclick={(e) => e.stopPropagation()}>
			<h2 class="mb-4 text-base font-semibold">{editingId ? 'Edit official' : 'New official'}</h2>
			<div class="flex flex-col gap-3">
				<div class="flex flex-col gap-1">
					<Label>Name</Label>
					<Input bind:value={form.name} />
				</div>
				<div class="flex flex-col gap-1">
					<Label>Role</Label>
					<Input bind:value={form.role} placeholder="e.g. HOD CS" />
				</div>
				<div class="flex flex-col gap-1">
					<Label>Organization</Label>
					<Input bind:value={form.organization} />
				</div>
				<div class="flex flex-col gap-1">
					<Label>Address</Label>
					<Input bind:value={form.address} />
				</div>
				<div class="flex flex-col gap-1">
					<Label>Signature</Label>
					<textarea
						bind:value={form.signature}
						class="w-full rounded-md border border-input bg-transparent p-2 text-sm"
						rows="3"></textarea>
				</div>
			</div>
			<div class="mt-4 flex justify-end gap-2">
				<Button variant="ghost" onclick={() => (showForm = false)}>Cancel</Button>
				<Button onclick={save} disabled={!form.name || !form.role}>Save</Button>
			</div>
		</div>
	</div>
{/if}
