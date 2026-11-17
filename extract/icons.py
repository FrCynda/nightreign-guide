"""Pull menu textures (item icons, map icons) out of the game archives into ../data/game/menu."""
import mmap
import os

from Crypto.Cipher import AES

from unpack import ARCHIVES, GAME, OUT, entries, fhash, keys, rsa_open

NAMES = [f"/menu/{n}{q}.{ext}" for n in ("00_solo", "01_common", "02_dlc01", "00_solo_dlc01", "01_common_dlc01")
         for q in ("_h", "") for ext in ("tpfbhd", "tpfbdt", "tpf.dcx", "sblytbnd.dcx")]
NAMES += [f"/menu/71_maptile_m{i:02}.tpf.dcx" for i in range(20)]
NAMES += [f"/menu/{n}_h.{ext}" for n in ("21_common_dlc01", "20_solo_dlc01") for ext in ("tpf.dcx", "sblytbnd.dcx", "tpfbhd", "tpfbdt")]
NAMES += [f"/menu/{n}" for n in ("hi/00_solo.tpfbhd", "hi/00_solo.tpfbdt", "hi/01_common.tpf.dcx", "hi/01_common.sblytbnd.dcx")]


def main():
    names, pems = {fhash(p): p for p in NAMES}, keys()
    for arc in ARCHIVES:
        bhd = rsa_open(os.path.join(GAME, arc + ".bhd"), pems[arc])
        with open(os.path.join(GAME, arc + ".bdt"), "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as bdt:
            for h, foff, padded, unpadded, key, ranges in entries(bhd):
                if h not in names:
                    continue
                buf = bytearray(bdt[foff:foff + padded])
                if key:
                    aes = AES.new(key, AES.MODE_ECB)
                    for s, e in ranges:
                        if s != -1 and e != -1 and s != e:
                            buf[s:e] = aes.decrypt(bytes(buf[s:e]))
                out = os.path.join(OUT, names[h].lstrip("/"))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                open(out, "wb").write(buf[:unpadded] if unpadded > 0 else buf)
                print(arc, names[h], len(buf))


# Page icon -> world-map marker sprite. Fort..Castle, Marsh, Blacksmith Village and both Underground Forts come from the
# game's own map legend (TutorialBody image tags); Small Encampment, Caravan, boss/event kinds are picked by eye.
PLACES = {"Fort": "MAP_07", "Western Underground Fort": "MAP_42045_075", "Eastern Underground Fort": "MAP_42044_074", "Old Sorcerer's Rise": "MenuIcon_42021", "Main Encampment": "MAP_10", "Small Encampment": "MAP_08",
          "Ruins": "MAP_03", "Great Church": "MAP_24", "Church": "MAP_02", "Sorcerer's Rise": "MAP_06", "Castle": "MAP_11",
          "Caravan": "MAP_124", "Marsh": "MAP_42047_077", "Blacksmith Village": "MAP_42048_078", "Township": "MAP_04",
          "Evergaol": "MAP_05", "Field Boss": "MAP_16", "Night Boss": "MAP_28", "Shifting Earth Boss": "MAP_41",
          "Nightlord Arena": "MAP_40",
          "Event": "MAP_175", "Map Event": "MAP_175"}
LOOT = {"Corpse": "MAP_180", "Chest": "MAP_62", "Bow Rack (open world)": "MAP_132", "Shack": "MAP_135", "Statue": "MAP_161"}  # chosen by the user
AFFINITY = {"Holy": "PropertyIcon_40145", "Magic": "PropertyIcon_40146", "Fire": "PropertyIcon_40148",
            "Lightning": "PropertyIcon_40150", "Blood Loss": "RE_bleed", "Frost": "RE_Cold", "Death Blight": "RE_Death",
            "Madness": "RE_Mad", "Scarlet Rot": "RE_Plague", "Poison": "RE_Poison", "Sleep": "RE_Sleep"}
HEROES = {n + 1: f"MenuIcon_{41000 + 10 * n}" for n in range(10)}  # Wylder..Executor, then Scholar/Undertaker (DLC atlas)
# wepType -> the game's white weapon-category glyph (inventory sort icons), matched by eye to the shapes.
TYPE_ICONS = {1: 40050, 3: 40051, 5: 40052, 7: 40061, 9: 40053, 11: 40054, 13: 40073, 14: 40074, 15: 40071, 16: 40072, 17: 40057,
              19: 40058, 21: 40055, 23: 40056, 24: 40076, 25: 40059, 28: 40060, 29: 40077, 31: 40075, 35: 40063, 37: 40079, 39: 40062,
              41: 40078, 51: 40068, 53: 40093, 55: 40094, 56: 40095, 57: 40066, 61: 40067, 65: 40091, 67: 40064, 69: 40065, 87: 40092}
MAPTILES = {"limveld": 0, "Mountaintop": 1, "The Crater": 2, "Rotted Woods": 3, "Great Hollow": 4, "Noklateo": 5}


def export():
    """Write the page's icons to ../app/icons as small webp files."""
    import io
    import json
    import re
    from PIL import Image
    from tex import bnd_entries, tpf
    from nr import dcx
    menu, app = os.path.join(OUT, "menu"), os.path.join(os.path.dirname(__file__), "..", "app")
    atlases, sprite = {}, {}
    for arc in ("01_common_h", "21_common_dlc01_h"):  # base game + DLC atlas (DLC heroes, DLC map markers)
        atlases.update({k: Image.open(io.BytesIO(v)) for k, v in tpf(dcx(os.path.join(menu, arc + ".tpf.dcx"))).items()})
        lay = dcx(os.path.join(menu, arc + ".sblytbnd.dcx"))
        for name, off, size in bnd_entries(lay):
            for m in re.finditer(r'name="MENU_([^"]+)\.png" x="(\d+)" width="(\d+)" y="(\d+)" height="(\d+)"', lay[off:off + size].decode()):
                k, x, w, y, h = m.groups()
                sprite[k] = (name[:-len(".layout")], int(x), int(y), int(x) + int(w), int(y) + int(h))

    def save(key, path, px):
        a, *box = sprite[key]
        im = atlases[a].convert("RGBA").crop(box) if atlases[a].mode != "RGBA" else atlases[a].crop(box)
        im.thumbnail((px, px), Image.LANCZOS)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        im.save(path, "WEBP", quality=88, method=6)

    data = json.loads(open(os.path.join(app, "data.js"), encoding="utf-8").read()[len("window.NR="):-1])
    for icon in {w[2] for w in data["weapons"].values()}:
        save(f"ItemIcon_{icon:05}", os.path.join(app, "icons", "w", f"{icon}.webp"), 96)
    for key in set(PLACES.values()) | set(LOOT.values()):
        save(key, os.path.join(app, "icons", "place", key + ".webp"), 256)  # native size (sprites are ~100-240px)
    for aff, key in AFFINITY.items():
        save(key, os.path.join(app, "icons", "aff", key + ".webp"), 96)
    for hero, key in HEROES.items():
        save(key, os.path.join(app, "icons", "hero", f"{hero}.webp"), 160)
        # Glowing white emblems from the hero tab bar: plain, and on a dark disc for the selected hero.
        save(f"MenuIcon_{41130 + hero - 1}", os.path.join(app, "icons", "emblem", f"{hero}.webp"), 72)
        save(f"MenuIcon_{41120 + hero - 1}", os.path.join(app, "icons", "emblem", f"{hero}on.webp"), 72)
    save("MenuIcon_40421", os.path.join(app, "icons", "ui", "check.webp"), 48)  # the game's glowing checkbox tick
    for t, n in TYPE_ICONS.items():
        save(f"MenuIcon_{n}", os.path.join(app, "icons", "type", f"{t}.webp"), 64)
    def stitch(i):  # 6x6 grid of 256px tiles, row 0 at the bottom; _B1 tiles are an overlay layer
        tiles = tpf(dcx(os.path.join(menu, f"71_maptile_m{i:02}.tpf.dcx")))
        m = Image.new("RGBA", (6 * 256, 6 * 256))
        for k in sorted((k for k in tiles if "_L0_" in k), key=lambda k: k.endswith("_B1")):
            _, _, _, y, x, *_ = k.split("_")
            im = Image.open(io.BytesIO(tiles[k]))
            im.load()
            m.alpha_composite(im.convert("RGBA"), (int(x) * 256, (5 - int(y)) * 256))
        return m

    from PIL import ImageChops
    os.makedirs(os.path.join(app, "icons", "map"), exist_ok=True)
    limveld = stitch(0)
    for key, i in MAPTILES.items():
        m = stitch(i)
        # Frame the cells this Shifting Earth repaints (Limveld: the middle of the map).
        diff = ImageChops.difference(m.convert("RGB"), limveld.convert("RGB")).convert("L").resize((6, 6), Image.BOX)
        cells = [(x, y) for y in range(6) for x in range(6) if i and diff.getpixel((x, y)) > 12] or [(1, 1), (4, 4)]
        x0, y0 = min(c[0] for c in cells), min(c[1] for c in cells)
        x1, y1 = max(c[0] for c in cells) + 1, max(c[1] for c in cells) + 1
        side = max(x1 - x0, y1 - y0, 2)
        left = min(max((x0 + x1 - side) / 2, 0), 6 - side) * 256
        top = min(max((y0 + y1 - side) / 2, 0), 6 - side) * 256
        m = m.crop((int(left), int(top), int(left + side * 256), int(top + side * 256))).resize((480, 480), Image.LANCZOS)
        m.save(os.path.join(app, "icons", "map", key.replace(" ", "_") + ".webp"), "WEBP", quality=80, method=6)
    print("icons ->", os.path.join(app, "icons"))


if __name__ == "__main__":
    import sys
    export() if sys.argv[1:] == ["export"] else main()
