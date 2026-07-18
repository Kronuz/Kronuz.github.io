/**
 * New-comment notifications: a fire-and-forget webhook ping so the blog owner learns a
 * comment landed (otherwise the store just writes it to D1 and nothing says so).
 *
 * The channel is configurable via NOTIFY_KIND (slack | discord | telegram); the
 * destination is the NOTIFY_WEBHOOK secret, so nothing is sent unless it's set. Slack and
 * Discord take a plain JSON webhook; Telegram posts to a bot `sendMessage` URL and also
 * needs NOTIFY_TELEGRAM_CHAT. Best-effort: failures are logged, never surfaced to the
 * commenter, and the POST rides `waitUntil` so it doesn't delay the response.
 */
import type { Env } from "./config.js";
import {
  notificationMessage,
  notificationPayload,
  notifyKind,
  type NotifyInput,
} from "./notify-core.js";

export type { NotifyInput } from "./notify-core.js";

/** The bit of the Worker ExecutionContext we use (kept structural to avoid a type import). */
interface WaitUntil {
  waitUntil(p: Promise<unknown>): void;
}

export function notifyNewComment(env: Env, ctx: WaitUntil | undefined, input: NotifyInput): void {
  const url = env.NOTIFY_WEBHOOK || "";
  if (!url) return; // notifications disabled
  const kind = notifyKind(env.NOTIFY_KIND);
  if (!kind) {
    if ((env.NOTIFY_KIND || "").trim()) console.warn(`notify: unsupported NOTIFY_KIND ${env.NOTIFY_KIND}`);
    return;
  }
  const body = notificationPayload(kind, { telegramChat: env.NOTIFY_TELEGRAM_CHAT }, notificationMessage(input));
  if (!body) return;
  const task = fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  })
    .then((r) => {
      if (!r.ok) console.warn(`notify(${kind}) failed:`, r.status);
    })
    .catch((e: unknown) => console.warn(`notify(${kind}) error:`, String(e)));
  if (ctx && typeof ctx.waitUntil === "function") ctx.waitUntil(task);
  else void task;
}
