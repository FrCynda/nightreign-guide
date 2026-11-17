"""Build ../app/data.js: every weapon source in every map (boss reward picks, kill drops, chests) plus the pool tree.
Re-run after each game patch (after unpack.py and re-unpacking regulation.bin)."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from loot import LOTS, lot_chain, pools
from msb import MSB, enemies, group_battles, treasures
from nr import by_id, text
from variants import scan

OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data.js")
TOOLS = os.path.join(os.path.dirname(__file__), "..", "tools")
MAPS = os.path.join(os.path.dirname(__file__), "..", "data", "game", "map", "mapstudio")  # fresh from unpack.py
HEROES = ["Wylder", "Guardian", "Ironeye", "Duchess", "Raider", "Revenant", "Recluse", "Executor", "Scholar", "Undertaker"]
TYPES = {1: "Dagger", 3: "Straight Sword", 5: "Greatsword", 7: "Colossal Sword", 9: "Curved Sword", 11: "Curved Greatsword",
         13: "Katana", 14: "Twinblade", 15: "Thrusting Sword", 16: "Heavy Thrusting Sword", 17: "Axe", 19: "Greataxe",
         21: "Hammer", 23: "Great Hammer", 24: "Flail", 25: "Spear", 28: "Great Spear", 29: "Halberd", 31: "Reaper",
         35: "Fist", 37: "Claw", 39: "Whip", 41: "Colossal Weapon", 50: "Light Bow", 51: "Bow", 53: "Greatbow",
         55: "Crossbow", 56: "Ballista", 57: "Staff", 61: "Sacred Seal", 65: "Small Shield", 67: "Medium Shield",
         69: "Greatshield", 87: "Torch"}
# Base-game map names: Smithbox's community list (tools/SmithboxMapNames_NR.json, "Kind - bosses"). Its kinds -> ours.
SB_KIND = {"Fort": "Fort", "Camp": "Main Encampment", "Ruins": "Ruins", "Great Church": "Great Church", "Church": "Church",
           "Sorcerer's Rise": "Sorcerer's Rise", "Small Camp": "Small Encampment", "Field Boss": "Field Boss",
           "Basement Boss": "Field Boss", "Evergaol": "Evergaol", "Night Boss": "Night Boss", "Night Horde": "Night Horde",
           "Castle": "Castle", "Event": "Event", "Township": "Township"}
# chaosMatching* = the Deep of Night mode (ChaosMatchingRankControlParam has one row per Depth 1-5, each with a
# cataclysmWeight: Cataclysms only happen there). DLC maps aren't in that list. Marsh/Blacksmith Village confirmed by matching a known drop list exactly; m52_4x/5x
# (named カオス inside) are Great Hollow spots, not Cataclysms: their WorldMapPointParam markers share the Great Hollow's
# grid and depth, and their bosses have separate normal and Deep of Night lots. Each spot has alternate versions
# (m52_50 blood / m52_52 rot+poison at the same marker). Western fort =
# the m53 maps whose own names say 西砦 (west fort) / 研究棟 (research hall, per the in-game description).
PLACES = [("m50_0", "Marsh"), ("m50_1", "Blacksmith Village"), ("m51_05", "Main Encampment"), ("m51_10", "Sorcerer's Rise"),
          ("m51_15", "Caravan"), ("m52_4", "Great Church"), ("m52_5", "Ruins"), ("m53_50", "Eastern Underground Fort"),
          ("m53_67", "Eastern Underground Fort"), ("m53_68", "Eastern Underground Fort"), ("m53_80", "Eastern Underground Fort"),
          ("m53_82", "Eastern Underground Fort"), ("m53_55", "Church"), ("m53_56", "Church"),
          ("m53_51", "Western Underground Fort"), ("m53_62", "Western Underground Fort"), ("m53", "Great Hollow"),
          ("m45_00", "Caravan"), ("m45_01", "Caravan"), ("m1", "Nightlord Arena"), ("m2", "Map Event")]
# m60 tile suffix (first digit) -> Shifting Earth. Mountaintop/Crater by their unique bosses (Borealis, Magma Wyrm);
# Great Hollow ruins with a fixed element (m52_52 = the Curseblade's Poison Ruins, per a player).
FILE_AFF = {"m52_50": "Blood Loss", "m52_52": "Poison"}
# Display names: the game's "X and more" health bars, and models the game gives no name text.
NAME_FIX = {"Crucible Knight and more": "Crucible Knights", "Centipede Demon and more": "Centipede Demon group"}
# Rotted Woods / Noklateo by lot families 6123/6124; 4 = Great Hollow (DLC).
SHIFTING = {"0": "Limveld", "1": "Mountaintop", "2": "The Crater", "3": "Rotted Woods", "4": "Great Hollow", "5": "Noklateo"}
# Boss reward lot family (lot // 1000) -> what kind of boss. Low-Tier / Castle / Shifting Earth match a known list
# and where they spawn; High-Tier and Night 1/2 are inferred from which bosses use them.
TIER = {6100: "Low-tier field boss", 6110: "High-tier field boss", 6120: "Castle boss", 6121: "Shifting Earth boss",
        6122: "Shifting Earth boss", 6123: "Shifting Earth boss", 6124: "Shifting Earth boss", 6200: "Night 1 boss",
        6210: "Night 2 boss"}
# SmallBaseMapVariationParam icon -> affinity; worked out from the bosses that carry each icon.
AFFINITY = {0: "Untyped", 42600: "Magic", 42601: "Fire", 42602: "Lightning", 42603: "Holy", 42604: "Poison",
            42605: "Scarlet Rot", 42606: "Blood Loss", 42607: "Death Blight", 42608: "Frost", 42609: "Sleep",
            42610: "Madness"}
# Invisible reward carriers next to a fallen phantom (c0120); 6300000's fixed picks are Frenzied Flame Seal + Vyke's
# War Spear. These only appear when playing offline, so they're left out.
PHANTOMS = {10000400, 10000410}
CHEST_WORDS = {"宝箱": "Chest", "宝死体": "Corpse", "弓棚": "Bow Rack", "杖机": "Staff Desk", "杖棚": "Staff Rack",
               "聖印棚": "Seal Shelf"}

weapon_name, npc_name = text("WeaponName"), text("NpcName")
wep, npc, variation = by_id("EquipParamWeapon"), by_id("NpcParam"), by_id("SmallBaseMapVariationParam")


def aliases(name):
    return {x["ID"]: x["Name"] for x in json.load(open(os.path.join(TOOLS, name), encoding="utf-8"))}


map_alias = aliases("SmithboxMapNames_NR.json")
er_alias = aliases("SmithboxCharacters_ER.json")
chr_alias = {**er_alias, **{k: er_alias.get(k, v) if "/" in v and " / " not in v else v
                            for k, v in aliases("SmithboxCharacters_NR.json").items()}}


def base(i, table):
    # Rarity/affix variants (e.g. 1030050) aren't their own rows; fall back to the base weapon.
    for b in (i, i // 100 * 100, i // 1000 * 1000, i // 10000 * 10000):
        if b in table:
            return b
    return None


def map_of(fname):
    """Which map a file belongs to: "" = every map (normal Limveld content), else the Shifting Earth it needs."""
    if fname.startswith("m60"):
        return "" if fname[10] == "0" else SHIFTING.get(fname[10], "")
    return "Great Hollow" if fname.startswith(("m53", "m52_4", "m52_5")) else ""


def place(fname, tier):
    """Player-facing place name, e.g. "Ruins", "Open world", "Night Boss"."""
    if fname.startswith("m60"):
        return "Open world"
    sb = map_alias.get(fname[:12], "")
    if sb == "Sorcerer's Rise - Ruined":
        return "Old Sorcerer's Rise"  # the game's map legend name
    if sb.split(" - ")[0] in SB_KIND:
        return SB_KIND[sb.split(" - ")[0]]
    if "Boss Arena" in sb or fname[:3] in ("m18", "m19"):
        return "Nightlord Arena"
    name = next((n for p, n in PLACES if fname.startswith(p)), None)
    # Unlisted boss arenas (m52 DLC sets etc.): name them by what their reward lot says they are.
    return name or {"Night 1 boss": "Night Boss", "Night 2 boss": "Night Boss", "Castle boss": "Castle"}.get(tier, "Field Boss")


def variants(fname, var_ents, names):
    """variation index -> (affinity, boss of that variation, share of visits), for maps that roll a variation."""
    row = variation.get(int(fname[1:3] + fname[4:6])) if not fname.startswith("m60") else None
    if not row:
        return {}
    w = [int(row.get(f"variationValue_{k}", 0)) for k in range(1, 11)]
    out = {}
    for k, wk in enumerate(w):
        if wk:
            boss = next((npc_name[n] for e in var_ents.get(k, []) for n in (names.get(e), names.get(e + 5000))
                         if n in npc_name), "")
            share = f"{wk / sum(w):.0%}" if sum(x > 0 for x in w) > 1 else ""
            out[k] = (AFFINITY.get(int(row.get(f"variationIconId_{k + 1}", 0)), ""), boss, share)
    return out


def who_enemy(npc_id, model, ids, names):
    # Exact boss name from the map's health bar setup (by entity or entity group) when there is one,
    # then the NpcParam's own name (Night invaders), else the community name for the character model.
    for i in ids:
        if names.get(i) in npc_name:
            return npc_name[names[i]]
    if int(npc[npc_id]["nameId"]) in npc_name:
        return npc_name[int(npc[npc_id]["nameId"])]
    # The NpcParam id says which enemy it really is (c7700xxxx = Gaping Dragon); the part's model can be a stand-in,
    # e.g. the Gaping Dragon placed through an ER "Lightning Ball" part, or invisible dummy parts.
    if f"c{npc_id // 10000:04d}" in chr_alias:
        model = f"c{npc_id // 10000:04d}"
    name = chr_alias.get(model, "")
    return "" if name == "Dummy" else name.split(" / ")[-1]  # "Augur / Maris, Fathom of Night" -> the boss's name


def who_chest(jp):
    if "彫像宝箱" in jp:
        return "Statue"  # statue chests in the open world
    if "廃屋" in jp:
        return "Shack"  # abandoned house: its seal shelf and corpse
    kind = next((v for k, v in CHEST_WORDS.items() if k in jp), "Chest")
    tier = "Uncommon" if re.search("アンコモン|ｱﾝｺﾓﾝ|UC", jp) else "Rare" if "レア" in jp else "Common"
    return f"{kind} ({tier})"


weapons, used_pools, used_lots, sources, seen, origins = {}, {}, {}, [], set(), []


def walk(pid, depth=0):
    if pid in used_pools or depth > 8:
        return
    rows = []
    used_pools[pid] = rows
    for r in pools.get(pid, []):
        w, cat, iid = int(r["chanceWeight"]), r["itemCategory"], int(r["itemId"])
        if w <= 0 or iid <= 0:
            continue
        if cat == "7":
            walk(iid, depth + 1)
        elif cat == "6" and base(iid, wep):
            iid = base(iid, wep)
            weapons[iid] = [weapon_name.get(base(iid, weapon_name) or 0, f"Weapon {iid}"), int(wep[iid]["wepType"]), int(wep[iid]["iconId"]), int(wep[iid]["rarity"])]
        else:
            cat = "x"  # non-weapon: still takes up weight in the roll
        rows.append([cat, iid, w, int(r["onlyForClass"]), int(r["weaponTypeDiscovery"])])


def add_lot(kind, lid):
    key = f"{kind[0]}{lid}"
    if key not in used_lots:
        r = LOTS[kind][lid]
        # 4th field: enableLuck, the slot's weight is scaled by Discovery / 100
        slots = [[r[f"lotItemCategory0{k}"], int(r[f"lotItemId0{k}"]), int(r[f"lotItemBasePoint0{k}"]), int(r.get(f"enableLuck0{k}") or 0)] for k in range(1, 9)]
        slots = [s if s[0] in ("6", "7") else ["x", 0, s[2], s[3]] for s in slots if s[2] > 0]
        for cat, iid, _, _ in slots:
            if cat == "7":
                walk(iid)
            elif cat == "6" and base(iid, wep):
                b = base(iid, wep)
                weapons[b] = [weapon_name.get(base(b, weapon_name) or 0, f"Weapon {b}"), int(wep[b]["wepType"]), int(wep[b]["iconId"]), int(wep[b]["rarity"])]
        used_lots[key] = [[c, base(i, wep) if c == "6" else i, p, l] for c, i, p, l in slots]
    return key


def add_source(where, map_, mode, var, tag, who, how, kind, lid):
    """One row per lot in the chain: [place, map, mode, affinity, share of visits, tag, who, how, lot key].
    map: "" = every map, else the Shifting Earth it needs. mode: "both", "normal" or "deep" (Deep of Night)."""
    if not who:  # invisible dummy parts (NpcParam 1000000 etc.): never fought, and their lots hold no weapons
        return
    aff, boss, share = var
    aff = aff or FILE_AFF.get(f[:6], "")
    who = NAME_FIX.get(who, who)
    if who.startswith("Demon Prince/"):  # one model for the Night 1 pair and the Night 2 Demon Prince
        who = "Demon in Pain & Demon from Below" if f.startswith("m52_0") else "Demon Prince"
    tag = boss if boss and how == "Loot" else tag  # chests in a variation: say whose variation it is
    for n, x in enumerate(lot_chain(kind, lid)):
        if who == "Maris' Tendril" and n:
            break  # its chain ends in an unused weapon lot; tendrils never drop weapons (per the user)
        label = f"{how} {n + 1}" if how == "Reward pick" else how
        row = [where, map_, mode, aff, share, tag, who, label, add_lot(kind, x)]
        if tuple(row) not in seen:
            seen.add(tuple(row))
            sources.append(row)
            origins.append(f)  # map file, for NR_AUDIT


NONE = ("", "", "")
for f in sorted(os.listdir(MAPS)):
    if f.startswith("m60") and f[11] != "0":
        continue  # low-detail distant copies of overworld tiles
    m = MSB(os.path.join(MAPS, f))
    var_ents, names = scan(f)
    var = variants(f, var_ents, names)
    models = {i: n[:5] for n, i, *_ in enemies(m)}  # part name starts with the character model, e.g. c4352_9000
    foes = [(i, [ent] + groups, v) for _, i, ent, groups, v in enemies(m)
            if i in npc and i not in PHANTOMS and not (var and v >= 0 and v not in var)]  # skip unused variations (weight 0)
    # Boss arenas get one label for everything in them; overworld tiles mix bosses, so only their rewards get one.
    lots = [int(npc[i]["rewardItemLot_2"]) for i, _, _ in foes] + [lot for _, _, lot, _ in group_battles(m)]
    tiers = [TIER[x // 1000] for x in lots if x // 1000 in TIER]
    arena = tiers[0] if tiers and not f.startswith("m60") else ""
    where, map_ = place(f, arena), map_of(f)
    # Chests and ordinary enemies inside a boss arena: say whose arena, not the boss tier.
    sb = map_alias.get(f[:12], "").split(" - ", 1)
    arena_label = f"{sb[1]} arena" if arena and len(sb) == 2 and ";" not in sb[1] else ""
    for jp, lid, v in treasures(m):
        if lid > 0 and not (var and v >= 0 and v not in var):
            if "魔術師の" in jp:  # the tower's puzzle reward: a 3-choice reward screen like a boss's, not a chest
                add_source(where, map_, "both", NONE, "", "Puzzle Reward", "Reward pick", "map", lid)
            else:
                add_source(where, map_, "both", var.get(v, NONE), arena_label, who_chest(jp), "Loot", "map", lid)

    def reward(i, ids, v, how, lid, mode, red=False):
        tag, here = (how != "Kill drop" and TIER.get(lid // 1000)) or (arena if how != "Kill drop" else arena_label), where
        if f.startswith("m60") and how != "Kill drop":
            # Bosses stand on overworld tiles; name the kind of spot instead of "Open world".
            here = {"Castle boss": "Castle", "Shifting Earth boss": "Shifting Earth Boss"}.get(tag, "Field Boss")
        who = who_enemy(i, models.get(i, ""), ids, names)
        add_source(here, map_, mode, var.get(v, NONE), tag, who and ("Red " + who if red else who), how, "enemy", lid)

    def rewards(i, ids, v, lot, chaos):
        # A boss with a separate Deep of Night reward gives `lot` only in normal expeditions.
        if lot > 0 and lot in LOTS["enemy"]:
            reward(i, ids, v, "Reward pick", lot, "normal" if chaos > 0 and chaos in LOTS["enemy"] else "both")
        if chaos > 0 and chaos in LOTS["enemy"]:
            reward(i, ids, v, "Reward pick", chaos, "deep")

    group_lots = {lot for _, _, lot, _ in group_battles(m)}
    for i, ids, v in foes:
        # An invisible dummy holding a group fight's reward (m34_00 Watchdogs) duplicates the group's own row.
        if not (models.get(i) in ("c0100", "c1000") and int(npc[i]["rewardItemLot_2"]) in group_lots):
            rewards(i, ids, v, int(npc[i]["rewardItemLot_2"]), int(npc[i]["chaosMatchingRewardLotId"]))
        lid = int(npc[i]["itemLotId_enemy"])
        # A visible part posing as another enemy's param (only m47_80's "Lightning Ball" using the Gaping Dragon's) isn't
        # a real kill; dummy parts (c0100/c1000) are fine, they carry real hidden rewards.
        model = models.get(i, "")
        stand_in = model not in ("", "c0100", "c1000") and model != f"c{i // 10000:04d}"
        if lid > 0 and lid in LOTS["enemy"] and not stand_in:
            reward(i, ids, v, "Kill drop", lid, "both")
        red = int(npc[i]["chaosMatchingItemLotId"])
        if red > 0 and red in LOTS["enemy"] and not stand_in:
            reward(i, ids, v, "Kill drop", red, "deep", red=True)
    # Group bosses (several enemies, one health bar): the reward lives on the map's group-battle event.
    for _, group, lot, chaos in group_battles(m):
        members = [(i, ids, v) for i, ids, v in foes if group in ids]
        if not members or any(int(npc[i]["rewardItemLot_2"]) == lot for i, _, _ in members):
            continue  # unused variation, or the members already carry the reward
        i, ids, v = members[0]
        rewards(i, [group] + ids, v, lot, chaos)

# The same overworld spot repeats on every Shifting Earth copy of a tile; if it's on the normal tile it's on every map.
if os.environ.get("NR_AUDIT"):  # every row with the map file it came from
    json.dump([[o] + r for o, r in zip(origins, sources)], open(os.environ["NR_AUDIT"], "w", encoding="utf-8"), ensure_ascii=False)
everywhere = {tuple(r[:1] + r[2:]) for r in sources if not r[1]}
sources = [r for r in sources if not r[1] or tuple(r[:1] + r[2:]) not in everywhere]

data = {"heroes": HEROES, "types": {k: v for k, v in TYPES.items() if any(w[1] == k for w in weapons.values())},
        "weapons": weapons, "pools": used_pools, "lots": used_lots, "sources": sources}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("window.NR=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
print({k: len(v) for k, v in data.items()}, f"{os.path.getsize(OUT) / 1e6:.1f} MB")
