"""Item odds for lots and pools, honoring character / discovery-relic rows."""
from collections import defaultdict
from nr import by_id, param

pools = defaultdict(list)
for r in param("ItemTableParam"):
    pools[int(r["id"])].append(r)
LOTS = {"map": by_id("ItemLotParam_map"), "enemy": by_id("ItemLotParam_enemy")}


def ok(r, hero, relic):
    cls, wtd = int(r["onlyForClass"]), int(r["weaponTypeDiscovery"])
    if cls:
        return cls == hero and relic is None
    if 0 <= wtd < 1000:
        return relic == wtd
    return True


def pool(pid, hero=1, relic=None, depth=0):
    """{(category, item id): probability} for one roll of an ItemTableParam pool."""
    rows = [r for r in pools.get(pid, []) if int(r["chanceWeight"]) > 0 and ok(r, hero, relic)]
    tot = sum(int(r["chanceWeight"]) for r in rows)
    out = defaultdict(float)
    if not tot or depth > 8:
        return out
    for r in rows:
        p, cat, iid = int(r["chanceWeight"]) / tot, r["itemCategory"], int(r["itemId"])
        if cat == "7":
            for k, v in pool(iid, hero, relic, depth + 1).items():
                out[k] += p * v
        elif iid > 0:
            out[(cat, iid)] += p
    return out


def lot_row(kind, lid, hero=1, relic=None):
    """{(category, item id): probability} for one ItemLot row (one of its 8 slots is picked)."""
    r = LOTS[kind][lid]
    slots = [(r[f"lotItemCategory0{k}"], int(r[f"lotItemId0{k}"]), int(r[f"lotItemBasePoint0{k}"])) for k in range(1, 9)]
    total = sum(s[2] for s in slots) or 1
    out = defaultdict(float)
    for cat, iid, pts in slots:
        if pts <= 0 or iid <= 0:
            continue
        sub = pool(iid, hero, relic) if cat == "7" else {(cat, iid): 1.0}
        for k, v in sub.items():
            out[k] += pts / total * v
    return out


def lot_chain(kind, lid):
    """A lot id awards itself and every consecutive id after it, like Elden Ring."""
    ids = []
    while lid in LOTS[kind]:
        ids.append(lid)
        lid += 1
    return ids
