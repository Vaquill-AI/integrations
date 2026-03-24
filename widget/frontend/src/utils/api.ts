import type { ChatHistoryItem, ChatResponse } from '../types';

export async function sendChatMessage(
  message: string,
  chatHistory: ChatHistoryItem[],
  mode?: string,
): Promise<ChatResponse> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      chatHistory: chatHistory.length > 0 ? chatHistory : undefined,
      mode,
    }),
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore parse error
    }

    if (response.status === 402) throw new Error('Insufficient credits. Please top up your Vaquill account.');
    if (response.status === 429) throw new Error('Too many requests. Please wait a moment and try again.');
    throw new Error(detail);
  }

  return response.json() as Promise<ChatResponse>;
}
