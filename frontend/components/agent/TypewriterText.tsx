"use client";

import { useEffect, useState } from "react";

/** Reveals the agent's answer progressively instead of having it pop in whole — the same
 * "composing" read a person gets from a live assistant, even though the backend already
 * returned the complete string in one response (AGT-01 isn't a token stream). A blinking
 * caret plays while text is still revealing; `onDone` lets the caller stop re-running this
 * for a message once it's finished, so re-renders never restart the animation. */
export function TypewriterText({ text, onDone, speedMs = 12 }: { text: string; onDone?: () => void; speedMs?: number }) {
  const [shownLength, setShownLength] = useState(0);

  useEffect(() => {
    setShownLength(0);
    if (!text) return;
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setShownLength(i);
      if (i >= text.length) {
        clearInterval(id);
        onDone?.();
      }
    }, speedMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  const done = shownLength >= text.length;

  return (
    <>
      {text.slice(0, shownLength)}
      {!done && <span className="inline-block w-[2px] h-[1em] bg-current ml-0.5 align-middle animate-[pulse_0.8s_ease-in-out_infinite]" />}
    </>
  );
}
