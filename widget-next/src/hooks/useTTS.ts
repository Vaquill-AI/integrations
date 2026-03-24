"use client";

import { useState, useRef, useCallback, useEffect } from "react";

export type TTSStatus = "idle" | "loading" | "playing" | "error";

interface UseTTSResult {
  status: TTSStatus;
  error: string | null;
  play: (text: string, messageId: string) => Promise<void>;
  stop: () => void;
  currentMessageId: string | null;
}

export function useTTS(): UseTTSResult {
  const [status, setStatus] = useState<TTSStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [currentMessageId, setCurrentMessageId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStatus("idle");
    setCurrentMessageId(null);
    setError(null);
  }, []);

  const play = useCallback(
    async (text: string, messageId: string) => {
      try {
        stop();
        setStatus("loading");
        setCurrentMessageId(messageId);
        setError(null);

        const controller = new AbortController();
        abortRef.current = controller;

        const response = await fetch("/api/tts/speak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({ error: "Unknown" }));
          throw new Error(errData.error ?? `HTTP ${response.status}`);
        }

        const blob = await response.blob();
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        audioRef.current = audio;

        audio.onplay = () => setStatus("playing");
        audio.onended = () => {
          URL.revokeObjectURL(audioUrl);
          setStatus("idle");
          setCurrentMessageId(null);
          audioRef.current = null;
        };
        audio.onerror = () => {
          URL.revokeObjectURL(audioUrl);
          setStatus("error");
          setError("Audio playback failed");
          audioRef.current = null;
        };

        await audio.play();
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          setStatus("idle");
          setCurrentMessageId(null);
          return;
        }
        const message = err instanceof Error ? err.message : "TTS failed";
        console.error("[useTTS]", message);
        setStatus("error");
        setError(message);
        setCurrentMessageId(null);
      }
    },
    [stop]
  );

  return { status, error, play, stop, currentMessageId };
}
