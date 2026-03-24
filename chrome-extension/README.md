# Vaquill Chrome Extension

AI-powered legal research assistant as a Chrome extension. Calls the Vaquill API directly -- no proxy server required.

---

## Overview

The Vaquill Chrome Extension lets users ask legal research questions from any browser tab. It communicates directly with the Vaquill API (`api.vaquill.ai`), renders structured answers with case citations, court details, excerpts, and PDF links, and maintains conversation context across messages.

---

## Prerequisites

- Google Chrome (or any Chromium-based browser) version 110+
- A Vaquill API key (`vq_key_...`) from [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api)

---

## Setup / Installation

### Step 1: Get your API key

1. Sign in at [app.vaquill.ai](https://app.vaquill.ai)
2. Go to **Settings > API** (or visit [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api))
3. Copy your API key (starts with `vq_key_`)

### Step 2: Load the extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` folder inside this directory
5. The Vaquill extension icon appears in your toolbar

### Step 3: Configure

1. Right-click the extension icon and select **Options** (or click the gear icon inside the popup)
2. Enter your API key (`vq_key_...`)
3. Choose your preferred defaults:
   - **Mode**: `standard` (fast) or `deep` (thorough, multi-hop retrieval)
   - **Jurisdiction**: Select the jurisdiction for search context
4. Click **Save**

### Step 4: Test

1. Click the extension icon to open the chat popup
2. Try a suggested question or type your own (e.g., "What is the doctrine of basic structure?")
3. View the AI response with inline citations
4. Expand source cards to see case name, citation, court, excerpt, relevance score, and PDF link

---

## Configuration

### Extension Config (`extension/js/config.js`)

| Setting | Description |
|---|---|
| `API_URL` | Vaquill API base URL (default: `https://api.vaquill.ai`) |
| `DEFAULT_MODE` | Default RAG mode: `standard` or `deep` |
| `MAX_SOURCES` | Maximum number of sources returned per query |
| `SUGGESTED_QUESTIONS` | Array of starter questions shown on the welcome screen |

### User Settings (stored in `chrome.storage.local`)

| Setting | Description |
|---|---|
| API Key | Your Vaquill API key (`vq_key_...`), entered via Options page |
| Mode | RAG tier: `standard` or `deep` |
| Jurisdiction | Preferred jurisdiction for search context |

---

## API Contract

**Endpoint:** `POST https://api.vaquill.ai/api/v1/ask`

**Request:**
```json
{
  "question": "What is the doctrine of basic structure?",
  "mode": "standard",
  "sources": true,
  "maxSources": 5,
  "chatHistory": [
    { "role": "user", "content": "previous question" },
    { "role": "assistant", "content": "previous answer" }
  ]
}
```

**Response:**
```json
{
  "data": {
    "answer": "The doctrine of basic structure...",
    "sources": [
      {
        "sourceIndex": 1,
        "caseName": "Kesavananda Bharati v. State of Kerala",
        "citation": "(1973) 4 SCC 225",
        "court": "Supreme Court of India",
        "year": 1973,
        "excerpt": "The court held that...",
        "relevanceScore": 0.97,
        "pdfUrl": "https://...",
        "judges": ["S.M. Sikri", "..."],
        "disposition": "ALLOWED"
      }
    ],
    "questionInterpreted": "...",
    "mode": "standard"
  },
  "meta": { ... }
}
```

---

## Project Structure

```
extension/
  manifest.json          Chrome extension manifest (v3)
  popup.html             Main chat popup
  options.html           Settings page (API key, mode, jurisdiction)
  css/popup.css          All styles
  icons/                 Extension icons (provide icon16.png, icon48.png, icon128.png)
  js/
    config.js            API URL, defaults, suggested questions
    session.js           Storage manager (API key, chat history, conversation history)
    background.js        Service worker -- calls POST /api/v1/ask
    popup.js             Chat UI logic, source rendering
    markdown.js          Lightweight markdown-to-HTML renderer
    options.js           Settings page logic
```

---

## Branding Customization

### Extension Name and Description

Edit `extension/manifest.json`:

```json
{
  "name": "Vaquill Legal Assistant",
  "description": "AI-powered legal research assistant with case citations and source documents",
  "version": "1.0.0"
}
```

### Icons

Place your icons in `extension/icons/`:
- `icon16.png` (16x16) -- toolbar
- `icon48.png` (48x48) -- extensions page
- `icon128.png` (128x128) -- Chrome Web Store listing

### Styling

Edit CSS custom properties at the top of `extension/css/popup.css`:

```css
:root {
  --primary-color: #8b5cf6;      /* Brand accent colour */
  --primary-hover: #7c3aed;
  /* ... */
}
```

---

## Host Permissions

The `host_permissions` field in `manifest.json` must match the API domain the extension calls.

**Default (Vaquill production API):**
```json
"host_permissions": [
  "https://api.vaquill.ai/*"
]
```

**Custom API domain:**
```json
"host_permissions": [
  "https://api.yourdomain.com/*"
]
```

**Multiple domains (development + production):**
```json
"host_permissions": [
  "http://localhost:8000/*",
  "https://api.vaquill.ai/*"
]
```

Security best practice: always use specific domains rather than wildcards.

---

## Publishing to Chrome Web Store

### Prerequisites

1. A Google Developer account ($5 one-time fee)
2. Register at: https://chrome.google.com/webstore/devconsole/

### Preparation Checklist

- [ ] Set production API URL in `config.js`
- [ ] Update `manifest.json` with correct name, description, version, and `host_permissions`
- [ ] Add extension icons (16, 48, 128 px)
- [ ] Prepare at least one screenshot (1280x800 px)
- [ ] Prepare a privacy policy URL (required by Google)

### Package the Extension

```bash
cd extension/
zip -r vaquill-extension.zip . -x "*.DS_Store" "*.git*"
```

### Upload to Chrome Web Store

1. Go to the [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole/)
2. Click **New Item**
3. Upload `vaquill-extension.zip`
4. Fill out the listing:
   - **Name**: Vaquill Legal Assistant
   - **Summary**: AI legal research assistant with case citations (132 chars max)
   - **Description**: Full feature description
   - **Category**: Productivity
   - **Language**: English
   - **Screenshots**: At least 1 (1280x800 px)
   - **Privacy Policy**: URL to your privacy policy
   - **Permissions Justification**: Explain why `storage` and `activeTab` are needed
5. Click **Submit for Review**
6. Typical review time: 1-3 business days

---

## Development

The extension uses vanilla JavaScript with no build step. Edit files directly and reload the extension at `chrome://extensions/` (click the refresh icon on the extension card).

---

## Troubleshooting

### "Failed to fetch" errors
- **Cause**: `host_permissions` in `manifest.json` does not match the API URL in `config.js`.
- **Fix**: Ensure both point to the same domain (e.g., `https://api.vaquill.ai`).

### API key not working
- **Cause**: Invalid or expired API key.
- **Fix**: Generate a new key at [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api) and re-enter it in the extension Options page.

### Extension not loading
- **Cause**: Invalid JSON syntax in `manifest.json`.
- **Fix**: Validate JSON syntax. Ensure all required Manifest V3 fields are present.

### No sources in responses
- **Cause**: The query may not match any indexed legal documents, or `maxSources` is set to 0.
- **Fix**: Try a more specific legal query. Verify `maxSources` is greater than 0 in `config.js`.

### Content Security Policy errors
- **Cause**: Modified `content_security_policy` in `manifest.json`.
- **Fix**: Restore the default CSP: `"extension_pages": "script-src 'self'; object-src 'self'"`. Do not add inline scripts or external script sources.

---

## Legal Disclaimer

Vaquill provides legal information, not legal advice. Users should consult a qualified lawyer for advice on their specific circumstances.
