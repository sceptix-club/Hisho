import type { User } from '$lib/types/user';
import { api, clearTokens } from '$lib/api';

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
			const res = await api('/auth/me');
			if (!res.ok) throw new Error('Not authenticated');
			user = await res.json();
		} catch {
			user = null;
		} finally {
			loading = false;
		}
	},
	async logout() {
		try {
			await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
		} catch {
			// ignore network errors, clear local state regardless
		}
		clearTokens();
		user = null;
		window.location.assign('/login');
	}
};
