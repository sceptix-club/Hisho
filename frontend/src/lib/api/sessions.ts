import { api } from '$lib/api';
import type { ChatMessage, ChatStream, SessionSummary } from '$lib/types/chat';

export async function listSessions(): Promise<SessionSummary[]> {
	const res = await api('/sessions');
	if (!res.ok) throw new Error(`Failed to list sessions (${res.status}).`);
	return res.json();
}

export async function fetchSession(id: string): Promise<{ id: string; messages: ChatMessage[] }> {
	const res = await api(`/sessions/${id}`);
	if (!res.ok) throw new Error(`Failed to load conversation (${res.status}).`);
	const data = await res.json();
	return {
		id: data.id ?? id,
		messages: Array.isArray(data.messages) ? data.messages : []
	};
}

export async function deleteSession(id: string): Promise<void> {
	const res = await api(`/sessions/${id}`, { method: 'DELETE' });
	if (!res.ok) throw new Error(`Failed to delete session (${res.status}).`);
}

export type StreamCallbacks = {
	onDelta?: (text: string) => void;
	onMessage?: (text: string) => void;
	onThought?: (text: string) => void;
	onToolCall?: (name: string, args?: Record<string, unknown>) => void;
	onToolResult?: (name: string, result?: unknown) => void;
	onTransfer?: (agent: string) => void;
	onError?: (text: string) => void;
	onDone?: (sessionId: string) => void;
};

/**
 * Stream a chat message. Wraps POST /chat/stream and parses SSE events,
 * invoking the appropriate callback for each event type.
 * Returns the session_id from the done event.
 * Aborting is supported via the provided AbortSignal.
 */
export async function streamChat(
	query: string,
	sessionId: string | null,
	callbacks: StreamCallbacks,
	signal?: AbortSignal
): Promise<string | null> {
	const res = await api('/chat/stream', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ query, session_id: sessionId }),
		signal
	});

	if (!res.ok || !res.body) {
		throw new Error(`Request failed (${res.status}).`);
	}

	const reader = res.body.getReader();
	const dec = new TextDecoder();
	let buf = '';
	let doneSid: string | null = null;
	let doneReceived = false;

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;
			buf += dec.decode(value, { stream: true });
			const parts = buf.split('\n\n');
			buf = parts.pop() || '';
			for (const part of parts) {
				if (!part) continue;
				for (const line of part.split('\n')) {
					if (!line.startsWith('data: ')) continue;
					try {
						const data = JSON.parse(line.slice(6)) as ChatStream;
						switch (data.type) {
							case 'delta':
								callbacks.onDelta?.(data.text);
								break;
							case 'message': {
								let text = data.text;
								try {
									text = JSON.parse(data.text).final_status;
								} catch {
									// use raw text
								}
								callbacks.onMessage?.(text);
								break;
							}
							case 'thought':
								callbacks.onThought?.(data.text);
								break;
							case 'tool_call':
								callbacks.onToolCall?.(data.name, data.args);
								break;
							case 'tool_result':
								callbacks.onToolResult?.(data.name, data.result);
								break;
							case 'transfer':
								callbacks.onTransfer?.(data.agent);
								break;
							case 'error':
								callbacks.onError?.(data.text);
								break;
							case 'done':
								doneSid = data.session_id;
								doneReceived = true;
								callbacks.onDone?.(data.session_id);
								break;
						}
					} catch {
						// ignore malformed SSE chunk
					}
				}
			}
		}
	} catch (e) {
		if ((e as Error).name === 'AbortError') throw e;
		if (!doneReceived) {
			callbacks.onError?.((e as Error).message || 'Connection interrupted.');
		}
	}

	return doneSid;
}
