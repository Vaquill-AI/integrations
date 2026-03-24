/**
 * Vaquill Chat Widget — Intercom-style Floating Chatbot
 *
 * Renders a floating button in the bottom-right corner. Clicking it opens
 * a slide-in chat window that embeds the Vaquill widget via an iframe.
 *
 * Usage — add before </body>:
 *   <script
 *     src="https://your-widget-host/embed/script-floating-chatbot.js"
 *     data-api-url="https://your-widget-host"
 *   ></script>
 *
 * Config options (set via data attributes on the script tag, or edit the
 * config object below for self-hosted deployments):
 *   data-api-url        — Backend URL (default: http://localhost:8000)
 *   data-primary-color  — Brand colour (default: #1a56db)
 *   data-button-size    — Button diameter (default: 60px)
 *   data-chat-width     — Widget width on desktop (default: 400px)
 *   data-chat-height    — Widget height (default: 600px)
 */

(function () {
    // ------------------------------------------------------------------ //
    // Configuration — reads from script data-* attributes with fallbacks  //
    // ------------------------------------------------------------------ //
    const scriptTag = document.currentScript;

    const config = {
        apiUrl:       (scriptTag && scriptTag.dataset.apiUrl)      || 'http://localhost:8000',
        primaryColor: (scriptTag && scriptTag.dataset.primaryColor) || '#1a56db',
        buttonSize:   (scriptTag && scriptTag.dataset.buttonSize)   || '60px',
        chatWidth:    (scriptTag && scriptTag.dataset.chatWidth)    || '400px',
        chatHeight:   (scriptTag && scriptTag.dataset.chatHeight)   || '600px',
        bottomOffset: '24px',
        rightOffset:  '24px',
    };

    // Prevent double-initialisation
    if (document.getElementById('vaquill-widget-chat-button')) return;

    // ------------------------------------------------------------------ //
    // Inject CSS animations                                                //
    // ------------------------------------------------------------------ //
    const styleEl = document.createElement('style');
    styleEl.textContent = `
        @keyframes vaquill-slide-in {
            from { opacity: 0; transform: scale(0.85) translateY(20px); }
            to   { opacity: 1; transform: scale(1)    translateY(0);    }
        }
        @keyframes vaquill-slide-out {
            from { opacity: 1; transform: scale(1)    translateY(0);    }
            to   { opacity: 0; transform: scale(0.85) translateY(20px); }
        }
        @media (max-width: 768px) {
            #vaquill-widget-chat-window {
                width: 100vw !important;
                height: 100vh !important;
                bottom: 0   !important;
                right:  0   !important;
                border-radius: 0 !important;
            }
        }
        .vaquill-avatar-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
        }
    `;
    document.head.appendChild(styleEl);

    // ------------------------------------------------------------------ //
    // Floating trigger button (hidden until widget info is fetched)        //
    // ------------------------------------------------------------------ //
    const button = document.createElement('button');
    button.id = 'vaquill-widget-chat-button';
    button.setAttribute('aria-label', 'Open Vaquill chat');
    button.style.cssText = `
        position: fixed;
        bottom: ${config.bottomOffset};
        right:  ${config.rightOffset};
        width:  ${config.buttonSize};
        height: ${config.buttonSize};
        background: linear-gradient(135deg, ${config.primaryColor}, #2563eb);
        color: white;
        border: none;
        border-radius: 50%;
        font-size: 24px;
        cursor: pointer;
        box-shadow: 0 4px 16px rgba(0,0,0,0.18);
        z-index: 999998;
        transition: transform 0.2s, box-shadow 0.2s;
        display: none;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        padding: 0;
    `;

    button.onmouseover = () => {
        button.style.transform = 'scale(1.08)';
        button.style.boxShadow = '0 6px 20px rgba(0,0,0,0.22)';
    };
    button.onmouseout = () => {
        button.style.transform = 'scale(1)';
        button.style.boxShadow = '0 4px 16px rgba(0,0,0,0.18)';
    };

    // Default icon — scales with buttonSize
    button.innerHTML = `
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
             xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                fill="white" opacity="0.9"/>
        </svg>`;

    // ------------------------------------------------------------------ //
    // Chat window                                                          //
    // ------------------------------------------------------------------ //
    const chatWindow = document.createElement('div');
    chatWindow.id = 'vaquill-widget-chat-window';
    chatWindow.style.cssText = `
        position: fixed;
        bottom: ${config.bottomOffset};
        right:  ${config.rightOffset};
        width:  ${config.chatWidth};
        height: ${config.chatHeight};
        background: white;
        border-radius: 16px;
        box-shadow: 0 16px 48px rgba(0,0,0,0.14), 0 2px 6px rgba(0,0,0,0.08);
        z-index: 999999;
        display: none;
        flex-direction: column;
        overflow: hidden;
        transform-origin: bottom right;
    `;

    // Header
    const header = document.createElement('div');
    header.style.cssText = `
        background: linear-gradient(135deg, ${config.primaryColor}, #2563eb);
        color: white;
        padding: 14px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-weight: 600;
        font-size: 15px;
        flex-shrink: 0;
    `;

    const titleSpan = document.createElement('span');
    titleSpan.textContent = 'Vaquill Legal AI';

    const closeBtn = document.createElement('button');
    closeBtn.setAttribute('aria-label', 'Close chat');
    closeBtn.style.cssText = `
        background: rgba(255,255,255,0.2);
        border: none;
        color: white;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        cursor: pointer;
        font-size: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.15s;
        flex-shrink: 0;
    `;
    closeBtn.textContent = '✕';
    closeBtn.onmouseover = () => { closeBtn.style.background = 'rgba(255,255,255,0.3)'; };
    closeBtn.onmouseout  = () => { closeBtn.style.background = 'rgba(255,255,255,0.2)'; };

    header.appendChild(titleSpan);
    header.appendChild(closeBtn);

    // Iframe container
    const iframeWrap = document.createElement('div');
    iframeWrap.style.cssText = 'flex: 1; position: relative; overflow: hidden;';

    // Loading placeholder
    const loadingDiv = document.createElement('div');
    loadingDiv.style.cssText = `
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #9ca3af;
        font-size: 14px;
        background: #f9fafb;
    `;
    loadingDiv.textContent = 'Loading…';

    // Iframe
    const iframe = document.createElement('iframe');
    iframe.src = config.apiUrl;
    iframe.title = 'Vaquill Legal AI Chat';
    iframe.style.cssText = 'width: 100%; height: 100%; border: none; display: block;';

    iframe.onload = () => { loadingDiv.style.display = 'none'; };

    iframeWrap.appendChild(loadingDiv);
    iframeWrap.appendChild(iframe);

    chatWindow.appendChild(header);
    chatWindow.appendChild(iframeWrap);

    document.body.appendChild(button);
    document.body.appendChild(chatWindow);

    // ------------------------------------------------------------------ //
    // Open / close logic                                                   //
    // ------------------------------------------------------------------ //
    let isOpen = false;

    function openChat() {
        chatWindow.style.display = 'flex';
        chatWindow.style.animation = 'vaquill-slide-in 0.25s cubic-bezier(0.4,0,0.2,1) forwards';
        button.style.display = 'none';
        isOpen = true;
    }

    function closeChat() {
        chatWindow.style.animation = 'vaquill-slide-out 0.25s cubic-bezier(0.4,0,0.2,1) forwards';
        setTimeout(() => {
            chatWindow.style.display = 'none';
            button.style.display = 'flex';
            isOpen = false;
        }, 250);
    }

    button.onclick = openChat;
    closeBtn.onclick = closeChat;

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen) closeChat();
    });

    // ------------------------------------------------------------------ //
    // Fetch widget branding to update title + button appearance           //
    // ------------------------------------------------------------------ //
    async function loadWidgetInfo() {
        try {
            const res = await fetch(`${config.apiUrl}/api/widget/info`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            if (data.title) titleSpan.textContent = data.title;
            if (data.branding && data.branding.primaryColor) {
                const c = data.branding.primaryColor;
                button.style.background = `linear-gradient(135deg, ${c}, #2563eb)`;
                header.style.background  = `linear-gradient(135deg, ${c}, #2563eb)`;
            }
        } catch (err) {
            console.warn('[Vaquill] Could not load widget info:', err);
        } finally {
            button.style.display = 'flex';
        }
    }

    loadWidgetInfo();

    console.log('[Vaquill] Floating chatbot widget loaded');
})();
