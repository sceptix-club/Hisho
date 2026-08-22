import type { User } from '$lib/types/user';

let user = $state<User | null>(null);
let loading = $state(true);
let loaded = false;

export const auth = {
	get user() {
		return user;
	},
	get loading() {
		return loading;
	},
	async load() {
		if (loaded) return;
		loaded = true;
		const token = localStorage.getItem('access_token');
		if (!token) {
			loading = false;
			return;
		}
		try {
			const res = await fetch('/auth/me', {
				headers: { Authorization: `Bearer ${token}` }
			});
			if (!res.ok) throw new Error('Not authenticated');
			user = await res.json();
		} catch {
			user = null;
		} finally {
			loading = false;
		}
	}
};
