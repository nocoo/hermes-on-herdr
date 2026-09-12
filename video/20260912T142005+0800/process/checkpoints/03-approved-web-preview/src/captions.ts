import { timing } from "./timeline";

// Measured sentence boundaries; proportional phrase timing keeps this review
// readable. Word-level alignment is not claimed. SRT retains exact sentences.
export const displayCaptions = timing.captions.flatMap((caption) => {
  const phrases: string[] = [""];
  for (const word of caption.text.split(" ")) {
    const last = phrases.length - 1;
    const current = phrases[last] ?? "";
    if (current.length && current.length + word.length + 1 > 72) phrases.push(word);
    else phrases[last] = current ? `${current} ${word}` : word;
  }
  const length = phrases.reduce((sum, phrase) => sum + phrase.length, 0);
  let start = caption.start;
  return phrases.map((text, i) => {
    const end =
      i === phrases.length - 1
        ? caption.end
        : start + ((caption.end - caption.start) * text.length) / length;
    const entry = { scene: caption.scene, text, start, end };
    start = end;
    return entry;
  });
});

export function captionAt(seconds: number) {
  return displayCaptions.find((caption) => seconds >= caption.start && seconds < caption.end);
}
