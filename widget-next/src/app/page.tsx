import { VAQUILL_CONFIG } from "@/config/constants";
import ChatHost from "@/components/ChatHost";
import FloatingHost from "@/components/FloatingHost";

/**
 * Root entry point. Server-rendered so we can branch on the env var
 * before hydration.
 *
 *   - `?embed=1` always renders the chat (the iframe loaded by
 *     `embed.js` carries this flag, and we must serve the chat there
 *     to avoid recursion when the deployment is in floating mode).
 *   - Otherwise, `VAQUILL_EMBED_MODE` decides:
 *       `inline`   → chat (default)
 *       `floating` → demo page that injects `embed.js`
 */
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ embed?: string }>;
}) {
  const sp = await searchParams;

  if (sp.embed === "1" || VAQUILL_CONFIG.embedMode === "inline") {
    return <ChatHost />;
  }
  return <FloatingHost />;
}
