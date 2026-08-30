export type ChatStream =
	| { type: 'delta'; text: string; who?: string }
	| { type: 'message'; text: string; who?: string }
	| { type: 'thought'; text: string; who?: string }
	| { type: 'tool_call'; name: string; args?: Record<string, unknown>; who?: string }
	| { type: 'tool_result'; name: string; result?: unknown; who?: string }
	| { type: 'transfer'; agent: string; who?: string }
	| { type: 'error'; text: string; who?: string }
	| { type: 'done'; session_id: string; who?: string };

export interface ChatMessage {
	role: 'user' | 'assistant';
	text: string;
	thought: string;
	tool_calls: { name: string; args?: Record<string, unknown>; result?: unknown }[];
	status: 'streaming' | 'complete';
	docUrl?: string;
}
