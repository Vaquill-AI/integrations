/**
 * Options Page Script — Vaquill Chrome Extension Settings
 */

// DOM Elements
const apiKeyInput = document.getElementById('apiKeyInput');
const modeSelect = document.getElementById('modeSelect');
const countrySelect = document.getElementById('countrySelect');
const saveBtn = document.getElementById('saveBtn');
const testBtn = document.getElementById('testConnectionBtn');
const resetBtn = document.getElementById('resetSessionBtn');
const connectionStatus = document.getElementById('connectionStatus');
const statusBox = document.getElementById('statusBox');
const statusTitle = document.getElementById('statusTitle');
const statusText = document.getElementById('statusText');

// ---------------------------------------------------------------------------
// Initialize
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  // Load saved values
  const apiKey = await SessionManager.getApiKey();
  const mode = await SessionManager.getMode();
  const countryCode = await SessionManager.getCountryCode();

  if (apiKey) apiKeyInput.value = apiKey;
  if (mode) modeSelect.value = mode;
  if (countryCode) countrySelect.value = countryCode;

  // Event listeners
  saveBtn.addEventListener('click', handleSave);
  testBtn.addEventListener('click', handleTestConnection);
  resetBtn.addEventListener('click', handleReset);
});

// ---------------------------------------------------------------------------
// Save Settings
// ---------------------------------------------------------------------------

async function handleSave() {
  const apiKey = apiKeyInput.value.trim();

  if (!apiKey) {
    showStatus('error', 'Validation Error', 'API key is required.');
    return;
  }

  if (!apiKey.startsWith('vq_key_')) {
    showStatus(
      'error',
      'Invalid API Key',
      'Vaquill API keys start with vq_key_. Check your key and try again.'
    );
    return;
  }

  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    await SessionManager.setApiKey(apiKey);
    await SessionManager.setMode(modeSelect.value);
    await SessionManager.setCountryCode(countrySelect.value || null);

    showStatus('success', 'Settings Saved', 'Your settings have been saved successfully.');
  } catch (error) {
    showStatus('error', 'Save Failed', `Could not save settings: ${error.message}`);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save Settings';
  }
}

// ---------------------------------------------------------------------------
// Test Connection
// ---------------------------------------------------------------------------

async function handleTestConnection() {
  testBtn.disabled = true;
  testBtn.textContent = 'Testing...';
  connectionStatus.textContent = 'Testing...';
  connectionStatus.className = 'status-badge';

  try {
    const response = await chrome.runtime.sendMessage({
      action: 'healthCheck',
    });

    if (response.success) {
      connectionStatus.textContent = 'Valid';
      connectionStatus.className = 'status-badge connected';
      showStatus('success', 'API Key Valid', 'Your API key is configured and ready to use.');
    } else {
      throw new Error(response.error || 'Validation failed');
    }
  } catch (error) {
    connectionStatus.textContent = 'Invalid';
    connectionStatus.className = 'status-badge disconnected';
    showStatus('error', 'Validation Failed', error.message);
  } finally {
    testBtn.disabled = false;
    testBtn.textContent = 'Test API Key';
  }
}

// ---------------------------------------------------------------------------
// Reset (clear history + chat)
// ---------------------------------------------------------------------------

async function handleReset() {
  if (
    !confirm(
      'Reset your session? This will:\n\n' +
        '- Clear conversation history\n' +
        '- Clear chat context\n\n' +
        'Your API key and settings will be kept.\n\nContinue?'
    )
  ) {
    return;
  }

  resetBtn.disabled = true;
  resetBtn.textContent = 'Resetting...';

  try {
    await SessionManager.clearConversation();
    showStatus('success', 'Session Reset', 'Conversation history has been cleared.');
  } catch (error) {
    showStatus('error', 'Reset Failed', `Could not reset session: ${error.message}`);
  } finally {
    resetBtn.disabled = false;
    resetBtn.textContent = 'Reset Session';
  }
}

// ---------------------------------------------------------------------------
// Status display
// ---------------------------------------------------------------------------

function showStatus(type, title, text) {
  statusBox.className = `info-box ${type}`;
  statusTitle.textContent = title;
  statusText.textContent = text;
  statusBox.style.display = 'block';

  if (type === 'success') {
    setTimeout(() => {
      statusBox.style.display = 'none';
    }, 5000);
  }
}
