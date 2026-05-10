"use client";

import { useEffect } from "react";

/**
 * Floating mode landing. Auto-injects `embed.js` so visiting the widget
 * URL itself produces a floating chat bubble — useful as a self-served
 * demo and as the actual product page when customers point their own
 * domain at this deployment with floating mode enabled.
 */
export default function FloatingHost() {
  useEffect(() => {
    if (document.getElementById("vaquill-embed-button")) return;
    const s = document.createElement("script");
    s.src = "/embed.js";
    s.defer = true;
    document.body.appendChild(s);
  }, []);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "48px 24px",
        textAlign: "center",
        background: "#f4f1ec",
        color: "#25211d",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      }}
    >
      <h1
        style={{
          fontFamily: '"Fraunces", Georgia, "Times New Roman", serif',
          fontSize: 32,
          fontWeight: 500,
          letterSpacing: "-0.01em",
          margin: "0 0 12px",
        }}
      >
        Vaquill Legal Assistant
      </h1>
      <p style={{ color: "#655d54", maxWidth: 480, margin: 0, lineHeight: 1.6 }}>
        Click the chat button in the bottom-right corner to start.
      </p>
    </main>
  );
}
