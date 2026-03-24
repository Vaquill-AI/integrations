/**
 * Vaquill Chat Widget — Inline Embed Script
 *
 * Embeds the Vaquill chat widget directly in the page at the location of a
 * placeholder <div>. The div must have the id "vaquill-widget-embed"
 * (or whatever you set via containerId in the config).
 *
 * Usage:
 *   1. Add a container div where you want the widget:
 *        <div id="vaquill-widget-embed"></div>
 *   2. Include this script after that div:
 *        <script src="script-inline-embed.js"></script>
 *
 * Config options (edit the object below or set data-* attributes on the
 * script tag):
 *   data-api-url      — Backend URL      (default: http://localhost:8000)
 *   data-container-id — Target div ID    (default: vaquill-widget-embed)
 *   data-height       — Widget height    (default: 640px)
 *   data-width        — Widget width     (default: 100%)
 */

(function () {
    const scriptTag = document.currentScript;

    const config = {
        apiUrl:      (scriptTag && scriptTag.dataset.apiUrl)      || 'http://localhost:8000',
        containerId: (scriptTag && scriptTag.dataset.containerId) || 'vaquill-widget-embed',
        height:      (scriptTag && scriptTag.dataset.height)      || '640px',
        width:       (scriptTag && scriptTag.dataset.width)       || '100%',
        borderRadius: '12px',
    };

    const container = document.getElementById(config.containerId);
    if (!container) {
        console.error(`[Vaquill] Container #${config.containerId} not found.`);
        return;
    }

    // Wrapper
    const wrapper = document.createElement('div');
    wrapper.style.cssText = `
        position: relative;
        width: ${config.width};
        height: ${config.height};
        border-radius: ${config.borderRadius};
        overflow: hidden;
        box-shadow: 0 4px 8px rgba(0,0,0,0.08), 0 12px 24px rgba(0,0,0,0.06);
        background: white;
        margin: 24px 0;
    `;

    // Loading placeholder
    const loadingDiv = document.createElement('div');
    loadingDiv.style.cssText = `
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #f9fafb;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #9ca3af;
        gap: 8px;
        font-size: 14px;
        z-index: 1;
    `;
    loadingDiv.innerHTML = `
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
             xmlns="http://www.w3.org/2000/svg">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                fill="#1a56db" opacity="0.7"/>
        </svg>
        <span>Loading Vaquill…</span>
    `;

    // Iframe
    const iframe = document.createElement('iframe');
    iframe.src = config.apiUrl;
    iframe.title = 'Vaquill Legal AI';
    iframe.style.cssText = `
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        border: none;
        display: block;
        z-index: 2;
        opacity: 0;
        transition: opacity 0.3s;
    `;

    iframe.onload = () => {
        loadingDiv.style.display = 'none';
        iframe.style.opacity = '1';
    };

    wrapper.appendChild(loadingDiv);
    wrapper.appendChild(iframe);
    container.innerHTML = '';
    container.appendChild(wrapper);

    console.log('[Vaquill] Inline embed widget loaded');
})();
