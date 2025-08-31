#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
import secrets

# Optional: load .env to populate DATABASE_URL, etc.
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

from app.db import init_db, get_session, create_all, drop_all
from app.models import APIKey, Platform, Resource, ResourceShopID, User, Purchase
from sqlalchemy import select, delete, update, text
from utils.api_key import new_api_key_record


def maybe_load_dotenv():
    env_path = Path(__file__).parent / ".env"
    if load_dotenv and env_path.exists():
        load_dotenv(env_path)


async def cmd_create(name: str | None, scopes: list[str] | None, length: int) -> None:
    async with get_session() as session:
        kid, plain, stored = new_api_key_record(length=length)
        row = APIKey(
            id=kid,
            name=name or "generated",
            hash=stored,
            method="pbkdf2_sha256",
            active=True,
            scopes=scopes or None,
        )
        session.add(row)
        await session.commit()
        print("Created API key")
        print(f"id: {kid}")
        print(f"key: {plain}")
        if scopes:
            print(f"scopes: {scopes}")


async def cmd_list(json_out: bool) -> None:
    async with get_session() as session:
        result = await session.execute(select(APIKey))
        rows = result.scalars().all()
        if json_out:
            out = [
                {
                    "id": r.id,
                    "name": r.name,
                    "active": r.active,
                    "created_at": (r.created_at.isoformat() if r.created_at else None),
                    "last_used_at": (r.last_used_at.isoformat() if r.last_used_at else None),
                    "scopes": r.scopes,
                }
                for r in rows
            ]
            print(json.dumps(out, indent=2))
            return
        for r in rows:
            created = r.created_at.isoformat() if r.created_at else ""
            last = r.last_used_at.isoformat() if r.last_used_at else ""
            print(f"- id={r.id} name={r.name} active={r.active} created_at={created} last_used_at={last} scopes={r.scopes}")


async def _set_active(kid: str, active: bool) -> int:
    async with get_session() as session:
        res = await session.execute(
            update(APIKey).where(APIKey.id == kid).values(active=active)
        )
        await session.commit()
        return res.rowcount or 0


async def cmd_activate(kid: str) -> None:
    changed = await _set_active(kid, True)
    if changed:
        print(f"Activated {kid}")
    else:
        print(f"No API key found with id {kid}")


async def cmd_deactivate(kid: str) -> None:
    changed = await _set_active(kid, False)
    if changed:
        print(f"Deactivated {kid}")
    else:
        print(f"No API key found with id {kid}")


async def cmd_delete(kid: str) -> None:
    async with get_session() as session:
        res = await session.execute(delete(APIKey).where(APIKey.id == kid))
        await session.commit()
        if (res.rowcount or 0) > 0:
            print(f"Deleted {kid}")
        else:
            print(f"No API key found with id {kid}")


async def ensure_db_ready() -> None:
    # initialize engine/session and ensure tables exist
    init_db()
    await create_all()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="API Key management CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Initialize first API key if none exists
    sub.add_parser("init-key", help="Create the first API key only if none exists (prints id and key)")

    p_create = sub.add_parser("create", help="Create a new API key")
    p_create.add_argument("--name", help="Optional name")
    p_create.add_argument("--scopes", nargs="*", help="Optional scopes", default=None)
    p_create.add_argument("--length", type=int, default=48, help="API key length (default: 48)")

    p_list = sub.add_parser("list", help="List API keys")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    p_act = sub.add_parser("activate", help="Activate a key by id")
    p_act.add_argument("id", help="API key id")

    p_deact = sub.add_parser("deactivate", help="Deactivate a key by id")
    p_deact.add_argument("id", help="API key id")

    p_del = sub.add_parser("delete", help="Delete a key by id")
    p_del.add_argument("id", help="API key id")

    p_env = sub.add_parser("init-env", help="Generate .env from template and inject secure SECRET_KEY")
    p_env.add_argument("--force", action="store_true", help="Overwrite existing .env if present")
    p_env.add_argument("--database-url", help="DATABASE_URL value to set (optional)")

    # DB management
    p_reset = sub.add_parser("db-reset", help="Drop and recreate all tables (DANGEROUS)")
    p_reset.add_argument("--yes-i-am-sure", action="store_true", help="Confirm destructive action")

    p_export = sub.add_parser("db-export", help="Export database to JSON file")
    p_export.add_argument("--output", default="data/export.json", help="Output JSON path (default: data/export.json)")

    p_import = sub.add_parser("db-import", help="Import database from JSON file")
    p_import.add_argument("--input", required=True, help="Input JSON path")
    p_import.add_argument("--wipe", action="store_true", help="Drop and recreate tables before import")

    p_test = sub.add_parser("db-test", help="Test database connectivity")

    # Refresh resources from data/plugins.json (safe upsert)
    p_refresh = sub.add_parser("resources-refresh", help="Refresh resources from data/plugins.json (safe upsert)")
    p_refresh.add_argument("--file", default="data/plugins.json", help="Path to plugins.json (default: data/plugins.json)")

    # Start development server
    p_start = sub.add_parser("start", help="Start Flask development server")
    p_start.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    p_start.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    p_start.add_argument("--debug", action="store_true", help="Enable debug mode")

    return p


