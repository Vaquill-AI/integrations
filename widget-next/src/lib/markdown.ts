/**
 * Markdown utilities for the Vaquill widget.
 */

/**
 * Convert inline `[N]` citation markers in the answer text into markdown
 * links that anchor to the matching source card (`#src-{msgId}-{N}`).
 *
 * Handles `[1]`, `[1][2][3]`, and `[1, 2]` / `[1,2]` runs. Only N values
 * present in `validIndices` are linkified — bogus markers left by the LLM
 * stay as plain text.
 */
export function linkifyCitations(
  markdown: string,
  msgId: string,
  validIndices: ReadonlySet<number>
): string {
  if (!validIndices.size) return markdown;

  // Split `[1, 2]` runs into adjacent `[1][2]` so a single-marker pass
  // can handle all variants uniformly.
  const expanded = markdown.replace(/\[(\d+(?:\s*,\s*\d+)+)\]/g, (_m, group: string) =>
    group
      .split(/\s*,\s*/)
      .map((n) => `[${n.trim()}]`)
      .join("")
  );

  return expanded.replace(/\[(\d+)\]/g, (match, nStr: string) => {
    const n = Number(nStr);
    if (!validIndices.has(n)) return match;
    // Escape the brackets so ReactMarkdown renders them as literal `[N]`
    // inside the link label.
    return `[\\[${n}\\]](#src-${msgId}-${n})`;
  });
}

/**
 * Light post-processing for markdown received from the Vaquill API.
 * Fixes common formatting quirks without destructively altering the content.
 */
export function processMarkdown(markdown: string): string {
  let processed = markdown;

  // Normalise blockquotes
  processed = processed.replace(/^>\s*/gm, "> ");

  // Normalise unordered list bullets
  processed = processed.replace(/^([*-])\s*/gm, "$1 ");

  // Normalise ordered list items
  processed = processed.replace(/^(\d+\.)\s*/gm, "$1 ");

  // Collapse runs of 3+ blank lines to a single blank line
  processed = processed.replace(/\n{3,}/g, "\n\n");

  return processed.trim();
}

