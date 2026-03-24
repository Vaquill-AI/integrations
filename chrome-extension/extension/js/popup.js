/**
 * Popup Script — Main UI Logic for Vaquill Chrome Extension
 */

// DOM Elements
const messagesContainer = document.getElementById('messagesContainer');
const textInput = document.getElementById('textInput');
const sendBtn = document.getElementById('sendBtn');
const refreshBtn = document.getElementById('refreshBtn');
const errorMessage = document.getElementById('errorMessage');
const welcomeScreen = document.getElementById('welcomeScreen');
const loadingScreen = document.getElementById('loadingScreen');
const chatWrapper = document.getElementById('chatWrapper');

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  try {
    setupEventListeners();
    setupWelcomeScreen();
    await loadConversationHistory();
    updateUIState();

    if (loadingScreen) loadingScreen.classList.add('hidden');
    if (chatWrapper) chatWrapper.style.display = 'flex';

    // Check if API key is configured
    const apiKey = await SessionManager.getApiKey();
    if (!apiKey) {
      showError('No API key configured. Click the gear icon or right-click the extension to open Settings.');
    }
  } catch (error) {
    if (loadingScreen) loadingScreen.classList.add('hidden');
    if (chatWrapper) chatWrapper.style.display = 'flex';
    if (welcomeScreen) welcomeScreen.style.display = 'flex';
    if (messagesContainer) messagesContainer.classList.remove('show');
    setupEventListeners();
  }
});

// ---------------------------------------------------------------------------
// Event Listeners
// ---------------------------------------------------------------------------

function setupEventListeners() {
  if (sendBtn) {
    sendBtn.addEventListener('click', () => handleSendMessage());
  }

  if (textInput) {
    textInput.addEventListener('input', () => {
      const hasText = textInput.value.trim().length > 0;
      sendBtn.disabled = !hasText;
    });

    textInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });

    // Focus input when no history
    const hasMessages =
      messagesContainer && messagesContainer.querySelectorAll('.message').length > 0;
    if (!hasMessages) {
      setTimeout(() => textInput.focus(), 100);
    }
  }

  if (refreshBtn) {
    refreshBtn.addEventListener('click', handleNewChat);
  }
}

// ---------------------------------------------------------------------------
// Welcome Screen with Suggested Questions
// ---------------------------------------------------------------------------

function setupWelcomeScreen() {
  const title = document.getElementById('title');
  const agentName = document.getElementById('agentName');

  if (title) title.textContent = CONFIG.EXTENSION_NAME;
  if (agentName) agentName.textContent = CONFIG.EXTENSION_NAME;

  const suggestedQuestionsContainer = document.getElementById('suggestedQuestions');
  if (!suggestedQuestionsContainer) return;

  CONFIG.SUGGESTED_QUESTIONS.forEach((question) => {
    const btn = document.createElement('button');
    btn.className = 'suggestion-btn';
    btn.setAttribute('role', 'listitem');
    btn.setAttribute('type', 'button');
    btn.textContent = question;
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      const original = btn.textContent;
      btn.innerHTML = '<span style="opacity: 0.6;">Sending...</span>';
      await handleSendMessage(original);
      if (btn.isConnected) {
        btn.disabled = false;
        btn.textContent = original;
      }
    });
    suggestedQuestionsContainer.appendChild(btn);
  });
}

// ---------------------------------------------------------------------------
// UI State
// ---------------------------------------------------------------------------

function updateUIState() {
  if (!messagesContainer || !welcomeScreen) return;

  const hasMessages = messagesContainer.querySelectorAll('.message').length > 0;

  if (hasMessages) {
    welcomeScreen.style.display = 'none';
    messagesContainer.style.display = 'block';
    messagesContainer.classList.add('show');
  } else {
    welcomeScreen.style.display = 'flex';
    messagesContainer.style.display = 'none';
    messagesContainer.classList.remove('show');
  }
}

// ---------------------------------------------------------------------------
// Send Message
// ---------------------------------------------------------------------------

