/**
 * New-comment notifications: a fire-and-forget webhook ping so the blog owner learns a
 * comment landed (otherwise the store just writes it to D1 and nothing says so).
 *
 * The channel is configurable via NOTIFY_KIND (slack | discord | telegram); the
 * standard provider is inferred from the NOTIFY_WEBHOOK secret, with NOTIFY_KIND as an
 * optional override for proxy/custom URLs. Nothing is sent unless the webhook is set. Slack and
 * Discord take a plain JSON webhook; Telegram posts to a bot `sendMessage` URL and also
 * needs NOTIFY_TELEGRAM_CHAT. Best-effort: failures are logged, never surfaced to the
 * commenter, and the POST rides `waitUntil` so it doesn't delay the response.
 */
import type { Env } from "./config.js";
import {
  notificationMessage,
  notificationPayload,
  notificationRetryDelay,
  notificationShouldRetry,
  notifyKind,
  notifyKindFromUrl,
  type NotifyInput,
} from "./notify-core.js";

export type { NotifyInput } from "./notify-core.js";

/** The bit of the Worker ExecutionContext we use (kept structural to avoid a type import). */
interface WaitUntil {
  waitUntil(p: Promise<unknown>): void;
}

async function post(url: string, body: unknown): Promise<Response> {
  return fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function deliver(url: string, kind: string, body: unknown): Promise<void> {
  let first: Response | undefined;
  try {
    first = await post(url, body);
    if (first.ok) return;
    if (!notificationShouldRetry(first.status)) {
      console.warn(`notify(${kind}) failed:`, first.status);
      return;
    }
  } catch {
    // A network failure is transient enough to merit the same single bounded retry.
  }

  const retryAfter = first?.headers.get("retry-after") ?? null;
  await new Promise((resolve) => setTimeout(resolve, notificationRetryDelay(retryAfter)));
  try {
    const second = await post(url, body);
    if (!second.ok) console.warn(`notify(${kind}) failed after retry:`, second.status);
  } catch (e: unknown) {
    console.warn(`notify(${kind}) error after retry:`, String(e));
  }
}

export function notifyNewComment(env: Env, ctx: WaitUntil | undefined, input: NotifyInput): void {
  const url = env.NOTIFY_WEBHOOK || "";
  if (!url) return; // notifications disabled
  const configuredKind = notifyKind(env.NOTIFY_KIND);
  const kind = configuredKind || notifyKindFromUrl(url);
  if (!kind) {
    console.warn("notify: could not infer a provider from NOTIFY_WEBHOOK; set a valid NOTIFY_KIND override");
    return;
  }
  const body = notificationPayload(kind, { telegramChat: env.NOTIFY_TELEGRAM_CHAT }, notificationMessage(input));
  if (!body) return;
  const task = deliver(url, kind, body);
  if (ctx && typeof ctx.waitUntil === "function") ctx.waitUntil(task);
  else void task;
}
