"use client";

import { useEffect, useState } from "react";

export interface SystemCapabilities {
  voice_mode_enabled: boolean;
  stt_enabled: boolean;
  tts_enabled: boolean;
  ai_completions_enabled: boolean;
  provider_info: {
    ai?: string;
    stt?: string;
    tts?: string;
  };
}

interface CapabilitiesState {
  capabilities: SystemCapabilities | null;
  loading: boolean;
  error: string | null;
}

const DEFAULT_CAPABILITIES: SystemCapabilities = {
  voice_mode_enabled: false,
  stt_enabled: false,
  tts_enabled: false,
  ai_completions_enabled: true,
  provider_info: { ai: "Vaquill" },
};

export function useCapabilities(): CapabilitiesState {
  const [state, setState] = useState<CapabilitiesState>({
    capabilities: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const res = await fetch("/api/agent/capabilities");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (mounted) {
          setState({
            capabilities: json.data ?? DEFAULT_CAPABILITIES,
            loading: false,
            error: null,
          });
        }
      } catch (err) {
        console.error("[useCapabilities] Failed:", err);
        if (mounted) {
          setState({
            capabilities: DEFAULT_CAPABILITIES,
            loading: false,
            error: err instanceof Error ? err.message : "Unknown error",
          });
        }
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, []);

  return state;
}
