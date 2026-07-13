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

/** The bit of the Worker ExecutionContext we use (kept structural to avoid a type import). */
interface WaitUntil {
  waitUntil(p: Promise<unknown>): void;
}

export interface NotifyInput {
  author: string;
  authorLogin: string;
  postTitle: string | null;
  postUrl: string | null;
  body: string;
  isReply: boolean;
}

function excerpt(s: string, n = 240): string {
  const one = (s || "").replace(/\s+/g, " ").trim();
  return one.length > n ? one.slice(0, n - 1) + "\u2026" : one;
}

function message(input: NotifyInput): string {
  const what = input.isReply ? "reply" : "comment";
  const who = input.author || input.authorLogin || "someone";
  const where = input.postTitle ? `\u201c${input.postTitle}\u201d` : "your blog";
  const lines = [`\ud83d\udcac New ${what} by ${who} on ${where}`, excerpt(input.body)];
  if (input.postUrl) lines.push(input.postUrl);
  return lines.filter(Boolean).join("\n");
}

/** Build the webhook body for the configured channel, or null when it can't/shouldn't send. */
function payload(kind: string, env: Env, text: string): unknown | null {
  switch (kind) {
    case "discord":
      return { content: text };
    case "telegram": {
      const chat = env.NOTIFY_TELEGRAM_CHAT || "";
      if (!chat) return null;
      return { chat_id: chat, text, disable_web_page_preview: false };
    }
    case "slack":
    default:
      return { text };
  }
}

export function notifyNewComment(env: Env, ctx: WaitUntil | undefined, input: NotifyInput): void {
  const url = env.NOTIFY_WEBHOOK || "";
  if (!url) return; // notifications disabled
  const kind = (env.NOTIFY_KIND || "slack").toLowerCase();
  const body = payload(kind, env, message(input));
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
