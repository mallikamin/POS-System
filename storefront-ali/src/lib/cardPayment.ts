/**
 * Whether "Pay now by card" is offered.
 *
 * `SHOP.cardPaymentEnabled` is the real switch and stays **false** until a test
 * card has gone through end to end on the live site. Until then the site keeps
 * taking cash on handover, which is how the shop already runs.
 *
 * The override exists because of an awkward truth about testing this: the only
 * place the card flow can be proven is the live site, against the live API, on
 * the real domain — the browser has to reach Stripe and be redirected back to a
 * real URL. But the moment the button is visible, real customers can press it,
 * and while the server holds TEST keys a real customer's real card is declined.
 * They would be blocked from paying for no reason they could understand.
 *
 * So `?card=1` turns it on for whoever has the link and nobody else. We test on
 * the real thing while every ordinary customer keeps seeing exactly what they
 * see today. Once a test card has been captured and the live keys are in, the
 * flag flips and this override becomes irrelevant.
 *
 * ⚠️ This is not a security control. It hides a button; it does not protect the
 * endpoint. The backend is inert without a Stripe key, refuses to create a
 * session for an order that is already answered or paid, and verifies every
 * webhook signature. Anyone who finds `?card=1` reaches the same guarded API as
 * everyone else.
 */

import { SHOP } from "../data/menu";

export function cardPaymentOffered(): boolean {
  if (SHOP.cardPaymentEnabled) return true;
  try {
    return new URLSearchParams(window.location.search).get("card") === "1";
  } catch {
    return false;
  }
}
