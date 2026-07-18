/** Pure notification formatting shared by webhook delivery and the Atom feed. */

export type NotifyKind = "discord" | "slack" | "telegram";

export interface NotifyInput {
  commentId: string;
  author: string;
  authorLogin: string;
  postTitle: string | null;
  postTerm: string | null;
  postUrl: string | null;
  siteUrl: string;
  body: string;
  isReply: boolean;
}

export interface NotifyPayloadEnv {
  telegramChat?: string;
}

export function notifyKind(value: string | undefined): NotifyKind | null {
  const kind = (value || "").trim().toLowerCase();
  return kind === "discord" || kind === "slack" || kind === "telegram" ? kind : null;
}

export function commentPermalink(postUrl: string | null, siteUrl: string, commentId: string): string | null {
  const base = postUrl || siteUrl;
  if (!base) return null;
  return `${base.split("#", 1)[0]}#${commentId}`;
}

function excerpt(s: string, n = 240): string {
  const one = (s || "").replace(/\s+/g, " ").trim();
  return one.length > n ? one.slice(0, n - 1) + "\u2026" : one;
}

export function notificationMessage(input: NotifyInput): string {
  const what = input.isReply ? "reply" : "comment";
  const who = input.author || input.authorLogin || "someone";
  const post = input.postTitle || input.postTerm;
  const where = post ? `\u201c${post}\u201d` : "your blog";
  const lines = [`\ud83d\udcac New ${what} by ${who} on ${where}`, excerpt(input.body)];
  const permalink = commentPermalink(input.postUrl, input.siteUrl, input.commentId);
  if (permalink) lines.push(permalink);
  return lines.filter(Boolean).join("\n");
}

export function notificationPayload(kind: NotifyKind, env: NotifyPayloadEnv, text: string): unknown | null {
  switch (kind) {
    case "discord":
      return { content: text };
    case "telegram":
      if (!env.telegramChat) return null;
      return { chat_id: env.telegramChat, text, disable_web_page_preview: false };
    case "slack":
      return { text };
  }
}
