#!/usr/bin/env python3
"""Buduje stronę: czyta data/raw (z fetch_stats.py) i zapisuje _site/ (web/ + data.json).

Opcjonalne zmienne środowiskowe:
  HIDE_PLAYERS  nicki oddzielone przecinkami, których nie pokazywać na stronie
  MC_VERSION    wersja Minecrafta do polskich nazw bloków i mobów (domyślnie najnowsza)
"""
import json
import re
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "_site")
TOP_N = 15

DISTANCE_KEYS = [
    "walk_one_cm", "sprint_one_cm", "crouch_one_cm", "swim_one_cm", "walk_on_water_one_cm",
    "walk_under_water_one_cm", "climb_one_cm", "fly_one_cm", "aviate_one_cm", "boat_one_cm",
    "horse_one_cm", "minecart_one_cm", "pig_one_cm", "strider_one_cm", "happy_ghast_one_cm",
    "nautilus_one_cm",
]


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def polish_lang():
    """Pobiera oficjalny polski plik językowy Minecrafta (nazwy bloków, mobów). Przy błędzie: pusty."""
    cache = os.path.join(ROOT, "data", "lang_pl.json")
    if os.path.exists(cache):
        return load_json(cache, {})
    try:
        manifest = fetch_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
        want = os.environ.get("MC_VERSION", "").strip() or manifest["latest"]["release"]
        ver = next((v for v in manifest["versions"] if v["id"] == want), None)
        if ver is None:
            ver = next(v for v in manifest["versions"] if v["id"] == manifest["latest"]["release"])
        index = fetch_json(fetch_json(ver["url"])["assetIndex"]["url"])
        h = index["objects"]["minecraft/lang/pl_pl.json"]["hash"]
        lang = fetch_json(f"https://resources.download.minecraft.net/{h[:2]}/{h}")
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(lang, f, ensure_ascii=False)
        print(f"Polskie nazwy z Minecrafta {ver['id']}.")
        return lang
    except Exception as e:
        print(f"Uwaga: nie udało się pobrać polskich nazw ({type(e).__name__}), będą angielskie ID.")
        return {}


def pretty_id(rid):
    path = rid.split(":", 1)[-1]
    return path.replace("_", " ").replace("/", " ").capitalize()


def make_namer(lang):
    def name(rid, kind):
        ns, _, path = rid.partition(":")
        if not path:
            ns, path = "minecraft", rid
        kinds = ["entity"] if kind == "entity" else ["block", "item"]
        for k in kinds:
            val = lang.get(f"{k}.{ns}.{path.replace('/', '.')}")
            if val:
                return val
        return pretty_id(rid)
    return name


def player_names():
    cache = load_json(os.path.join(RAW, "usercache.json"), []) or []
    names, expires = {}, {}
    for e in cache:
        uuid, name = e.get("uuid"), e.get("name")
        if not uuid or not name:
            continue
        names[uuid] = name
        try:  # usercache: expiresOn = ostatnie wejście + 1 miesiąc
            exp = datetime.strptime(e["expiresOn"], "%Y-%m-%d %H:%M:%S %z")
            expires[uuid] = (exp - timedelta(days=30)).astimezone(timezone.utc)
        except (KeyError, ValueError):
            pass
    return names, expires


def top(d, n, namer, kind):
    items = sorted(((k, v) for k, v in d.items() if v > 0), key=lambda kv: -kv[1])[:n]
    return [[namer(k, kind), v] for k, v in items]


def safe_color(c):
    c = str(c or "")
    return c if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", c) else "#F5D90A"


