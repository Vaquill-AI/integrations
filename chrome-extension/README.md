# Vaquill Chrome Extension

AI-powered legal research assistant as a Chrome extension. Calls the Vaquill API directly -- no proxy server required.

## Setup

1. Get an API key from [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api)
2. Open `chrome://extensions/` in Chrome
3. Enable **Developer mode** (top right toggle)
4. Click **Load unpacked** and select the `extension/` folder
5. Click the extension icon, then open **Settings** (right-click > Options)
6. Enter your API key (`vq_key_...`) and save

## Structure

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

## Icons

Place your extension icons in `extension/icons/`:
- `icon16.png` (16x16)
- `icon48.png` (48x48)
- `icon128.png` (128x128)

## Development

The extension uses vanilla JavaScript with no build step. Edit files directly and reload the extension in `chrome://extensions/`.
