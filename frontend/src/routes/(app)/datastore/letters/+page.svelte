<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import Input from '$lib/components/ui/input/input.svelte';
	import Label from '$lib/components/ui/label/label.svelte';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import * as knowledge from '$lib/api/knowledge';
	import { Delete, DeleteIcon, Pencil, Trash } from '@lucide/svelte';

	let letterTypes = $state<knowledge.LetterType[] | null>(null);
	let roles = $state<string[]>([]);
	let error = $state('');
	let showForm = $state(false);
	let editingId = $state<string | null>(null);
	let form = $state<{
		id: string;
		name: string;
		description: string;
		template: string;
		approval_chain: knowledge.ApprovalChainStep[];
	}>({
		id: '',
		name: '',
		description: '',
		template: '',
		approval_chain: []
	});

	async function load() {
		await auth.load();
		try {
			const [lts, offs] = await Promise.all([
				knowledge.listLetterTypes(),
				knowledge.listOfficials()
			]);
			letterTypes = lts;
			roles = [...new Set(offs.map((o) => o.role))].sort();
			error = '';
		} catch (e) {
			error = (e as Error).message;
			letterTypes = [];
		}
	}

	function openNew() {
		editingId = null;
		form = { id: '', name: '', description: '', template: '', approval_chain: [] };
		showForm = true;
	}

	function openEdit(lt: knowledge.LetterType) {
		editingId = lt.id;
		form = {
			id: lt.id,
			name: lt.name,
			description: lt.description,
			template: lt.template,
			approval_chain: lt.approval_chain.map((s) => ({ ...s }))
		};
		showForm = true;
	}

	function addStep() {
		const next = form.approval_chain.length + 1;
		form.approval_chain = [
			...form.approval_chain,
			{ step: next, role: roles[0] ?? '', action: '' }
		];
	}

	function removeStep(i: number) {
		form.approval_chain = form.approval_chain.filter((_, idx) => idx !== i);
	}

	async function save() {
		try {
			const body = {
				name: form.name,
				description: form.description,
				template: form.template,
				approval_chain: [...form.approval_chain]
					.map((s) => ({ ...s, step: Number(s.step) }))
					.sort((a, b) => a.step - b.step)
			};
			if (editingId) await knowledge.updateLetterType(editingId, body);
			else await knowledge.createLetterType({ id: form.id, ...body });
			showForm = false;
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function remove(id: string) {
		if (!confirm('Delete this letter type?')) return;
		try {
			await knowledge.deleteLetterType(id);
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	onMount(load);
</script>

<div class="mx-auto w-full max-w-3xl p-6">
	<div class="mb-4 flex items-center justify-between">
		<h1 class="text-lg font-semibold">Letter Types</h1>
		<Button onclick={openNew}>Add letter type</Button>
	</div>

	{#if error}
		<p class="mb-3 text-sm text-red-500">{error}</p>
	{/if}

	{#if letterTypes === null}
		<div class="flex flex-col gap-2">
			<Skeleton class="h-10 w-full" />
			<Skeleton class="h-10 w-full" />
		</div>
	{:else if !letterTypes.length}
		<p class="text-muted-foreground text-sm">No letter types yet.</p>
	{:else}
		<table class="w-full text-sm">
			<thead>
				<tr class="text-left text-muted-foreground">
					<th class="p-2">ID</th>
					<th class="p-2">Name</th>
					<th class="p-2">Description</th>
					<th class="p-2"></th>
				</tr>
			</thead>
			<tbody>
				{#each letterTypes as lt (lt.id)}
					<tr class="border-t">
						<td class="p-2">{lt.id}</td>
						<td class="p-2">{lt.name}</td>
						<td class="p-2">{lt.description}</td>
						<td class="p-2 text-right">
							<Button variant="ghost" size="sm" onclick={() => openEdit(lt)}>
								<Pencil class="size-4" /></Button
							>
							<Button variant="ghost" size="sm" onclick={() => remove(lt.id)}>
								<Trash class="size-4" />
							</Button>
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
		<div
			class="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-background p-6"
			onclick={(e) => e.stopPropagation()}
		>
			<h2 class="mb-4 text-base font-semibold">
				{editingId ? 'Edit letter type' : 'New letter type'}
			</h2>
			<div class="flex flex-col gap-3">
				<div class="flex flex-col gap-1">
					<Label>ID (slug)</Label>
					<Input
						bind:value={form.id}
						placeholder="event_permission_request"
						disabled={!!editingId}
					/>
				</div>
				<div class="flex flex-col gap-1">
					<Label>Name</Label>
					<Input bind:value={form.name} />
				</div>
				<div class="flex flex-col gap-1">
					<Label>Description</Label>
					<Input bind:value={form.description} />
				</div>
				<div class="flex flex-col gap-1">
					<Label>Template</Label>
					<textarea
						bind:value={form.template}
						class="w-full rounded-md border border-input bg-transparent p-2 text-sm"
						rows="6"></textarea>
				</div>

				<div class="flex flex-col gap-2">
					<div class="flex items-center justify-between">
						<Label>Approval chain</Label>
						<Button variant="ghost" size="sm" onclick={addStep}>Add step</Button>
					</div>
					{#each form.approval_chain as step, i (i)}
						<div class="flex items-end gap-2 rounded-md border border-input p-2">
							<div class="flex flex-col gap-1">
								<Label class="text-xs">Step</Label>
								<Input type="number" bind:value={step.step} class="w-16" />
							</div>
							<div class="flex flex-1 flex-col gap-1">
								<Label class="text-xs">Role</Label>
								<select
									bind:value={step.role}
									class="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
								>
									{#each roles as r (r)}
										<option value={r}>{r}</option>
									{/each}
								</select>
							</div>
							<div class="flex flex-1 flex-col gap-1">
								<Label class="text-xs">Action</Label>
								<Input bind:value={step.action} placeholder="Approve" />
							</div>
							<Button variant="ghost" size="sm" onclick={() => removeStep(i)}>✕</Button>
						</div>
					{/each}
				</div>
			</div>
			<div class="mt-4 flex justify-end gap-2">
				<Button variant="ghost" onclick={() => (showForm = false)}>Cancel</Button>
				<Button onclick={save} disabled={!form.id || !form.name}>Save</Button>
			</div>
		</div>
	</div>
{/if}
