<script lang="ts">
	import BookOpenIcon from '@lucide/svelte/icons/book-open';
	import BotIcon from '@lucide/svelte/icons/bot';
	import LifeBuoyIcon from '@lucide/svelte/icons/life-buoy';
	import SendIcon from '@lucide/svelte/icons/send';
	import Settings2Icon from '@lucide/svelte/icons/settings-2';
	import Database from '@lucide/svelte/icons/database';
	import NavMain from './nav-main.svelte';
	import NavProjects from './nav-projects.svelte';
	import NavSecondary from './nav-secondary.svelte';
	import NavUser from './nav-user.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import Skeleton from '$lib/components/ui/skeleton/skeleton.svelte';

	import type { ComponentProps } from 'svelte';
	import { FileText, Mail, MessageSquare, Presentation } from '@lucide/svelte';
	import type { User } from '$lib/types/user';

	let user = $state<User | null>(null);
	let loading = $state(true);

	$effect(() => {
		const token = localStorage.getItem('access_token');
		if (!token) {
			user = null;
			loading = false;
			return;
		}
		fetch('/auth/me', {
			headers: { Authorization: `Bearer ${token}` }
		})
			.then((res) => {
				if (!res.ok) throw new Error('Not Authenticated');
				return res.json();
			})
			.then((data) => (user = data))
			.catch(() => (user = null))
			.finally(() => (loading = false));
	});

	const data = {
		navMain: [
			{
				title: 'Chat',
				url: '/chat',
				icon: MessageSquare,
				isActive: true,
				items: [
					{ title: 'History', url: '/history' },
					{ title: 'Starred', url: '/starred' }
				]
			},
			{
				title: 'Models',
				url: '#',
				icon: BotIcon,
				items: [
					{ title: 'Letter Writer', url: '#' },
					{ title: 'Email Writer', url: '#' }
				]
			},
			{
				title: 'DataStore',
				url: '#',
				icon: Database,
				items: [
					{ title: 'Officials', url: '#' },
					{ title: 'Letters', url: '#' }
				]
			},
			{
				title: 'Documentation',
				url: '#',
				icon: BookOpenIcon,
				items: [
					{ title: 'Introduction', url: '#' },
					{ title: 'Get Started', url: '#' },
					{ title: 'Tutorials', url: '#' },
					{ title: 'Changelog', url: '#' }
				]
			},
			{
				title: 'Settings',
				url: '#',
				icon: Settings2Icon,
				items: [
					{ title: 'General', url: '#' },
					{ title: 'Team', url: '#' },
					{ title: 'Billing', url: '#' },
					{ title: 'Limits', url: '#' }
				]
			}
		],
		navSecondary: [
			{ title: 'Support', url: '#', icon: LifeBuoyIcon },
			{ title: 'Feedback', url: '#', icon: SendIcon }
		],
		projects: [
			{ name: 'Workshops', url: '#', icon: Presentation },
			{ name: 'Letters', url: '#', icon: Mail },
			{ name: 'Reports', url: '#', icon: FileText }
		]
	};

	let { ref = $bindable(null), ...restProps }: ComponentProps<typeof Sidebar.Root> = $props();
</script>

<Sidebar.Root bind:ref variant="inset" {...restProps}>
	<Sidebar.Header>
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton size="lg">
					{#snippet child({ props })}
						<a href="/" {...props}>
							<div class="size-8 overflow-hidden rounded-lg">
								<img src="/hamster.webp" alt="Hisho" class="size-full object-cover" />
							</div>
							<div class="grid flex-1 text-start text-sm leading-tight">
								<span class="truncate font-medium">Hisho</span>
								<span class="truncate text-xs">The Sceptix Club</span>
							</div>
						</a>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Header>
	<Sidebar.Content>
		<NavMain items={data.navMain} />
		<NavProjects projects={data.projects} />
		<NavSecondary items={data.navSecondary} class="mt-auto" />
	</Sidebar.Content>
	<Sidebar.Footer>
		{#if loading}
			<div class="flex items-center gap-2 p-2">
				<Skeleton class="size-8 rounded-lg" />
				<div class="grid flex-1 gap-1">
					<Skeleton class="h-3 w-24" />
					<Skeleton class="h-3 w-32" />
				</div>
			</div>
		{:else if user}
			<NavUser {user} />
		{:else}
			<a href="/login" class="text-muted-foreground hover:text-foreground p-2 text-sm">Sign in</a>
		{/if}
	</Sidebar.Footer>
</Sidebar.Root>