async def main_async(args) -> None:
    if args.cmd == "init-key":
        await ensure_db_ready()
        # Only create a key if none exists yet
        async with get_session() as session:
            exists = (await session.execute(select(APIKey).limit(1))).scalar_one_or_none()
            if exists is not None:
                print("An API key already exists. Use 'python manage.py list' to view ids or 'create' to add more.")
                return
            kid, plain, stored = new_api_key_record(length=48)
            row = APIKey(id=kid, name="default", hash=stored, method="pbkdf2_sha256", active=True)
            session.add(row)
            await session.commit()
            print("Initial API key created")
            print(f"id: {kid}")
            print(f"key: {plain}")
        return
    if args.cmd == "create":
        await ensure_db_ready()
        await cmd_create(args.name, args.scopes, args.length)
    elif args.cmd == "list":
        await ensure_db_ready()
        await cmd_list(args.json)
    elif args.cmd == "activate":
        await ensure_db_ready()
        await cmd_activate(args.id)
    elif args.cmd == "deactivate":
        await ensure_db_ready()
        await cmd_deactivate(args.id)
    elif args.cmd == "delete":
        await ensure_db_ready()
        await cmd_delete(args.id)
    elif args.cmd == "init-env":
        await cmd_init_env(force=args.force, database_url=args.database_url)
    elif args.cmd == "db-reset":
        await cmd_db_reset(confirm=args.yes_i_am_sure)
    elif args.cmd == "db-export":
        await ensure_db_ready()
        await cmd_db_export(output=args.output)
    elif args.cmd == "db-import":
        await cmd_db_import(input_path=args.input, wipe=args.wipe)
    elif args.cmd == "db-test":
        await cmd_db_test()
    elif args.cmd == "resources-refresh":
        await cmd_resources_refresh(file_path=args.file)
    else:
        raise SystemExit(2)


def _set_kv_lines(lines: list[str], key: str, value: str) -> list[str]:
    out: list[str] = []
    found = False
    for ln in lines:
        if ln.strip().startswith(f"{key}=") or ln.strip().startswith(f"{key}="):
            out.append(f"{key}={value}\n")
            found = True
        else:
            out.append(ln)
    if not found:
        if out and not out[-1].endswith("\n"):
            out[-1] = out[-1] + "\n"
        out.append(f"{key}={value}\n")
    return out


async def cmd_init_env(*, force: bool, database_url: str | None) -> None:
    root = Path(__file__).parent
    env_path = root / ".env"
    example_path = root / ".env.example"

    if env_path.exists() and not force:
        print(".env already exists. Use --force to overwrite.")
        return

    content: list[str] = []
    if example_path.exists():
        content = example_path.read_text().splitlines(keepends=True)
    else:
        # minimal template if no example found
        content = [
            "# Environment configuration\n",
            "# DATABASE_URL=postgresql://user:pass@host:5432/dbname\n",
        ]

    # Generate a secure SECRET_KEY
    secret = secrets.token_urlsafe(48)
    content = _set_kv_lines(content, "SECRET_KEY", secret)

    if database_url:
        content = _set_kv_lines(content, "DATABASE_URL", database_url)

    env_path.write_text("".join(content))
    print(f"Written {env_path}")


def _row_to_dict(model_obj) -> dict:
    return {c.name: getattr(model_obj, c.name) for c in model_obj.__table__.columns}


async def cmd_db_reset(*, confirm: bool) -> None:
    if not confirm:
        print("Refusing to run without --yes-i-am-sure")
        return
    init_db()
    await drop_all()
    await create_all()
    print("Database dropped and recreated.")


async def cmd_db_export(*, output: str) -> None:
    from pathlib import Path
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async with get_session() as session:
        data: dict[str, list[dict]] = {}

        # Export order: platforms, resources, resource_shop_ids, users, purchases, api_keys
        plats = (await session.execute(select(Platform))).scalars().all()
        data["platforms"] = [_row_to_dict(p) for p in plats]

        ress = (await session.execute(select(Resource))).scalars().all()
        data["resources"] = [_row_to_dict(r) for r in ress]

        links = (await session.execute(select(ResourceShopID))).scalars().all()
        data["resource_shop_ids"] = [_row_to_dict(l) for l in links]

        users = (await session.execute(select(User))).scalars().all()
        data["users"] = [_row_to_dict(u) for u in users]

        purchases = (await session.execute(select(Purchase))).scalars().all()
        data["purchases"] = [_row_to_dict(p) for p in purchases]

        keys = (await session.execute(select(APIKey))).scalars().all()
        # Do not export plaintext keys (we only have hashes)
        data["api_keys"] = [_row_to_dict(k) for k in keys]

    Path(output).write_text(json.dumps(data, indent=2, default=str))
    print(f"Exported data to {out_path}")


