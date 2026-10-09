import { useEffect, useRef, useState } from "react";

/** Reveals text word by word the first time it appears live (history loads instantly). */
export function useTypewriter(text: string, live: boolean, wordsPerTick = 2, ms = 28) {
  const [n, setN] = useState(live ? 0 : Number.MAX_SAFE_INTEGER);
  const words = useRef<string[]>([]);
  words.current = text.split(/(\s+)/);
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => {
      setN((c) => {
        if (c >= words.current.length) {
          clearInterval(t);
          return c;
        }
        return c + wordsPerTick * 2;
      });
    }, ms);
    return () => clearInterval(t);
  }, [live, wordsPerTick, ms]);
  const done = n >= words.current.length;
  return { shown: done ? text : words.current.slice(0, n).join(""), done };
}
