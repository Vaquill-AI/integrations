/**
 * Configuration for Vaquill Chrome Extension
 *
 * The extension calls the Vaquill API directly — no proxy needed.
 * Users provide their own API key (vq_key_...) via the options page.
 */

const CONFIG = {
  // ===========================================
  // Vaquill API
  // ===========================================
  API_BASE_URL: 'https://api.vaquill.ai/api/v1',

  // ===========================================
  // Branding
  // ===========================================
  EXTENSION_NAME: 'Vaquill Legal Assistant',
  EXTENSION_TAGLINE: 'AI-powered legal research',

  // ===========================================
  // API Endpoints (relative to API_BASE_URL)
  // ===========================================
  ENDPOINTS: {
    ASK: '/ask',
  },

  // ===========================================
  // Defaults
  // ===========================================
  DEFAULTS: {
    MODE: 'standard',        // "standard" or "deep"
    SOURCES: true,
    MAX_SOURCES: 5,
    COUNTRY_CODE: null,      // null = auto, or "IN"
  },

  // ===========================================
  // Feature Flags
  // ===========================================
  FEATURES: {
    AUTO_SCROLL: true,
  },

  // ===========================================
  // UI Settings
  // ===========================================
  UI: {
    MAX_MESSAGE_LENGTH: 1000,   // matches API max_length
    MAX_CHAT_HISTORY: 20,       // matches API max chatHistory
    TYPING_INDICATOR_DELAY: 300,
    ERROR_DISPLAY_DURATION: 5000,
    MAX_STORED_PAIRS: 50,       // max user+ai pairs in local storage
  },

  // ===========================================
  // Suggested Questions (shown on welcome screen)
  // ===========================================
  SUGGESTED_QUESTIONS: [
    'What is the doctrine of basic structure?',
    'Explain the test for negligence under Indian tort law',
    'What are the grounds for anticipatory bail under Section 438 CrPC?',
  ],
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CONFIG;
}