def load_badges(hidden):
    """Odznaki TOP 3 z moda (badges.json). Bez UUID, tylko nicki. Brak pliku = pusta lista."""
    raw = load_json(os.path.join(RAW, "badges.json"), None)
    if not isinstance(raw, dict):
        return []
    out = []
    for c in raw.get("categories", []) or []:
        try:
            top = [{"place": int(t["place"]), "name": str(t["name"]), "display": str(t.get("display", t.get("value", "")))}
                   for t in c.get("top", []) if str(t.get("name", "")).lower() not in hidden][:3]
            out.append({"id": str(c["id"]), "name": str(c.get("name", c["id"])), "symbol": str(c.get("symbol", "★"))[:2],
                        "color": safe_color(c.get("color")), "top": top})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def main():
    stats_dir = os.path.join(RAW, "stats")
    if not os.path.isdir(stats_dir):
        sys.exit("Brak data/raw/stats. Najpierw uruchom fetch_stats.py.")

    hidden = {n.strip().lower() for n in os.environ.get("HIDE_PLAYERS", "").split(",") if n.strip()}
    names, last_login = player_names()
    mtimes = load_json(os.path.join(RAW, "mtimes.json"), {}) or {}
    namer = make_namer(polish_lang())

    players = []
    for fname in sorted(os.listdir(stats_dir)):
        if not fname.endswith(".json"):
            continue
        uuid = fname[:-5]
        name = names.get(uuid, uuid[:8])
        if name.lower() in hidden:
            continue
        raw = load_json(os.path.join(stats_dir, fname), {}) or {}
        s = raw.get("stats", {})
        custom = {k.split(":", 1)[-1]: v for k, v in s.get("minecraft:custom", {}).items()}
        mined = s.get("minecraft:mined", {})
        killed = s.get("minecraft:killed", {})
        killed_by = s.get("minecraft:killed_by", {})
        crafted = s.get("minecraft:crafted", {})
        used = s.get("minecraft:used", {})

        play_ticks = custom.get("play_time", custom.get("play_one_minute", 0))
        if play_ticks <= 0 and not mined and not killed:
            continue  # ktoś wszedł na sekundę

        seen = [d for d in (mtimes.get(uuid), last_login.get(uuid)) if d]
        seen = [datetime.fromisoformat(d) if isinstance(d, str) else d for d in seen]
        last_seen = max(seen).isoformat() if seen else None

        totals = {
            "play_time": round(play_ticks / 20),  # sekundy
            "deaths": custom.get("deaths", 0),
            "mob_kills": custom.get("mob_kills", 0),
            "player_kills": custom.get("player_kills", 0),
            "mined": sum(mined.values()),
            "crafted": sum(crafted.values()),
            "distance": round(sum(custom.get(k, 0) for k in DISTANCE_KEYS) / 100),  # metry
            "jumps": custom.get("jump", 0),
            "diamonds": sum(v for k, v in mined.items() if k.endswith("diamond_ore")),
            "ancient_debris": mined.get("minecraft:ancient_debris", 0),
            "fish": custom.get("fish_caught", 0),
            "trades": custom.get("traded_with_villager", 0),
            "bred": custom.get("animals_bred", 0),
            "enchants": custom.get("enchant_item", 0),
            "sleep": custom.get("sleep_in_bed", 0),
            "chests": custom.get("open_chest", 0),
            "damage_dealt": round(custom.get("damage_dealt", 0) / 20),  # serca
            "damage_taken": round(custom.get("damage_taken", 0) / 20),
            "elytra": round(custom.get("aviate_one_cm", 0) / 100),
            "since_death": round(custom.get("time_since_death", 0) / 20),
        }
        players.append({
            "name": name,
            "last_seen": last_seen,
            "totals": totals,
            "top": {
                "mined": top(mined, TOP_N, namer, "block"),
                "killed": top(killed, TOP_N, namer, "entity"),
                "killed_by": top(killed_by, TOP_N, namer, "entity"),
                "crafted": top(crafted, TOP_N, namer, "item"),
                "used": top(used, TOP_N, namer, "item"),
            },
        })

    data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "players": players,
            "badges": load_badges(hidden)}

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "web"), OUT)
    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Strona gotowa: {len(players)} graczy.")


if __name__ == "__main__":
    main()
