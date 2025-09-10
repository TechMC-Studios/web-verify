from flask import Flask, jsonify

from .config import configure_app
from .db import init_db, create_all, get_session, get_engine
from sqlalchemy import select
from .models import APIKey, Platform, Resource, ResourceShopID
import asyncio
#from .seed import run_seed_and_bootstrap


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    configure_app(app)

    # Initialize database bindings
    init_db(app)


    # Organized bootstrap: create tables, seed base data, ensure API key
    async def _bootstrap():
        await create_all()

        async with get_session() as session:
            # 1) Seed platforms
            platform_names = ["spigot", "polymart"]
            for name in platform_names:
                existing = await session.execute(select(Platform).where(Platform.name == name))
                if existing.scalar_one_or_none() is None:
                    session.add(Platform(name=name))
            await session.commit()

            # 2) Seed resources from data/plugins.json (id -> slug, name)
            try:
                import json
                from pathlib import Path

                data_path = Path(app.root_path).parent / "data" / "plugins.json"
                if data_path.exists():
                    plugins = json.loads(data_path.read_text())
                    key_map = {"spigotmc": "spigot", "polymart": "polymart"}

                    # prefetch platforms
                    plats = await session.execute(select(Platform))
                    plat_by_name = {p.name: p for p in plats.scalars().all()}

                    for item in plugins:
                        slug = item.get("id")
                        name = item.get("name")
                        if not slug or not name:
                            continue
                        res_q = await session.execute(select(Resource).where(Resource.slug == slug))
                        res = res_q.scalar_one_or_none()
                        if res is None:
                            res = Resource(slug=slug, name=name)
                            session.add(res)
                            await session.flush()  # get PK

                        shops = (item.get("shops") or {})
                        for shop_key, meta in shops.items():
                            platform_name = key_map.get(shop_key)
                            if not platform_name or platform_name not in plat_by_name:
                                continue
                            platform = plat_by_name[platform_name]
                            external_id = str(meta.get("resource_id")) if meta and meta.get("resource_id") is not None else None
                            if not external_id:
                                continue
                            # ensure mapping exists
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
                    await session.commit()
            except Exception as e:
                # Non-fatal: seeding from plugins.json failed
                print(f"[BOOTSTRAP] Warning: failed seeding resources from plugins.json: {e}")

            # 3) API key is not auto-created anymore; instruct operator to create it manually
            result = await session.execute(select(APIKey).limit(1))
            first = result.scalar_one_or_none()
            if first is None:
                print("[BOOTSTRAP] No API key found. Create one by running: \n"
                      "  python manage.py init-key\n"
                      "or inside Docker: docker compose exec web python manage.py init-key")

        # Important: dispose engine to clear any connections created in this bootstrap loop
        # so they are not reused across a different asyncio loop during requests.
        try:
            engine = get_engine()
            await engine.dispose()
        except Exception:
            pass

    # Run bootstrap synchronously during app creation
    try:
        asyncio.run(_bootstrap())
    except RuntimeError:
        # In case an event loop is already running (e.g., within certain servers),
        # schedule the task instead of running a nested loop.
        loop = asyncio.get_event_loop()
        loop.create_task(_bootstrap())
    except Exception as e:
        # Do not crash app creation if DB is down. Mark unavailable and continue.
        app.config["DB_AVAILABLE"] = False
        print(f"[BOOTSTRAP] Database unavailable, continuing without DB: {e}")

    # Register blueprints lazily to avoid import cycles
    from .blueprints.health import bp as health_bp
    from .blueprints.verify import bp as verify_bp
    from .blueprints.resources import bp as resources_bp
    from .blueprints.users import bp as users_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(verify_bp, url_prefix="/verify")
    app.register_blueprint(resources_bp, url_prefix="/resources")
    app.register_blueprint(users_bp, url_prefix="/users")

    # Run seed and bootstrap (creates tables, seeds resources, creates API key)
    #with app.app_context():
    #    run_seed_and_bootstrap(app)

    # Register API key middleware
    from .auth import require_api_key
    app.before_request(require_api_key)

    # Error handlers to gracefully return 503 on DB connectivity errors
    try:
        from sqlalchemy.exc import OperationalError
        import asyncpg

        @app.errorhandler(OperationalError)
        async def _handle_sa_operational_error(e):  # type: ignore[override]
            return (
                jsonify({
                    "error": "service_unavailable",
                    "message": "Database is unavailable. Please try again later.",
                    "detail": "operational_error",
                }),
                503,
            )

        @app.errorhandler(asyncpg.PostgresError)
        async def _handle_asyncpg_error(e):  # type: ignore[override]
            return (
                jsonify({
                    "error": "service_unavailable",
                    "message": "Database is unavailable. Please try again later.",
                    "detail": "postgres_error",
                }),
                503,
            )
    except Exception:
        # If imports fail, skip custom handlers
        pass

    return app

