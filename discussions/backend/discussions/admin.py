"""Tiny tenant-admin CLI for the multi-tenant comment backend (phase 3).

Registers the blogs that may use this server and who moderates each. It writes the same
SQLite DB the server reads; a running server picks up changes within TENANT_REFRESH_SECONDS
(app.py), so onboarding a blog needs no restart. Origin enforcement (app.py) then rejects
any blog whose origin isn't registered here.

Run from the backend dir with the service's venv so DB_PATH/.env match the server:

    ./.venv/bin/python -m discussions.admin tenant list
    ./.venv/bin/python -m discussions.admin tenant add --id myblog \
        --origin https://my.example --repo org/myblog \
        --repo-url https://github.com/org/myblog --admins alice,bob
    ./.venv/bin/python -m discussions.admin admin add --tenant myblog --login carol
    ./.venv/bin/python -m discussions.admin tenant rm --id myblog [--purge]
"""
import argparse
import asyncio
import os
import sys


def _load_env() -> None:
    # Mirror run.sh: source the backend's .env so DB_PATH (and friends) match the server.
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(backend_dir, ".env")
    if not os.path.exists(env_path):
        return
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def _split(csv: str) -> list:
    return [s.strip() for s in (csv or "").split(",") if s.strip()]


async def _run(args) -> int:
    from . import db
    await db.init()
    try:
        if args.cmd == "tenant" and args.action == "add":
            await db.tenant_create(args.id, args.origin, args.repo, args.repo_url,
                                   _split(args.admins), args.strip_suffix, args.giphy_key)
            t = await db.tenant_get(args.id)
            admins = await db.tenant_admins(args.id)
            print(f"ok: tenant {t['id']} origin={t['origin']} repo={t['repo']} "
                  f"admins={','.join(sorted(admins)) or '-'} "
                  f"stripSuffix={t['strip_suffix'] or '-'} "
                  f"giphyKey={'set' if t['giphy_key'] else '-'}")
        elif args.cmd == "tenant" and args.action == "rm":
            if not await db.tenant_get(args.id):
                print(f"no such tenant: {args.id}", file=sys.stderr)
                return 1
            await db.tenant_delete(args.id, purge=args.purge)
            print(f"ok: removed tenant {args.id}" + (" (purged its data)" if args.purge else ""))
        elif args.cmd == "tenant" and args.action == "list":
            tenants = await db.tenant_list()
            if not tenants:
                print("(no tenants)")
            for t in tenants:
                print(f"{t['id']}\torigin={t['origin']}\trepo={t['repo']}\t"
                      f"admins={','.join(t['admins']) or '-'}")
        elif args.cmd == "admin" and args.action == "add":
            if not await db.tenant_get(args.tenant):
                print(f"no such tenant: {args.tenant}", file=sys.stderr)
                return 1
            await db.tenant_admin_add(args.tenant, args.login)
            print(f"ok: {args.login} now moderates {args.tenant}")
        elif args.cmd == "admin" and args.action == "rm":
            await db.tenant_admin_remove(args.tenant, args.login)
            print(f"ok: {args.login} no longer moderates {args.tenant}")
        else:
            print("unknown command", file=sys.stderr)
            return 2
    finally:
        await db.close()
    return 0


def main() -> int:
    _load_env()
    p = argparse.ArgumentParser(prog="discussions.admin", description="Tenant admin CLI.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("tenant", help="manage tenants (hosted blogs)")
    ts = pt.add_subparsers(dest="action", required=True)
    a = ts.add_parser("add", help="create or update a tenant")
    a.add_argument("--id", required=True, help="tenant id (stable key)")
    a.add_argument("--origin", required=True, help="the blog's site origin (e.g. https://x.example)")
    a.add_argument("--repo", default="", help="owner/name of the blog's repo")
    a.add_argument("--repo-url", dest="repo_url", default="", help="'view on GitHub' URL")
    a.add_argument("--admins", default="", help="comma-separated moderator logins")
    a.add_argument("--strip-suffix", dest="strip_suffix", default="",
                   help="login suffix to hide when displaying handles (e.g. an EMU org suffix)")
    a.add_argument("--giphy-key", dest="giphy_key", default="",
                   help="public GIPHY key; enables the widget's GIF picker for this blog")
    r = ts.add_parser("rm", help="remove a tenant from the registry")
    r.add_argument("--id", required=True)
    r.add_argument("--purge", action="store_true", help="also delete its comments/reactions")
    ts.add_parser("list", help="list all tenants and their moderators")

    pa = sub.add_parser("admin", help="manage a tenant's moderators")
    as_ = pa.add_subparsers(dest="action", required=True)
    aa = as_.add_parser("add", help="grant a login moderator rights on a tenant")
    aa.add_argument("--tenant", required=True)
    aa.add_argument("--login", required=True)
    ar = as_.add_parser("rm", help="revoke a login's moderator rights on a tenant")
    ar.add_argument("--tenant", required=True)
    ar.add_argument("--login", required=True)

    args = p.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
