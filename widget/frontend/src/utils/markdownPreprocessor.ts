/**
 * Client-side markdown preprocessor — mirrors the Python version in backend.
 * Fixes common LLM markdown formatting issues before rendering.
 */
export function preprocessMarkdown(text: string): string {
  if (!text) return text;

  let result = text;

  // Fix headings: ###Word -> ### Word
  result = result.replace(/(#{1,6})([^\s#\n])/g, '$1 $2');

  // Ensure blank line before headings
  result = result.replace(/([^\n])\n(#{1,6}\s)/g, '$1\n\n$2');

  // Fix bold: **bold**word -> **bold** word
  result = result.replace(/(\*\*[^*\n]+?\*\*)([a-zA-Z0-9])/g, '$1 $2');

  // Fix italic: *italic*word -> *italic* word
  result = result.replace(/(?<!\*)(\*[^*\n]+?\*)(?!\*)([a-zA-Z0-9])/g, '$1 $2');

  // Fix numbered lists: 1.Item -> 1. Item
  result = result.replace(/(\n\d+\.)([^\s])/g, '$1 $2');

  // Fix bullet lists: -Item -> - Item
  result = result.replace(/(\n[-*+])([^\s])/g, '$1 $2');

  // Collapse 3+ blank lines to 2
  result = result.replace(/\n{3,}/g, '\n\n');

  return result.trim();
}
