/**
 * Vaquill Widget — Floating Chatbot Embed
 *
 * Drop one tag on any site to get an Intercom-style floating chat:
 *
 *   <script
 *     src="https://your-widget.vercel.app/embed.js"
 *     data-host="https://your-widget.vercel.app"
 *     defer
 *   ></script>
 *
 * Optional data-* attributes:
 *   data-host           — Widget origin (default: script's origin)
 *   data-title          — Header label (default: "Vaquill Legal Assistant")
 *   data-primary-color  — Brand colour (default: #6e3730 Vaquill maroon)
 *   data-button-size    — Button diameter (default: 56px)
 *   data-chat-width     — Window width on desktop (default: 480px)
 *   data-chat-height    — Window height (default: 680px)
 *   data-position       — bottom-right | bottom-left (default: bottom-right)
 *   data-teaser         — Welcome bubble text shown next to the launcher
 *                         until the user opens or dismisses it. Pass an
 *                         empty string to disable.
 *   data-teaser-delay   — Milliseconds before the teaser fades in
 *                         (default: 2000).
 */

(function () {
  if (document.getElementById("vaquill-embed-button")) return;

  // ------------------------------------------------------------------ //
  // Config — read script tag attributes with fallbacks                   //
  // ------------------------------------------------------------------ //
  const script = document.currentScript;
  const scriptOrigin = script ? new URL(script.src).origin : window.location.origin;

  const ds = script ? script.dataset : {};
  // Allow `data-teaser=""` to explicitly disable; only fall back to the
  // default when the attribute is absent.
  const teaserText = ds.teaser !== undefined
    ? ds.teaser
    : "Have a US legal question? Ask me — answers are grounded in real case law and statutes.";
  const teaserDelay = Number(ds.teaserDelay);
  const config = {
    host: ds.host || scriptOrigin,
    title: ds.title || "Vaquill Legal Assistant",
    primaryColor: ds.primaryColor || "#6e3730",
    buttonSize: ds.buttonSize || "56px",
    chatWidth: ds.chatWidth || "480px",
    chatHeight: ds.chatHeight || "680px",
    position: (ds.position === "bottom-left" ? "bottom-left" : "bottom-right"),
    teaser: teaserText,
    teaserDelayMs: Number.isFinite(teaserDelay) && teaserDelay >= 0 ? teaserDelay : 2000,
  };

  const isLeft = config.position === "bottom-left";
  const sideOffset = "24px";
  const bottomOffset = "24px";

  // ------------------------------------------------------------------ //
  // Fonts (Fraunces for the header to match the widget brand)            //
  // ------------------------------------------------------------------ //
  if (!document.querySelector('link[data-vq-fonts]')) {
    const preconnect1 = document.createElement("link");
    preconnect1.rel = "preconnect";
    preconnect1.href = "https://fonts.googleapis.com";
    preconnect1.setAttribute("data-vq-fonts", "1");
    document.head.appendChild(preconnect1);

    const preconnect2 = document.createElement("link");
    preconnect2.rel = "preconnect";
    preconnect2.href = "https://fonts.gstatic.com";
    preconnect2.crossOrigin = "anonymous";
    preconnect2.setAttribute("data-vq-fonts", "1");
    document.head.appendChild(preconnect2);

    const fontLink = document.createElement("link");
    fontLink.rel = "stylesheet";
    fontLink.href =
      "https://fonts.googleapis.com/css2?family=Fraunces:wght@400;500;600&display=swap";
    fontLink.setAttribute("data-vq-fonts", "1");
    document.head.appendChild(fontLink);
  }

  // ------------------------------------------------------------------ //
  // CSS keyframes + mobile fullscreen                                   //
  // ------------------------------------------------------------------ //
  const style = document.createElement("style");
  style.textContent = `
    @keyframes vq-embed-in {
      from { opacity: 0; transform: scale(0.92) translateY(12px); }
      to   { opacity: 1; transform: scale(1)    translateY(0);    }
    }
    @keyframes vq-embed-out {
      from { opacity: 1; transform: scale(1)    translateY(0);    }
      to   { opacity: 0; transform: scale(0.92) translateY(12px); }
    }
    @keyframes vq-teaser-in {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @media (max-width: 640px) {
      #vaquill-embed-window {
        width: 100vw !important;
        height: 100dvh !important;
        height: 100vh !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        border-radius: 0 !important;
      }
      #vaquill-embed-teaser { display: none !important; }
    }
  `;
  document.head.appendChild(style);

  // ------------------------------------------------------------------ //
  // Floating launcher button                                            //
  // ------------------------------------------------------------------ //
  const button = document.createElement("button");
  button.id = "vaquill-embed-button";
  button.setAttribute("aria-label", "Open " + config.title);
  button.style.cssText = `
    position: fixed;
    bottom: ${bottomOffset};
    ${isLeft ? "left" : "right"}: ${sideOffset};
    width: ${config.buttonSize};
    height: ${config.buttonSize};
    background: ${config.primaryColor};
    color: #ffffff;
    border: none;
    border-radius: 9999px;
    cursor: pointer;
    box-shadow: 0 6px 18px rgba(37, 33, 29, 0.18), 0 1px 2px rgba(37, 33, 29, 0.10);
    z-index: 2147483646;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    transition: transform 150ms ease, box-shadow 150ms ease, background-color 150ms ease;
  `;
  button.onmouseover = () => {
    button.style.transform = "scale(1.06)";
    button.style.boxShadow = "0 10px 24px rgba(37, 33, 29, 0.22)";
  };
  button.onmouseout = () => {
    button.style.transform = "scale(1)";
    button.style.boxShadow = "0 6px 18px rgba(37, 33, 29, 0.18), 0 1px 2px rgba(37, 33, 29, 0.10)";
  };

  // Chat-bubble icon (24px), white stroke
  button.innerHTML = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
         stroke-linejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>`;

  // ------------------------------------------------------------------ //
  // Slide-in chat window                                                //
  // ------------------------------------------------------------------ //
  const win = document.createElement("div");
  win.id = "vaquill-embed-window";
  win.style.cssText = `
    position: fixed;
    bottom: ${bottomOffset};
    ${isLeft ? "left" : "right"}: ${sideOffset};
    width: ${config.chatWidth};
    height: ${config.chatHeight};
    background: #ffffff;
    border-radius: 16px;
    box-shadow: 0 24px 56px rgba(37, 33, 29, 0.18), 0 2px 8px rgba(37, 33, 29, 0.08);
    z-index: 2147483647;
    display: none;
    flex-direction: column;
    overflow: hidden;
    transform-origin: ${isLeft ? "bottom left" : "bottom right"};
  `;

  // Slim header above the iframe (the widget's own header still shows
  // inside, but this gives users a close button without depending on
  // postMessage from the iframe).
  const header = document.createElement("div");
  header.style.cssText = `
    background: ${config.primaryColor};
    color: #ffffff;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: "Fraunces", Georgia, "Times New Roman", serif;
    font-weight: 500;
    font-size: 17px;
    letter-spacing: -0.01em;
    flex-shrink: 0;
  `;

  const titleEl = document.createElement("span");
  titleEl.textContent = config.title;

  // Right cluster: [New chat] [Close]
  const headerActions = document.createElement("div");
  headerActions.style.cssText =
    "display: flex; align-items: center; gap: 8px; flex-shrink: 0;";

  const ghostBtnCss = `
    background: rgba(255, 255, 255, 0.16);
    border: none;
    color: #ffffff;
    width: 28px;
    height: 28px;
    border-radius: 9999px;
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 150ms ease;
    padding: 0;
  `;
  const hoverIn = (b) => {
    b.style.background = "rgba(255, 255, 255, 0.28)";
  };
  const hoverOut = (b) => {
    b.style.background = "rgba(255, 255, 255, 0.16)";
  };

  // New-chat button — posts a message to the iframe so it clears its
  // own state + localStorage. Same-origin only.
  const newBtn = document.createElement("button");
  newBtn.setAttribute("aria-label", "Start a new chat");
  newBtn.title = "New chat";
  newBtn.style.cssText = ghostBtnCss;
  newBtn.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round"
         stroke-linejoin="round" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>`;
  newBtn.onmouseover = () => hoverIn(newBtn);
  newBtn.onmouseout = () => hoverOut(newBtn);
  newBtn.onclick = () => {
    if (iframe.contentWindow) {
      iframe.contentWindow.postMessage({ type: "vaquill:new-chat" }, config.host);
    }
  };

  const closeBtn = document.createElement("button");
  closeBtn.setAttribute("aria-label", "Close chat");
  closeBtn.title = "Close";
  closeBtn.style.cssText = ghostBtnCss;
  closeBtn.textContent = "✕";
  closeBtn.onmouseover = () => hoverIn(closeBtn);
  closeBtn.onmouseout = () => hoverOut(closeBtn);

  headerActions.appendChild(newBtn);
  headerActions.appendChild(closeBtn);

  header.appendChild(titleEl);
  header.appendChild(headerActions);

  // Iframe shell
  const frameWrap = document.createElement("div");
  frameWrap.style.cssText = "flex: 1; position: relative; overflow: hidden; background: #f4f1ec;";

  const loading = document.createElement("div");
  loading.style.cssText = `
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #655d54;
    font-size: 14px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f1ec;
  `;
  loading.textContent = "Loading…";

  const iframe = document.createElement("iframe");
  iframe.src = config.host + "/?embed=1";
  iframe.title = config.title;
  iframe.style.cssText = "width: 100%; height: 100%; border: none; display: block; background: #ffffff;";
  iframe.allow = "clipboard-write";
  iframe.onload = () => {
    loading.style.display = "none";
  };

  frameWrap.appendChild(loading);
  frameWrap.appendChild(iframe);

  win.appendChild(header);
  win.appendChild(frameWrap);

  document.body.appendChild(button);
  document.body.appendChild(win);

  // ------------------------------------------------------------------ //
  // Welcome teaser bubble — sits above the launcher with a friendly    //
  // greeting until the user opens chat or dismisses it. Hidden once     //
  // dismissed (sessionStorage), so it doesn't nag on every page.        //
  // ------------------------------------------------------------------ //
  const TEASER_DISMISSED_KEY = "vq-teaser-dismissed";
  let teaser = null;
  let teaserCloseBtn = null;

  function teaserDismissed() {
    try {
      return sessionStorage.getItem(TEASER_DISMISSED_KEY) === "1";
    } catch {
      return false;
    }
  }

  function rememberTeaserDismissed() {
    try {
      sessionStorage.setItem(TEASER_DISMISSED_KEY, "1");
    } catch {
      // sessionStorage blocked — fine, teaser will reappear next page
      // load. We'd rather show it than fail silently.
    }
  }

  if (config.teaser && !teaserDismissed()) {
    teaser = document.createElement("div");
    teaser.id = "vaquill-embed-teaser";
    teaser.setAttribute("role", "status");
    // Sit above the launcher button. Width capped so long sentences
    // wrap into ~2-3 lines instead of stretching across the page.
    teaser.style.cssText = `
      position: fixed;
      bottom: calc(${bottomOffset} + ${config.buttonSize} + 14px);
      ${isLeft ? "left" : "right"}: ${sideOffset};
      max-width: 280px;
      padding: 10px 32px 10px 14px;
      background: #ffffff;
      color: #25211d;
      border: 1px solid rgba(37, 33, 29, 0.10);
      border-radius: 14px;
      box-shadow: 0 8px 24px rgba(37, 33, 29, 0.12), 0 1px 2px rgba(37, 33, 29, 0.06);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        "Helvetica Neue", Arial, sans-serif;
      font-size: 13px;
      line-height: 1.5;
      z-index: 2147483645;
      cursor: pointer;
      opacity: 0;
      animation: vq-teaser-in 260ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
      animation-delay: ${config.teaserDelayMs}ms;
      animation-fill-mode: forwards;
    `;
    teaser.textContent = config.teaser;

    teaserCloseBtn = document.createElement("button");
    teaserCloseBtn.setAttribute("aria-label", "Dismiss");
    teaserCloseBtn.title = "Dismiss";
    teaserCloseBtn.style.cssText = `
      position: absolute;
      top: 4px;
      ${isLeft ? "right" : "right"}: 4px;
      width: 22px;
      height: 22px;
      padding: 0;
      border: none;
      background: transparent;
      color: rgba(37, 33, 29, 0.55);
      cursor: pointer;
      font-size: 14px;
      line-height: 1;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background-color 120ms ease, color 120ms ease;
    `;
    teaserCloseBtn.textContent = "✕";
    teaserCloseBtn.onmouseover = () => {
      teaserCloseBtn.style.background = "rgba(37, 33, 29, 0.08)";
      teaserCloseBtn.style.color = "#25211d";
    };
    teaserCloseBtn.onmouseout = () => {
      teaserCloseBtn.style.background = "transparent";
      teaserCloseBtn.style.color = "rgba(37, 33, 29, 0.55)";
    };
    teaserCloseBtn.onclick = (e) => {
      e.stopPropagation();
      hideTeaser();
      rememberTeaserDismissed();
    };

    teaser.appendChild(teaserCloseBtn);
    document.body.appendChild(teaser);
  }

  function hideTeaser() {
    if (!teaser) return;
    teaser.style.display = "none";
  }

  // ------------------------------------------------------------------ //
  // Open / close                                                        //
  // ------------------------------------------------------------------ //
  let isOpen = false;

  function open() {
    win.style.display = "flex";
    win.style.animation = "vq-embed-in 220ms cubic-bezier(0.4, 0, 0.2, 1) forwards";
    button.style.display = "none";
    hideTeaser();
    rememberTeaserDismissed();
    isOpen = true;
  }

  function close() {
    win.style.animation = "vq-embed-out 200ms cubic-bezier(0.4, 0, 0.2, 1) forwards";
    setTimeout(() => {
      win.style.display = "none";
      button.style.display = "flex";
      isOpen = false;
    }, 200);
  }

  // Clicking the teaser itself opens the chat — friendlier than
  // forcing users to find the small launcher button.
  if (teaser) {
    teaser.addEventListener("click", (e) => {
      if (e.target === teaserCloseBtn) return;
      open();
    });
  }

  button.onclick = open;
  closeBtn.onclick = close;

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) close();
  });
})();
