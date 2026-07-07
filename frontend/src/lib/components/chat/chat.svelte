<script lang="ts">
	import { fly } from 'svelte/transition';
	import type { ChatStream, ChatMessage } from '$lib/types/chat';
	import Message from '$lib/components/ui/message/message.svelte';
	import { Avatar, AvatarImage, AvatarFallback } from '$lib/components/ui/avatar/index';
	import { Bubble } from '$lib/components/ui/bubble/index.js';
	import Input from '$lib/components/ui/input/input.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import { SendHorizontal } from '@lucide/svelte';
	import { Skeleton } from '../ui/skeleton';

	let input = $state('');
	let messages = $state<ChatMessage[]>([]);

	let buf = '';

	async function send() {
		if (!input) return;

		const query = input;
		input = '';

		messages.push({
			role: 'user',
			text: query,
			thought: '',
			tool_calls: [],
			status: 'complete'
		});

		messages.push({
			role: 'assistant',
			text: '',
			thought: '',
			tool_calls: [],
			status: 'streaming'
		});
		const reply = messages[messages.length - 1];

		const res = await fetch('http://localhost:8000/chat/stream', {
			method: 'POST',
			body: JSON.stringify({ query, user_id: 'default', session_id: null }),
			headers: { 'Content-Type': 'application/json' }
		});
		if (!res.ok || !res.body) {
			reply.status = 'complete';
			return;
		}

		const reader = res.body.getReader();
		const dec = new TextDecoder();

		while (true) {
			const { done, value } = await reader.read();
			if (done) break;
			buf += dec.decode(value, { stream: true });
			const parts = buf.split('\n\n');
			buf = parts.pop() || '';
			for (const part of parts) {
				if (!part) continue;
				for (const line of part.split('\n')) {
					if (!line.startsWith('data: ')) continue;
					try {
						const data = JSON.parse(line.slice(6)) as ChatStream;
						if (data.type === 'delta') {
							reply.text += data.text;
						} else if (data.type === 'message') {
							const final_status = JSON.parse(data.text).final_status;
							reply.text = final_status;
						} else if (data.type === 'thought') {
							reply.thought += data.text;
						} else if (data.type === 'tool_call') {
							reply.tool_calls.push({ name: data.name, args: data.args });
						} else if (data.type === 'tool_result') {
							const tc = reply.tool_calls.find(
								(t) => t.name === data.name && t.result === undefined
							);
							if (tc) tc.result = data.result;
							else reply.tool_calls.push({ name: data.name, result: data.result });
						} else if (data.type === 'done') {
							reply.status = 'complete';
						}
					} catch {
						// ignore malformed SSE chunk
					}
				}
			}
		}
	}
</script>

<div transition:fly class="flex h-full flex-col">
	<div class="flex-1 min-h-0 overflow-y-auto p-4">
		<div class="flex flex-col gap-3">
			{#each messages as msg, i (i)}
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
							{:else}
								<Bubble variant="sent">
									<div data-slot="bubble-content">{msg.text}</div>
								</Bubble>
							{/if}
						</div>
					</Message>
				</div>
			{/each}
		</div>
	</div>
	<div class="border-t p-10">
		<form onsubmit={send} class="flex gap-2">
			<Input bind:value={input} placeholder="Type a message..." class="flex-1 border-none" />
			<Button type="submit" disabled={!input}>
				<SendHorizontal />
			</Button>
		</form>
	</div>
</div>
