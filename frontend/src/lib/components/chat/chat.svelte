<script lang="ts">
	import { fly } from 'svelte/transition';
	import type { ChatMessage } from '$lib/types/chat';
	import Message from '$lib/components/ui/message/message.svelte';
	import { Avatar, AvatarImage, AvatarFallback } from '$lib/components/ui/avatar/index';
	import { Bubble } from '$lib/components/ui/bubble/index.js';
	import Input from '$lib/components/ui/input/input.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import { SendHorizontal } from '@lucide/svelte';

	let input = $state('');

	async function send() {
		if (!input) return;

		messages.push({ who: 'me', text: input });
		input = '';

		// TODO: replace with real API call
		await new Promise((r) => setTimeout(r, 800));
		messages.push({ who: 'them', text: 'Interesting, tell me more!' });
	}

	let messages: ChatMessage[] = $state([
		{ who: 'them', text: 'Hey! How are you doing?' },
		{ who: 'me', text: "I'm great, thanks! Working on this chat UI." },
		{ who: 'them', text: 'Nice! Let me know if you need any help.' }
	]);
</script>

<div transition:fly class="flex h-full flex-col">
	<div class="flex-1 min-h-0 overflow-y-auto p-4">
		<div class="flex flex-col gap-3">
			{#each messages as message}
				<div transition:fly={{ y: 10, duration: 250 }}>
					<Message align={message.who === 'me' ? 'end' : 'start'}>
						<div
							data-slot="message-avatar"
							class="flex size-8 shrink-0 items-center justify-center self-end overflow-hidden rounded-full bg-muted"
						>
							<Avatar size="sm">
								<AvatarImage
									src={message.who === 'me' ? '/goal.gif' : '/hamster.webp'}
									alt={message.who === 'me' ? 'you' : 'assistant'}
								/>
								<AvatarFallback>{message.who === 'me' ? 'ME' : 'AI'}</AvatarFallback>
							</Avatar>
						</div>
						<div
							data-slot="message-content"
							class={message.who === 'me'
								? 'flex w-full min-w-0 flex-col gap-2.5 wrap-break-word items-end'
								: 'flex w-full min-w-0 flex-col gap-2.5 wrap-break-word items-start'}
						>
							<Bubble variant={message.who === 'me' ? 'sent' : 'received'}>
								<div data-slot="bubble-content">{message.text}</div>
							</Bubble>
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
