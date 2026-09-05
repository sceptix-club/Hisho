import { goto } from '$app/navigation';
import { fetchSession } from '$lib/api/sessions';
import type { ChatMessage } from '$lib/types/chat';
import { streamChat } from '$lib/api/sessions';

let sessionId = $state<string | null>(null);
let messages = $state<ChatMessage[]>([]);
let loading = $state(false);
let sending = $state(false);
let error = $state<string | null>(null);

let loadedSession: string | null = null;
let abortController: AbortController | null = null;

function syncUrl(id: string | null) {
	if (id) {
		goto(`/chat?session=${id}`, { replaceState: true, noScroll: true });
	} else {
		goto('/chat', { replaceState: true, noScroll: true });
	}
}

export const session = {
	get sessionId() {
		return sessionId;
	},
	get messages() {
		return messages;
	},
	get loading() {
		return loading;
	},
	get sending() {
		return sending;
	},
	get error() {
		return error;
	},
	get loadedSession() {
		return loadedSession;
	},

	/** Load a session by id (used on resume). Fetches from GET /sessions/{id}. */
	async load(id: string) {
		if (id === loadedSession && messages.length > 0) return;
		loadedSession = id;
		loading = true;
		error = null;
		// Abort any in-flight stream
		abortController?.abort();
		abortController = null;

		try {
			const data = await fetchSession(id);
			messages = data.messages;
			sessionId = data.id;
		} catch (e) {
			messages = [];
			sessionId = null;
			error = e instanceof Error ? e.message : 'Could not load this conversation.';
			// keep loadedSession so retry can re-call load()
		} finally {
			loading = false;
		}
	},

	/** Reset to new-chat state. Optionally without navigating (if already on /chat). */
	reset() {
		abortController?.abort();
		abortController = null;
		messages = [];
		sessionId = null;
		loadedSession = null;
		error = null;
		loading = false;
		sending = false;
		syncUrl(null);
	},

	/**
	 * Handle URL changes: called when the ?session= param changes.
	 * If param is set and differs from loadedSession, load it.
	 * If param is removed, reset.
	 */
	syncFromUrl(param: string | null) {
		if (param && param !== loadedSession) {
			this.load(param);
		} else if (!param && loadedSession !== null) {
			// URL cleared (e.g. after newChat) — reset if we still have a loaded session
			abortController?.abort();
			abortController = null;
			messages = [];
			sessionId = null;
			loadedSession = null;
			error = null;
			loading = false;
			sending = false;
		}
	},

	/** Send a user message and stream the assistant response. */
	async send(query: string) {
		if (!query || sending) return;
		sending = true;
		error = null;

		const userMsg: ChatMessage = {
			role: 'user',
			text: query,
			thought: '',
			tool_calls: [],
			status: 'complete'
		};

		messages.push(userMsg);
		messages.push({
			role: 'assistant',
			text: '',
			thought: '',
			tool_calls: [],
			status: 'streaming',
			docUrl: undefined
		} as ChatMessage);

		const ac = new AbortController();
		abortController = ac;
		let doneSid: string | null = null;
		let hadError = false;

		// Always mutate through the $state proxy (messages[messages.length-1])
		// so Svelte 5's deep reactivity fires. A captured `reply` variable
		// would point at the raw object and bypass the proxy's set trap,
		// which is why streaming appeared frozen until refresh.
		const getReply = () => messages[messages.length - 1];

		try {
			doneSid = await streamChat(
				query,
				sessionId,
				{
					onDelta: (t) => {
						getReply().text += t;
					},
					onMessage: (t) => {
						getReply().text = t;
					},
					onThought: (t) => {
						getReply().thought += t;
					},
					onToolCall: (name, args) => {
						getReply().tool_calls.push({ name, args });
					},
					onToolResult: (name, result) => {
						const r = getReply();
						const tc = r.tool_calls.find((t) => t.name === name && t.result === undefined);
						if (tc) tc.result = result;
						else r.tool_calls.push({ name, result });
						if (name === 'sync_letter_to_google_docs' && result) {
							try {
								const parsed = typeof result === 'string' ? JSON.parse(result as string) : result;
								if (parsed && typeof parsed === 'object' && 'url' in parsed) {
									r.docUrl = (parsed as { url: string }).url;
								}
							} catch {
								// ignore
							}
						}
					},
					onError: (t) => {
						getReply().text = `⚠ ${t}`;
						hadError = true;
					},
					onDone: (sid) => {
						doneSid = sid;
						sessionId = sid;
						loadedSession = sid;
						syncUrl(sid);
					}
				},
				ac.signal
			);

			// If stream ended without explicit done, still sync if we have a sid
			if (doneSid && sessionId !== doneSid) {
				sessionId = doneSid;
				loadedSession = doneSid;
				syncUrl(doneSid);
			}
		} catch (e) {
			if ((e as Error).name === 'AbortError') {
				// cancelled — keep what we have
			} else {
				getReply().text = (e as Error).message?.includes('Failed')
					? `⚠ ${(e as Error).message} Please retry.`
					: `⚠ Connection error. Please retry.`;
				hadError = true;
			}
		} finally {
			abortController = null;
			sending = false;
			const r = getReply();
			r.status = 'complete';
			// Never leave bubble stuck on skeleton — if no text and no error, show fallback
			if (!r.text && !hadError) {
				r.text = '⚠ No response. Please retry.';
			}
		}
	},

	/** Retry the last failed load. */
	retry() {
		if (loadedSession) this.load(loadedSession);
	},

	/** Cancel the in-flight stream (if any). */
	cancel() {
		abortController?.abort();
		abortController = null;
		sending = false;
	}
};
