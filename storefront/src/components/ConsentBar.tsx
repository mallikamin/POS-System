import { useEffect, useState } from "react";
import {
  denyConsent,
  grantConsent,
  replayStoredConsent,
  storedConsent,
} from "../lib/consent";

/**
 * Cookie consent bar.
 *
 * Sits at the bottom of the screen on a first visit and does nothing else.
 * Deliberately NOT a modal: this is a takeaway, and a customer who came to
 * order chips should never have their basket blocked behind a legal notice.
 * Declining is one tap, the same size as accepting, and the shop works
 * identically either way.
 *
 * It is above the basket bar in the stacking order for the few seconds it is
 * on screen, then gone for good on that device.
 */
export default function ConsentBar() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // A decision already made is replayed to the tag, not re-asked. Only a
    // visitor who has never answered sees the bar.
    replayStoredConsent();
    if (storedConsent() === null) setVisible(true);
  }, []);

  if (!visible) return null;

  function choose(accepted: boolean) {
    if (accepted) grantConsent();
    else denyConsent();
    setVisible(false);
  }

  return (
    <div
      role="dialog"
      aria-label="Cookies"
      className="fixed bottom-0 inset-x-0 z-50 p-4"
    >
      <div className="card mx-auto max-w-3xl p-4 flex flex-col sm:flex-row sm:items-center gap-3 shadow-2xl">
        <p className="text-sm text-cream/80 leading-relaxed flex-1">
          We use cookies to measure how well our ads work. You can order
          perfectly well without them.
        </p>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => choose(false)}
            className="btn-ghost tap flex-1 sm:flex-none"
          >
            No thanks
          </button>
          <button
            onClick={() => choose(true)}
            className="btn-primary tap flex-1 sm:flex-none"
          >
            Allow
          </button>
        </div>
      </div>
    </div>
  );
}
