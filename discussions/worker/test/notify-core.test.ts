import assert from "node:assert/strict";
import test from "node:test";
import {
  commentPermalink,
  notificationMessage,
  notificationPayload,
  notifyKind,
  type NotifyInput,
} from "../src/notify-core.ts";

const input: NotifyInput = {
  commentId: "c_123",
  author: "German",
  authorLogin: "Kronuz",
  postTitle: "House Rules",
  postTerm: "house-rules",
  postUrl: "https://kronuz.github.io/blog/house-rules/",
  siteUrl: "https://kronuz.github.io",
  body: "A comment",
  isReply: false,
};

test("builds the same stable comment permalink used by the feed", () => {
  assert.equal(
    commentPermalink(input.postUrl, input.siteUrl, input.commentId),
    "https://kronuz.github.io/blog/house-rules/#c_123",
  );
  assert.equal(commentPermalink(null, input.siteUrl, input.commentId), "https://kronuz.github.io#c_123");
});

test("uses the term and site URL fallbacks and identifies replies", () => {
  const text = notificationMessage({ ...input, postTitle: null, postUrl: null, isReply: true });
  assert.match(text, /^💬 New reply by German on “house-rules”/);
  assert.match(text, /https:\/\/kronuz\.github\.io#c_123$/);
});

test("recognizes only configured providers", () => {
  assert.equal(notifyKind(" Discord "), "discord");
  assert.equal(notifyKind(""), null);
  assert.equal(notifyKind("discrod"), null);
});

test("builds a Discord payload", () => {
  assert.deepEqual(notificationPayload("discord", {}, "hello"), { content: "hello" });
});

test("builds Slack and Telegram payloads", () => {
  assert.deepEqual(notificationPayload("slack", {}, "hello"), { text: "hello" });
  assert.deepEqual(notificationPayload("telegram", { telegramChat: "42" }, "hello"), {
    chat_id: "42",
    text: "hello",
    disable_web_page_preview: false,
  });
  assert.equal(notificationPayload("telegram", {}, "hello"), null);
});
