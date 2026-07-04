<script lang="ts">
	import { cn } from '$lib/utils.js';

	let {
		align = 'start',
		class: className,
		children
	}: {
		align?: 'start' | 'end';
		class?: string;
		children?: import('svelte').Snippet;
	} = $props();
</script>

<div
	data-slot="message"
	data-align={align}
	class={cn(
		'group/message relative flex w-full min-w-0 gap-2 text-sm data-[align=end]:flex-row-reverse',
		className
	)}
>
	{@render children?.()}
</div>