async def cmd_db_import(*, input_path: str, wipe: bool) -> None:
    init_db()
    if wipe:
        await drop_all()
        await create_all()

    from pathlib import Path
    p = Path(input_path)
    if not p.exists():
        print(f"Input not found: {input_path}")
        return

    payload = json.loads(p.read_text())

    async with get_session() as session:
        # Insert in dependency-safe order, using merge to upsert by PK
        for rec in payload.get("platforms", []):
            session.merge(Platform(**rec))
        await session.flush()

        for rec in payload.get("resources", []):
            session.merge(Resource(**rec))
        await session.flush()

        for rec in payload.get("resource_shop_ids", []):
            session.merge(ResourceShopID(**rec))
        await session.flush()

        for rec in payload.get("users", []):
            session.merge(User(**rec))
        await session.flush()

        for rec in payload.get("purchases", []):
            session.merge(Purchase(**rec))
        await session.flush()

        for rec in payload.get("api_keys", []):
            session.merge(APIKey(**rec))
        await session.commit()

    print(f"Imported data from {input_path}")


async def cmd_db_test() -> None:
    """Verify DB connectivity and basic query execution."""
    try:
        init_db()
        # try a simple SELECT 1
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        print("Database connectivity: OK")
    except Exception as e:
        print(f"Database connectivity: FAILED - {e}")


def cmd_start(*, host: str, port: int, debug: bool) -> None:
    """Run the Flask development server.

    This uses the same app factory as `flask run` (see run.py) and is intended for convenience.
    """
    # Import locally to avoid import cycles and only create the app when needed
    from run import app
    app.run(host=host, port=port, debug=debug)


async def cmd_resources_refresh(*, file_path: str) -> None:
    """Safely upsert Platforms, Resources and ResourceShopID from plugins.json.

    This is non-destructive: it only inserts missing records and preserves existing data.
    Can be run while the app is up.
    """
    init_db()
    await create_all()

    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        print(f"plugins.json not found: {file_path}")
        return

    try:
        payload = json.loads(path.read_text())
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return

    # Keys mapping from json shops to platform names in DB
    key_map = {"spigotmc": "spigot", "polymart": "polymart", "builtbybit": "builtbybit"}

    async with get_session() as session:
        # Ensure platforms
        for name in ("spigot", "polymart", "builtbybit"):
            res_pl = await session.execute(select(Platform).where(Platform.name == name))
            if res_pl.scalar_one_or_none() is None:
                session.add(Platform(name=name))
        await session.commit()

        # Prefetch platforms into a map
        plats = await session.execute(select(Platform))
        plat_by_name = {p.name: p for p in plats.scalars().all()}

        # Iterate plugins and upsert Resource and ResourceShopID links
        created_resources = 0
        created_links = 0
        for item in payload or []:
            slug = item.get("id")
            name = item.get("name")
            if not slug or not name:
                continue

            # Resource upsert
            q_res = await session.execute(select(Resource).where(Resource.slug == slug))
            res = q_res.scalar_one_or_none()
            if res is None:
                res = Resource(slug=slug, name=name)
                session.add(res)
                await session.flush()
                created_resources += 1

            # Link per shop
            shops = (item.get("shops") or {})
            for shop_key, meta in shops.items():
                platform_name = key_map.get(shop_key)
                if not platform_name or platform_name not in plat_by_name:
                    continue
                platform = plat_by_name[platform_name]
                external_id = str(meta.get("resource_id")) if meta and meta.get("resource_id") is not None else None
                if not external_id:
                    continue

                link_q = await session.execute(
                    select(ResourceShopID).where(
                        ResourceShopID.resource_id == res.id,
                        ResourceShopID.platform_id == platform.id,
                    )
                )
                if link_q.scalar_one_or_none() is None:
                    session.add(
                        ResourceShopID(
                            resource_id=res.id,
                            platform_id=platform.id,
                            external_resource_id=external_id,
                        )
                    )
                    created_links += 1

        await session.commit()
        print(
            f"Refresh complete. Added {created_resources} new resources and {created_links} shop links from {file_path}."
        )


def main() -> None:
    maybe_load_dotenv()
    args = build_parser().parse_args()
    if args.cmd == "start":
        # Run server outside of asyncio.run to avoid event loop conflicts
        cmd_start(host=args.host, port=args.port, debug=args.debug)
        return
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
