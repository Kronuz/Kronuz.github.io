/**
 * GitHub client: the OAuth token exchange and the /user identity lookup.
 *
 * A port of the identity-only parts of discussions/backend/discussions/gh.py. The Python
 * module also carried a GraphQL transport for the github store; that store isn't part of
 * this Worker, so only sign-in remains. httpx becomes the Workers-native `fetch`.
 */
import { type Cfg, HttpError } from "./config.js";

const UA = "blog-comments";

export interface GitHubUser {
  login: string;
  avatar_url: string;
  name?: string | null;
  html_url?: string | null;
}

/** Exchange an OAuth code for (access_token, granted_scope). */
export async function exchangeCode(cfg: Cfg, code: string): Promise<{ token: string; scope: string }> {
  const resp = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json", "User-Agent": UA },
    body: new URLSearchParams({
      client_id: cfg.oauthClientId,
      client_secret: cfg.oauthClientSecret,
      code,
      redirect_uri: cfg.publicBaseUrl + "/auth/callback",
    }),
  });
  const data = (await resp.json()) as { access_token?: string; scope?: string };
  if (!data.access_token) {
    throw new HttpError(502, "oauth exchange failed: " + JSON.stringify(data));
  }
  return { token: data.access_token, scope: data.scope || "" };
}

/** Fetch the signed-in user's public identity with their token. */
export async function user(token: string): Promise<GitHubUser> {
  const resp = await fetch("https://api.github.com/user", {
    headers: { Authorization: "bearer " + token, Accept: "application/vnd.github+json", "User-Agent": UA },
  });
  if (!resp.ok) throw new HttpError(502, "GitHub identity lookup failed");
  return (await resp.json()) as GitHubUser;
}
