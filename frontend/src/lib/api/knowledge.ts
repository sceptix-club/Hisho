const BASE = '';

function authHeaders(): Record<string, string> {
	const token = localStorage.getItem('access_token');
	return token ? { Authorization: `Bearer ${token}` } : {};
}

function jsonHeaders(): Record<string, string> {
	return { 'Content-Type': 'application/json', ...authHeaders() };
}

export type Official = {
	id: string;
	name: string;
	role: string;
	organization: string;
	address: string;
	signature: string;
	created_at?: string;
	updated_at?: string;
};

export type ApprovalChainStep = { step: number; role: string; action: string };

export type LetterType = {
	id: string;
	name: string;
	description: string;
	approval_chain: ApprovalChainStep[];
	template: string;
};

export type OfficialInput = Omit<Official, 'id' | 'created_at' | 'updated_at'>;

export async function listOfficials(): Promise<Official[]> {
	const res = await fetch(`${BASE}/officials`, { headers: authHeaders() });
	if (!res.ok) throw new Error('Failed to load officials');
	return res.json();
}

export async function createOfficial(body: OfficialInput): Promise<Official> {
	const res = await fetch(`${BASE}/officials`, {
		method: 'POST',
		headers: jsonHeaders(),
		body: JSON.stringify(body)
	});
	if (!res.ok) throw new Error('Failed to create official');
	return res.json();
}

export async function updateOfficial(id: string, body: Partial<OfficialInput>): Promise<Official> {
	const res = await fetch(`${BASE}/officials/${id}`, {
		method: 'PUT',
		headers: jsonHeaders(),
		body: JSON.stringify(body)
	});
	if (!res.ok) throw new Error('Failed to update official');
	return res.json();
}

export async function deleteOfficial(id: string): Promise<void> {
	const res = await fetch(`${BASE}/officials/${id}`, { method: 'DELETE', headers: authHeaders() });
	if (!res.ok) throw new Error('Failed to delete official');
}

export async function listLetterTypes(): Promise<LetterType[]> {
	const res = await fetch(`${BASE}/letter-types`, { headers: authHeaders() });
	if (!res.ok) throw new Error('Failed to load letter types');
	return res.json();
}

export async function createLetterType(body: {
	id: string;
	name: string;
	description?: string;
	approval_chain: ApprovalChainStep[];
	template: string;
}): Promise<LetterType> {
	const res = await fetch(`${BASE}/letter-types`, {
		method: 'POST',
		headers: jsonHeaders(),
		body: JSON.stringify(body)
	});
	if (!res.ok) throw new Error('Failed to create letter type');
	return res.json();
}

export async function updateLetterType(
	id: string,
	body: Partial<{
		name: string;
		description: string;
		approval_chain: ApprovalChainStep[];
		template: string;
	}>
): Promise<LetterType> {
	const res = await fetch(`${BASE}/letter-types/${id}`, {
		method: 'PUT',
		headers: jsonHeaders(),
		body: JSON.stringify(body)
	});
	if (!res.ok) throw new Error('Failed to update letter type');
	return res.json();
}

export async function deleteLetterType(id: string): Promise<void> {
	const res = await fetch(`${BASE}/letter-types/${id}`, {
		method: 'DELETE',
		headers: authHeaders()
	});
	if (!res.ok) throw new Error('Failed to delete letter type');
}
