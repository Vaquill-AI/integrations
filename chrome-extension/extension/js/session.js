/**
 * Session & Chat History Manager
 *
 * Vaquill uses stateless chat — there is no server-side conversation ID.
 * Instead we maintain chatHistory locally and send it with every request.
 */

const SessionManager = {
  // Storage keys (prefixed with vaquill_)
  API_KEY_KEY: 'vaquill_api_key',
  MODE_KEY: 'vaquill_mode',
  COUNTRY_KEY: 'vaquill_country_code',
  CHAT_HISTORY_KEY: 'vaquill_chat_history',
  CONVERSATION_HISTORY_KEY: 'vaquill_conversation_history',

  // ---------------------------------------------------------------
  // API Key
  // ---------------------------------------------------------------

  /**
   * Get the stored API key.
   * @returns {Promise<string|null>}
   */
  async getApiKey() {
    return new Promise((resolve) => {
      chrome.storage.local.get([this.API_KEY_KEY], (result) => {
        resolve(result[this.API_KEY_KEY] || null);
      });
    });
  },

  /**
   * Save the API key.
   * @param {string} apiKey
   */
  async setApiKey(apiKey) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [this.API_KEY_KEY]: apiKey }, resolve);
    });
  },

  // ---------------------------------------------------------------
  // Mode (standard / deep)
  // ---------------------------------------------------------------

  async getMode() {
    return new Promise((resolve) => {
      chrome.storage.local.get([this.MODE_KEY], (result) => {
        resolve(result[this.MODE_KEY] || CONFIG.DEFAULTS.MODE);
      });
    });
  },

  async setMode(mode) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [this.MODE_KEY]: mode }, resolve);
    });
  },

  // ---------------------------------------------------------------
  // Country Code
  // ---------------------------------------------------------------

  async getCountryCode() {
    return new Promise((resolve) => {
      chrome.storage.local.get([this.COUNTRY_KEY], (result) => {
        resolve(result[this.COUNTRY_KEY] || CONFIG.DEFAULTS.COUNTRY_CODE);
      });
    });
  },

  async setCountryCode(code) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [this.COUNTRY_KEY]: code || null }, resolve);
    });
  },

  // ---------------------------------------------------------------
  // Chat History (sent to API for multi-turn context)
  // ---------------------------------------------------------------

  /**
   * Get the chat history array [{role, content}, ...].
   * @returns {Promise<Array>}
   */
  async getChatHistory() {
    return new Promise((resolve) => {
      chrome.storage.local.get([this.CHAT_HISTORY_KEY], (result) => {
        resolve(result[this.CHAT_HISTORY_KEY] || []);
      });
    });
  },

  /**
   * Append a user message and assistant response to chat history.
   * Trims to the last MAX_CHAT_HISTORY messages.
   * @param {string} userMessage
   * @param {string} assistantMessage
   */
  async addToChatHistory(userMessage, assistantMessage) {
    return new Promise((resolve) => {
      chrome.storage.local.get([this.CHAT_HISTORY_KEY], (result) => {
        const history = result[this.CHAT_HISTORY_KEY] || [];

        history.push(
          { role: 'user', content: userMessage },
          { role: 'assistant', content: assistantMessage }
        );

        // Keep only the last N messages (API limit is 20)
        const trimmed = history.slice(-(CONFIG.UI.MAX_CHAT_HISTORY));

        chrome.storage.local.set({ [this.CHAT_HISTORY_KEY]: trimmed }, resolve);
      });
    });
  },

  /**
   * Clear chat history (start fresh conversation).
   */
  async clearChatHistory() {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [this.CHAT_HISTORY_KEY]: [] }, resolve);
    });
  },

  // ---------------------------------------------------------------
  // Conversation History (for restoring UI messages across popup opens)
  // ---------------------------------------------------------------

  /**
   * Get stored conversation history (UI display pairs).
   * @returns {Promise<Array>}
   */
  async getConversationHistory() {
    return new Promise((resolve) => {
      chrome.storage.local.get([this.CONVERSATION_HISTORY_KEY], (result) => {
        resolve(result[this.CONVERSATION_HISTORY_KEY] || []);
      });
    });
  },

  /**
   * Save a user+AI exchange to conversation history.
   * @param {string} userMessage
   * @param {string} aiMessage
   * @param {Array} sources
   */
  async saveToConversationHistory(userMessage, aiMessage, sources) {
    return new Promise((resolve) => {
      chrome.storage.local.get([this.CONVERSATION_HISTORY_KEY], (result) => {
        const history = result[this.CONVERSATION_HISTORY_KEY] || [];

        history.push({
          userMessage,
          aiMessage,
          sources: sources || [],
          timestamp: Date.now(),
        });

        // Trim to last N pairs
        const trimmed = history.slice(-(CONFIG.UI.MAX_STORED_PAIRS));

        chrome.storage.local.set(
          { [this.CONVERSATION_HISTORY_KEY]: trimmed },
          resolve
        );
      });
    });
  },

  /**
   * Clear conversation history (UI + API chat history).
   */
  async clearConversation() {
    return new Promise((resolve) => {
      chrome.storage.local.set(
        {
          [this.CHAT_HISTORY_KEY]: [],
          [this.CONVERSATION_HISTORY_KEY]: [],
        },
        resolve
      );
    });
  },
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SessionManager;
}
