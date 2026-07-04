<script lang="ts">
	import { cn } from '$lib/utils.js';

	let {
		variant = 'received',
		class: className,
		children,
		...restProps
	}: {
		variant?: 'received' | 'sent';
		class?: string;
		children?: import('svelte').Snippet;
	} & Record<string, unknown> = $props();
</script>

<div
	data-slot="bubble"
	data-variant={variant}
	class={cn(
		'max-w-[75%] rounded-2xl px-3 py-2 text-sm break-words data-[variant=sent]:bg-primary data-[variant=sent]:text-primary-foreground data-[variant=received]:bg-muted',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</div>
