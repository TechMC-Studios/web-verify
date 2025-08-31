from pathlib import Path
from utils.plugins_io import load_plugins
from utils import api_key as api_key_utils
from app.db import get_session
from app.models import Platform, Resource, ResourceShopID, APIKey


def run_seed_and_bootstrap(app):
    db = get_session()
    try:
        # Ensure platforms
        existing = {p.name for p in db.query(Platform).all()}
        for name in ("spigot", "polymart", "bbb"):
            if name not in existing:
                db.add(Platform(name=name))
        db.commit()

        # Ensure resources from data/plugins.json if resources table empty
        if db.query(Resource).count() == 0:
            # load from data/plugins.json
            plugins = load_plugins()
            for slug, item in plugins.items():
                r = Resource(slug=slug, name=item.get("name") or slug)
                db.add(r)
                db.flush()
                shops = item.get("shops", {})
                for shop_name, info in shops.items():
                    # normalize shop names: examples like 'spigotmc' -> 'spigot'
                    normalized = shop_name.replace("mc", "") if shop_name.endswith("mc") else shop_name
                    p = db.query(Platform).filter_by(name=normalized).first()
                    if not p:
                        p = db.query(Platform).filter_by(name=shop_name).first()
                    if not p:
                        continue
                    external_id = str(info.get("resource_id"))
                    db.add(ResourceShopID(resource_id=r.id, platform_id=p.id, external_resource_id=external_id))
            db.commit()

        # Bootstrap API key: if none exists, generate and print once
        if db.query(APIKey).count() == 0:
            kid, plain, stored = api_key_utils.new_api_key_record(length=48)
            # store hash
            ak = APIKey(name="initial", hash=stored, method="pbkdf2_sha256", active=True)
            db.add(ak)
            db.commit()
            # print to stdout so operator can copy it
            print("INITIAL_API_KEY:", plain)

    finally:
        db.close()
