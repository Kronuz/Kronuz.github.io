"""Self-cleaning end-to-end smoke test for the comment backend.

Drives the active store through the full comment lifecycle against the live SQLite DB
(add -> read -> react -> edit -> hide/unhide -> delete), under a throwaway term, and
removes everything it creates. Asserts tenant scoping along the way. Safe to run against
production: it only touches its own `__smoke__<rand>` term and cleans up after itself.

    cd discussions/backend && ./.venv/bin/python smoke_test.py
"""
import asyncio
import os
import secrets
import sys

# Run from the backend dir; load .env so config matches the running service.
os.chdir(os.path.dirname(os.path.abspath(__file__)))
for _line in open(".env"):
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k, _v.strip().strip('"').strip("'"))
sys.path.insert(0, ".")

from discussions.config import DEFAULT_TENANT_ID  # noqa: E402
from discussions.db import build_database  # noqa: E402
from discussions.store.selfhosted import SelfHostedStore  # noqa: E402
from discussions.tenants import DbTenants  # noqa: E402

TERM = "__smoke__" + secrets.token_hex(4)
USER = {"login": "smoke-bot", "name": "Smoke Bot", "avatarUrl": "", "url": "", "is_admin": False}
ADMIN = {"login": "smoke-admin", "name": "Smoke Admin", "avatarUrl": "", "url": "", "is_admin": True}

_n = 0
def check(label, cond):
    global _n
    print(("  PASS " if cond else "  FAIL ") + label)
    assert cond, "FAILED: " + label
    _n += 1


async def main():
    db = build_database()
    await db.init()
    tenants = DbTenants(db)
    await tenants.load()  # seeds the default tenant from env + loads the registry cache
    store = SelfHostedStore(db, tenants)
    # Moderation is per-tenant now (tenants.is_admin against the comment's tenant), not
    # the viewer's self-reported flag. Register the throwaway admin as a moderator of the
    # default tenant so it can hide/delete here; removed in cleanup. A second synthetic
    # tenant id (never written to) is used for read-isolation + per-tenant-admin checks.
    T2 = "__smoke_t2__" + secrets.token_hex(4)
    await db._conn.execute(
        "INSERT OR IGNORE INTO tenant_admins(tenant_id, login) VALUES(?,?)",
        (DEFAULT_TENANT_ID, ADMIN["login"]))
    await db._conn.commit()
    await tenants.load()
    print(f"[smoke] term={TERM} tenant={DEFAULT_TENANT_ID}")

    cid = rid = None
    try:
        c = await store.add_comment(tenant_id=DEFAULT_TENANT_ID, term=TERM, title="Smoke",
                                    subtitle=None, url="https://x/smoke",
                                    body="hello **smoke**", reply_to_id=None, viewer=USER)
        cid = c["id"]
        check("comment created", cid.startswith("c_"))
        check("comment tenant_id is default",
              (await db.comment_get(cid))["tenant_id"] == DEFAULT_TENANT_ID)
        check("markdown rendered", "<strong>smoke</strong>" in c["bodyHTML"])

        r = await store.add_comment(tenant_id=DEFAULT_TENANT_ID, term=TERM, title=None,
                                    subtitle=None, url=None, body="a reply",
                                    reply_to_id=cid, viewer=USER)
        rid = r["id"]
        check("reply created", rid.startswith("c_"))

        disc = await store.get_discussion(tenant_id=DEFAULT_TENANT_ID, term=TERM,
                                          after=None, first=20, viewer=USER)
        check("discussion read back", disc["discussion"]["totalCount"] == 1)
        check("reply nested", disc["comments"][0]["replyCount"] == 1)
        check("discussion title stored", disc["discussion"]["title"] == "Smoke")

        # Tenant scoping: the same term under a different tenant sees none of these rows.
        other_t = await store.get_discussion(tenant_id=T2, term=TERM, after=None,
                                             first=20, viewer=None)
        check("read is tenant-scoped (other tenant sees 0)",
              other_t["discussion"]["totalCount"] == 0)
        # Per-tenant admin: a default-tenant moderator is not a moderator of another tenant.
        check("admin scoped to its tenant", tenants.is_admin(DEFAULT_TENANT_ID, ADMIN["login"]))
        check("admin not global across tenants", not tenants.is_admin(T2, ADMIN["login"]))

        rr = await store.react(comment_id=cid, content="ROCKET", on=True, viewer=USER)
        check("reaction added", any(x["content"] == "ROCKET" for x in rr["reactions"]))

        ed = await store.edit_comment(comment_id=cid, body="edited smoke", viewer=USER)
        check("comment edited", ed["bodyMarkdown"] == "edited smoke")

        hd = await store.set_hidden(comment_id=cid, hide=True, reason="SPAM", viewer=ADMIN)
        check("admin hid comment", hd["isMinimized"] and hd["minimizedReason"] == "SPAM")
        un = await store.set_hidden(comment_id=cid, hide=False, reason=None, viewer=ADMIN)
        check("admin unhid comment", not un["isMinimized"])

        # authz: a non-admin, non-author can't edit
        other = {"login": "stranger", "name": "S", "avatarUrl": "", "url": "", "is_admin": False}
        try:
            await store.edit_comment(comment_id=cid, body="hax", viewer=other)
            check("stranger edit blocked", False)
        except Exception as e:
            check("stranger edit blocked (403)", getattr(e, "status_code", None) == 403)
    finally:
        # Clean up: delete the comment (cascades to its reply + reactions), drop the
        # throwaway discussion row, and remove the admin grant we added so no residue
        # remains (the synthetic T2 was never written to).
        if cid:
            await store.delete_comment(comment_id=cid, viewer=ADMIN)
        await db._conn.execute("DELETE FROM discussions WHERE tenant_id=? AND term=?",
                               (DEFAULT_TENANT_ID, TERM))
        await db._conn.execute("DELETE FROM tenant_admins WHERE tenant_id=? AND login=?",
                               (DEFAULT_TENANT_ID, ADMIN["login"]))
        await db._conn.commit()
        await tenants.load()

    gone = await store.get_discussion(tenant_id=DEFAULT_TENANT_ID, term=TERM,
                                      after=None, first=20, viewer=None)
    check("cleanup removed the thread", gone["discussion"]["totalCount"] == 0)
    left = await db.comment_get(cid) if cid else None
    check("cleanup removed the comment row", left is None)

    await db.close()
    print(f"\nALL {_n} SMOKE CHECKS PASSED")


asyncio.run(main())
