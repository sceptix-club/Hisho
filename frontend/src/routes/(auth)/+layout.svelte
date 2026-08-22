<script lang="ts">
	let { children } = $props();
</script>

<div>
	<div class="relative min-h-svh">
		{@render children()}
		<div
			class="absolute bottom-0 left-0 right-0 text-center p-4 pb-6 text-sm text-muted-foreground"
		>
			Made with love by <a href="https://www.sceptix.in/">The Sceptix Club</a>
		</div>
	</div>
</div>
