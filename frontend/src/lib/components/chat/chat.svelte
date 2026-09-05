<script lang="ts">
	import { fly } from 'svelte/transition';
	import type { ChatMessage } from '$lib/types/chat';
	import Message from '$lib/components/ui/message/message.svelte';
	import { Avatar, AvatarImage, AvatarFallback } from '$lib/components/ui/avatar/index';
	import { Bubble } from '$lib/components/ui/bubble/index.js';
	import Input from '$lib/components/ui/input/input.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import { SendHorizontal, SquarePen, ExternalLink } from '@lucide/svelte';
	import { Skeleton } from '../ui/skeleton';
	import { session } from '$lib/stores/session.svelte';
	import { page } from '$app/state';

	let input = $state('');

	$effect(() => {
		const param = page.url.searchParams.get('session');
		session.syncFromUrl(param);
	});

	async function handleSend(e: Event) {
		e.preventDefault();
		if (!input.trim() || session.sending) return;
		const q = input;
		input = '';
		await session.send(q);
	}

	function newChat() {
		session.reset();
	}
</script>

<div transition:fly class="flex h-full flex-col">
	<div class="flex-1 min-h-0 overflow-y-auto p-4">
		<div class="flex flex-col gap-3">
			{#if session.error}
				<div
					class="mx-auto mt-10 flex max-w-md flex-col items-center gap-3 rounded-md border border-red-500/40 bg-red-500/10 p-4 text-center"
				>
					<p class="text-sm text-red-500">⚠ {session.error}</p>
					<div class="flex gap-2">
						<Button type="button" variant="outline" onclick={() => session.retry()}>Retry</Button>
						<Button type="button" variant="ghost" onclick={newChat}>New chat</Button>
					</div>
				</div>
			{:else if session.loading}
				<div class="flex flex-col gap-3">
					<Skeleton class="h-16 w-3/4" />
					<Skeleton class="h-16 w-2/3" />
				</div>
			{:else}
				{#each session.messages as msg, i (i)}
					<div transition:fly={{ y: 10, duration: 250 }}>
						<Message align={msg.role === 'user' ? 'end' : 'start'}>
							<div
								data-slot="message-avatar"
								class="flex size-8 shrink-0 items-center justify-center self-end overflow-hidden rounded-full bg-muted"
							>
								<Avatar size="sm">
									<AvatarImage
										src={msg.role === 'user' ? '/goal.gif' : '/hamster.webp'}
										alt={msg.role === 'user' ? 'you' : 'assistant'}
									/>
									<AvatarFallback>{msg.role === 'user' ? 'ME' : 'AI'}</AvatarFallback>
								</Avatar>
							</div>
							<div
								data-slot="message-content"
								class={msg.role === 'user'
									? 'flex w-full min-w-0 flex-col gap-2.5 wrap-break-word items-end'
									: 'flex w-full min-w-0 flex-col gap-2.5 wrap-break-word items-start'}
							>
								{#if msg.role === 'assistant'}
									{#if msg.thought}
										<label
											for="thought-{i}"
											class="flex items-start gap-1 cursor-pointer text-sm text-gray-400 italic"
										>
											<input type="checkbox" id="thought-{i}" class="hidden peer" />
											<span
												class="mt-0.5 text-xs transition-transform peer-checked:rotate-180 select-none shrink-0"
												>...
											</span>
											<span
												class="whitespace-pre-wrap overflow-hidden line-clamp-1 peer-checked:line-clamp-none"
												>{msg.thought}</span
											>
										</label>
									{/if}
									{#each msg.tool_calls as tc, ti (ti)}
										<div class="text-sm text-blue-500 font-mono">🔧 {tc.name}</div>
									{/each}
									<Bubble variant="received">
										<div data-slot="bubble-content" class="whitespace-pre-wrap">
											{#if !msg.text && msg.status === 'streaming'}
												<Skeleton class="h-4 w-[250px] bg-muted-foreground/20" />
											{:else}
												{msg.text || ''}
											{/if}
										</div>
									</Bubble>
									{#if msg.docUrl}
										<a
											href={msg.docUrl}
											target="_blank"
											rel="noopener noreferrer"
											class="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
										>
											<ExternalLink class="size-4" />
											Open in Google Docs
										</a>
									{/if}
								{:else}
									<Bubble variant="sent">
										<div data-slot="bubble-content">{msg.text}</div>
									</Bubble>
								{/if}
							</div>
						</Message>
					</div>
				{/each}
			{/if}
		</div>
	</div>
	<div class="border-t p-10">
		<form onsubmit={handleSend} class="flex gap-2">
			<Button
				type="button"
				variant="ghost"
				onclick={newChat}
				disabled={!session.messages.length && !session.sessionId}
				title="New chat"
			>
				<SquarePen />
			</Button>
			<Input
				bind:value={input}
				placeholder={session.sending ? 'Waiting for response...' : 'Type a message...'}
				class="flex-1 border-none"
				disabled={session.sending}
			/>
			<Button type="submit" disabled={!input.trim() || session.sending}>
				<SendHorizontal />
			</Button>
		</form>
	</div>
</div>
