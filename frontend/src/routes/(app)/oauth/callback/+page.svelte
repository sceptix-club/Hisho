<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		const hash = window.location.hash;
		const token = hash.replace(/^#token=/, '');
		if (token) {
			localStorage.setItem('access_token', token);
		}
		goto('/', { replaceState: true });
	});
</script>

<p class="text-muted-foreground p-8 text-center">Completing sign-in...</p>
