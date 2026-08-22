const TOKEN_KEY = 'access_token';

export class ApiError extends Error {
	status: number;
	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

export function getToken(): string | null {
	return localStorage.getItem(TOKEN_KEY);
}

export function clearTokens(): void {
	localStorage.removeItem(TOKEN_KEY);
}

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
	if (!refreshing) {
		refreshing = (async () => {
			try {
				const res = await fetch('/auth/refresh', {
					method: 'POST',
					credentials: 'include'
				});
				if (!res.ok) return null;
				const data = await res.json();
				localStorage.setItem(TOKEN_KEY, data.access_token);
				return data.access_token as string;
			} catch {
				return null;
			} finally {
				refreshing = null;
			}
		})();
	}
	return refreshing;
}

export async function api(input: string, init: RequestInit = {}, retry = true): Promise<Response> {
	const headers = new Headers(init.headers);
	const token = getToken();
	if (token && !headers.has('Authorization')) {
		headers.set('Authorization', `Bearer ${token}`);
	}

	const res = await fetch(input, { ...init, headers });

	if (res.status === 401 && retry && input !== '/auth/refresh') {
		const newToken = await refreshAccessToken();
		if (newToken) {
			return api(input, init, false);
		}
		clearTokens();
		window.location.assign('/login');
		throw new ApiError(401, 'Session expired');
	}

	return res;
}