async function handleSendMessage(messageText = null) {
  const message = messageText ? messageText.trim() : textInput.value.trim();
  if (!message) return;

  // Enforce length limit
  if (message.length > CONFIG.UI.MAX_MESSAGE_LENGTH) {
    showError(`Message too long. Maximum ${CONFIG.UI.MAX_MESSAGE_LENGTH} characters.`);
    return;
  }

  // Clear input
  if (!messageText) {
    textInput.value = '';
    sendBtn.disabled = true;
  }

  // Switch to messages view
  welcomeScreen.style.display = 'none';
  messagesContainer.classList.add('show');
  messagesContainer.style.display = 'block';

  addMessage(message, 'user');
  setInputEnabled(false);

  const typingIndicator = showTypingIndicator();

  try {
    // Get chat history for multi-turn context
    const chatHistory = await SessionManager.getChatHistory();

    const response = await chrome.runtime.sendMessage({
      action: 'sendMessage',
      data: { message, chatHistory },
    });

    typingIndicator.remove();

    if (!response.success) {
      throw new Error(response.error || 'Failed to get response');
    }

    const aiMessage = response.data.message;
    const sources = response.data.sources || [];

    addMessage(aiMessage, 'ai', sources);

    // Persist chat history (for API multi-turn) and conversation history (for UI)
    await SessionManager.addToChatHistory(message, aiMessage);
    await SessionManager.saveToConversationHistory(message, aiMessage, sources);
  } catch (error) {
    typingIndicator.remove();
    showError(error.message || 'Failed to send message. Please try again.');
  } finally {
    setInputEnabled(true);
    textInput.focus();
  }
}

// ---------------------------------------------------------------------------
// Add Message to UI
// ---------------------------------------------------------------------------

function addMessage(text, type, sources = []) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}`;
  messageDiv.dataset.timestamp = Date.now();

  // Avatar
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';

  if (type === 'user') {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
    </svg>`;
  } else {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
    </svg>`;
  }

  // Content
  const content = document.createElement('div');
  content.className = 'message-content';

  if (type === 'ai' && typeof renderMarkdown === 'function') {
    content.innerHTML = renderMarkdown(text);
  } else {
    content.textContent = text;
  }

  // Copy button for AI messages
  if (type === 'ai') {
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'message-actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'action-btn copy-btn';
    copyBtn.title = 'Copy message';
    copyBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
    </svg>`;
    copyBtn.addEventListener('click', () => handleCopyMessage(text, copyBtn));
    actionsDiv.appendChild(copyBtn);

    content.appendChild(actionsDiv);
  }

  // Sources (structured objects from Vaquill API)
  if (type === 'ai' && sources && sources.length > 0) {
    const citationsWrapper = buildSourcesSection(sources);
    if (citationsWrapper) {
      content.appendChild(citationsWrapper);
    }
  }

  // Timestamp
  const timestamp = document.createElement('span');
  timestamp.className = 'message-timestamp';
  timestamp.textContent = 'Just now';
  content.appendChild(timestamp);

  messageDiv.appendChild(avatar);
  messageDiv.appendChild(content);
  messagesContainer.appendChild(messageDiv);

  // Auto-scroll
  if (CONFIG.FEATURES.AUTO_SCROLL) {
    requestAnimationFrame(() => {
      messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: 'smooth',
      });
    });
  }

  updateTimestamps();
}

// ---------------------------------------------------------------------------
// Sources Section (collapsible)
// ---------------------------------------------------------------------------

function buildSourcesSection(sources) {
  if (!sources || sources.length === 0) return null;

  const wrapper = document.createElement('div');
  wrapper.className = 'citations-wrapper';

  // Header
  const header = document.createElement('div');
  header.className = 'citations-header';
  header.innerHTML = `
    <span class="citations-title">Sources (${sources.length})</span>
    <svg class="citations-toggle-icon" viewBox="0 0 24 24" fill="currentColor">
      <path d="M7 10l5 5 5-5z"/>
    </svg>
  `;

  // Content
  const contentEl = document.createElement('div');
  contentEl.className = 'citations-content';

  sources.forEach((source, index) => {
    const item = document.createElement('div');
    item.className = 'citation-item';

    const sourceIndex = source.sourceIndex || index + 1;
    const caseName = source.caseName || 'Unknown Case';
    const citation = source.citation || '';
    const court = source.court || '';
    const year = source.year || '';
    const excerpt = source.excerpt || '';
    const pdfUrl = source.pdfUrl || null;
    const relevanceScore = source.relevanceScore;
    const judges = source.judges;
    const disposition = source.disposition || '';

    // Build subtitle parts
    const subtitleParts = [];
    if (court) subtitleParts.push(court);
    if (year) subtitleParts.push(year);
    if (disposition) subtitleParts.push(disposition);
    const subtitle = subtitleParts.join(' | ');

    // Build judges line
    const judgesLine =
      judges && judges.length > 0
        ? `<div class="citation-judges">Bench: ${escapeHtml(judges.join(', '))}</div>`
        : '';

    // Relevance badge
    const scoreBadge =
      relevanceScore != null
        ? `<span class="citation-score">${Math.round(relevanceScore * 100)}%</span>`
        : '';

    // PDF link
    const pdfLink = pdfUrl
      ? `<a href="${escapeHtml(pdfUrl)}" target="_blank" rel="noopener" class="citation-pdf-link" title="View PDF">PDF</a>`
      : '';

    item.innerHTML = `
      <div class="citation-number">${sourceIndex}</div>
      <div class="citation-text">
        <div class="citation-case-header">
          <span class="citation-link">${escapeHtml(caseName)}</span>
          ${scoreBadge}
          ${pdfLink}
        </div>
        ${citation ? `<div class="citation-ref">${escapeHtml(citation)}</div>` : ''}
        ${subtitle ? `<div class="citation-subtitle">${escapeHtml(subtitle)}</div>` : ''}
        ${judgesLine}
        ${excerpt ? `<p class="citation-description">${escapeHtml(excerpt)}</p>` : ''}
      </div>
    `;

    contentEl.appendChild(item);
  });

  // Toggle
  header.addEventListener('click', () => {
    wrapper.classList.toggle('expanded');
  });

  wrapper.appendChild(header);
  wrapper.appendChild(contentEl);
  return wrapper;
}

