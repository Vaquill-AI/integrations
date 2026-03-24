"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useCapabilities } from "@/hooks/useCapabilities";
import { UI_CONFIG, VAQUILL_CONFIG } from "@/config/constants";
import type { VaquillMode } from "@/lib/vaquill";

// Lazy-load ChatWidget to avoid SSR issues with browser APIs
const ChatWidget = dynamic(() => import("@/components/ChatWidget"), {
  ssr: false,
});

// Default example questions — can be overridden via env or embed params
const DEFAULT_QUESTIONS = [
  "What is the doctrine of basic structure in the Indian Constitution?",
  "Explain the concept of promissory estoppel with case law.",
  "What are the grounds for divorce under Hindu Marriage Act?",
];

export default function Home() {
  const { capabilities, loading, error } = useCapabilities();

  // Apply theme from data attribute on <html> to keep SSR + client in sync
  useEffect(() => {
    const theme = document.documentElement.dataset.theme ?? "dark";
    document.documentElement.dataset.theme = theme;
  }, []);

  if (loading) {
    return (
      <div className="flex-center-screen">
        <div className="spinner" role="status" aria-label="Loading" />
      </div>
    );
  }

  if (error && !capabilities) {
    return (
      <div className="flex-center-screen">
        <p style={{ color: "var(--color-error)", textAlign: "center" }}>
          Failed to initialise widget. Please refresh the page.
        </p>
      </div>
    );
  }

  return (
    <main
      style={{
        display: "flex",
        alignItems: "stretch",
        justifyContent: "center",
        height: "100%",
        padding: "1rem",
      }}
    >
      <ChatWidget
        agentName={UI_CONFIG.agentName}
        defaultMode={VAQUILL_CONFIG.defaultMode as VaquillMode}
        exampleQuestions={DEFAULT_QUESTIONS}
        ttsEnabled={capabilities?.tts_enabled ?? false}
        sttEnabled={capabilities?.stt_enabled ?? false}
      />
    </main>
  );
}
