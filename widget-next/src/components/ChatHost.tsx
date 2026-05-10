"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { EXAMPLE_QUESTIONS, UI_CONFIG } from "@/config/constants";

// Lazy-load ChatWidget to avoid SSR issues with browser APIs.
const ChatWidget = dynamic(() => import("@/components/ChatWidget"), {
  ssr: false,
});

/**
 * Renders the chat directly. Used when:
 *   - `VAQUILL_EMBED_MODE=inline` (default), OR
 *   - the page is loaded as `?embed=1` (i.e. inside the floating iframe)
 */
export default function ChatHost() {
  const [embedded, setEmbedded] = useState(false);
  useEffect(() => {
    setEmbedded(
      new URLSearchParams(window.location.search).get("embed") === "1"
    );
  }, []);

  return (
    <main
      style={{
        display: "flex",
        alignItems: "stretch",
        justifyContent: "center",
        height: "100%",
      }}
    >
      <ChatWidget
        agentName={UI_CONFIG.agentName}
        exampleQuestions={[...EXAMPLE_QUESTIONS]}
        embedded={embedded}
      />
    </main>
  );
}
