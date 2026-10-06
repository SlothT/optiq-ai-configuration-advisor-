export const ANSWER_LENGTHS = { short: 256, medium: 1024, long: 2048 };
export type AnswerLength = "automatic" | keyof typeof ANSWER_LENGTHS;

export function answerTokenLimit(prompt: string, length: AnswerLength): number {
  if (length !== "automatic") return ANSWER_LENGTHS[length];
  const words = prompt.match(/\b(\d[\d,]*)\s*[- ]?words?\b/i);
  if (words) {
    return Math.min(4096, Math.max(64, Math.ceil(Number(words[1].replace(/,/g, "")) * 1.5)));
  }
  if (/\b(short|brief|concise)\b/i.test(prompt)) return ANSWER_LENGTHS.short;
  if (/\b(long|detailed|comprehensive)\b/i.test(prompt)) return ANSWER_LENGTHS.long;
  return ANSWER_LENGTHS.medium;
}
