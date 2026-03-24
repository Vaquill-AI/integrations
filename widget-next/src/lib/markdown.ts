/**
 * Markdown utilities for the Vaquill widget.
 */

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

/**
 * Strip all markdown syntax and return plain text.
 * Used for TTS input so the model doesn't read out formatting characters.
 */
export function stripMarkdown(markdown: string): string {
  return markdown
    .replace(/\*\*([^*]+)\*\*/g, "$1") // bold
    .replace(/\*([^*]+)\*/g, "$1") // italic
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // links
    .replace(/^#+\s+/gm, "") // headings
    .replace(/^>\s+/gm, "") // blockquotes
    .replace(/^[*-]\s+/gm, "") // unordered lists
    .replace(/`([^`]+)`/g, "$1") // inline code
    .trim();
}