// ---------------------------------------------------------------------------
// Typing Indicator
// ---------------------------------------------------------------------------

function showTypingIndicator() {
  const indicator = document.createElement('div');
  indicator.className = 'message ai';
  indicator.id = 'typingIndicator';

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
  </svg>`;

  const content = document.createElement('div');
  content.className = 'message-content';

  const typingDiv = document.createElement('div');
  typingDiv.className = 'typing-indicator';
  typingDiv.innerHTML =
    '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

  content.appendChild(typingDiv);
  indicator.appendChild(avatar);
  indicator.appendChild(content);

  messagesContainer.appendChild(indicator);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  return indicator;
}

// ---------------------------------------------------------------------------
// Error / Input helpers
// ---------------------------------------------------------------------------

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.classList.add('show');

  setTimeout(() => {
    errorMessage.classList.remove('show');
  }, CONFIG.UI.ERROR_DISPLAY_DURATION);
}

function setInputEnabled(enabled) {
  textInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
}

// ---------------------------------------------------------------------------
// New Chat
// ---------------------------------------------------------------------------

async function handleNewChat() {
  await SessionManager.clearConversation();
  messagesContainer.innerHTML = '';
  updateUIState();
}

// ---------------------------------------------------------------------------
// Load Conversation History (UI restore)
// ---------------------------------------------------------------------------

async function loadConversationHistory() {
  try {
    const history = await SessionManager.getConversationHistory();

    if (history.length > 0) {
      if (welcomeScreen) welcomeScreen.style.display = 'none';
      if (messagesContainer) messagesContainer.classList.add('show');

      history.forEach(({ userMessage, aiMessage, sources }) => {
        if (userMessage) addMessage(userMessage, 'user');
        if (aiMessage) addMessage(aiMessage, 'ai', sources || []);
      });
    }
  } catch (error) {
    // Silently fail — do not block init
  }
}

// ---------------------------------------------------------------------------
// Copy
// ---------------------------------------------------------------------------

async function handleCopyMessage(text, button) {
  try {
    const plainText = text.replace(/[*_~`#]/g, '');
    await navigator.clipboard.writeText(plainText);

    const originalHTML = button.innerHTML;
    button.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
    </svg>`;
    button.classList.add('success');

    setTimeout(() => {
      button.innerHTML = originalHTML;
      button.classList.remove('success');
    }, 2000);
  } catch (error) {
    showError('Failed to copy message');
  }
}

// ---------------------------------------------------------------------------
// Timestamp Updates
// ---------------------------------------------------------------------------

function updateTimestamps() {
  const messages = document.querySelectorAll('.message');

  messages.forEach((msg) => {
    const ts = msg.dataset.timestamp;
    if (!ts) return;

    const span = msg.querySelector('.message-timestamp');
    if (!span) return;

    const diff = Date.now() - parseInt(ts);
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    let timeText = 'Just now';
    if (days > 0) timeText = `${days}d ago`;
    else if (hours > 0) timeText = `${hours}h ago`;
    else if (minutes > 0) timeText = `${minutes}m ago`;
    else if (seconds > 5) timeText = `${seconds}s ago`;

    span.textContent = timeText;
  });
}

setInterval(updateTimestamps, 10000);

// ---------------------------------------------------------------------------
// Utility: escape HTML to prevent XSS
// ---------------------------------------------------------------------------

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
