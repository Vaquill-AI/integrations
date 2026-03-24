/**
 * Background Service Worker
 *
 * Calls the Vaquill API directly with the user's API key.
 * No proxy server required.
 */

// Open options page on first install so users can enter their API key
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    chrome.runtime.openOptionsPage();
  }
});

// ---------------------------------------------------------------------------
// Message router
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  const handlers = {
    sendMessage: () => handleSendMessage(request.data),
    healthCheck: () => handleHealthCheck(),
  };

  const handler = handlers[request.action];
  if (handler) {
    handler()
      .then(sendResponse)
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true; // keep channel open for async response
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Read the API key from storage.
 * @returns {Promise<string>}
 */
async function getApiKey() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(['vaquill_api_key'], (result) => {
      const key = result.vaquill_api_key;
      if (!key) {
        reject(new Error('API key not configured. Open extension settings to add your Vaquill API key.'));
        return;
      }
      resolve(key);
    });
  });
}

/**
 * Read user preferences (mode, countryCode) from storage.
 */
async function getPreferences() {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      ['vaquill_mode', 'vaquill_country_code'],
      (result) => {
        resolve({
          mode: result.vaquill_mode || 'standard',
          countryCode: result.vaquill_country_code || null,
        });
      }
    );
  });
}

// ---------------------------------------------------------------------------
// Health Check — validate the API key with a lightweight call
// ---------------------------------------------------------------------------

async function handleHealthCheck() {
  try {
    const apiKey = await getApiKey();

    // We do a simple ask with a trivial question to verify the key works.
    // In the future, if Vaquill adds a /me or /health endpoint, use that instead.
    // For now, just confirm the key is present and non-empty.
    if (apiKey && apiKey.startsWith('vq_key_')) {
      return { success: true, data: { status: 'ok', configured: true } };
    }

    return {
      success: false,
      error: 'API key format is invalid. It should start with vq_key_',
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// ---------------------------------------------------------------------------
// Send Message — POST to Vaquill /ask
// ---------------------------------------------------------------------------

async function handleSendMessage({ message, chatHistory }) {
  try {
    const apiKey = await getApiKey();
    const prefs = await getPreferences();

    const body = {
      question: message,
      mode: prefs.mode,
      sources: true,
      maxSources: 5,
    };

    // Include chatHistory for multi-turn context (if any)
    if (chatHistory && chatHistory.length > 0) {
      body.chatHistory = chatHistory;
    }

    // Include country code if set
    if (prefs.countryCode) {
      body.countryCode = prefs.countryCode;
    }

    const apiUrl = 'https://api.vaquill.ai/api/v1/ask';

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      // Vaquill returns { error: { message, code } } or { detail: "..." }
      const errMsg =
        data?.error?.message ||
        data?.detail ||
        data?.message ||
        `Request failed with status ${response.status}`;
      throw new Error(errMsg);
    }

    // Response shape: { data: { answer, sources, questionInterpreted, mode }, meta: {...} }
    const answer = data.data?.answer || '';
    const sources = data.data?.sources || [];
    const questionInterpreted = data.data?.questionInterpreted || null;

    return {
      success: true,
      data: {
        message: answer,
        sources,
        questionInterpreted,
      },
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}
