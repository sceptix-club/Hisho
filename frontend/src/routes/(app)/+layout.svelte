<script lang="ts">
	import { SunIcon } from '@lucide/svelte';
	import { MoonIcon } from '@lucide/svelte';
	import { toggleMode } from 'mode-watcher';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index';
	import AppSidebar from '$lib/components/app-sidebar.svelte';

	let { children } = $props();
</script>

<Sidebar.Provider>
	<AppSidebar />
	<main class="flex flex-1 flex-col h-dvh overflow-hidden">
		<Sidebar.Trigger />
		<div class="flex-1 overflow-hidden">
			{@render children()}
		</div>
	</main>
	<div>
		<Button onclick={toggleMode} variant="ghost" size="icon">
			<SunIcon
				class="h-[1.2rem]  scale-100 rotate-0 !transition-all dark:scale-0 dark:-rotate-90"
			/>
			<MoonIcon
				class="absolute h-[1.2rem]  scale-0 rotate-90 !transition-all dark:scale-100 dark:rotate-0"
			/>
			<span class="sr-only">Toggle theme</span>
		</Button>
	</div>
</Sidebar.Provider>
