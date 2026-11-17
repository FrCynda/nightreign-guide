"""Loaders for WitchyBND-serialized Nightreign params and text."""
import os
import xml.etree.ElementTree as ET
from functools import lru_cache

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


@lru_cache(None)
def param(name):
    """Rows of a param as a list of dicts; missing fields fall back to the paramdef default."""
    root = ET.parse(os.path.join(RAW, "regulation-bin", name + ".param.xml")).getroot()
    defaults = {f.get("name"): f.get("defaultValue") for f in root.iter("field")}
    rows = []
    for r in root.iter("row"):
        d = dict(defaults)
        d.update(r.attrib)
        rows.append(d)
    return rows


@lru_cache(None)
def by_id(name):
    """id -> first row (ids repeat in table params; use param() for those)."""
    out = {}
    for r in param(name):
        out.setdefault(int(r["id"]), r)
    return out


@lru_cache(None)
def text(name):
    """FMG id -> text, skipping empty entries: base text (WitchyBND XML) plus the DLC/patch text from unpack.py."""
    out = {}
    for arc in ("item-msgbnd-dcx", "menu-msgbnd-dcx"):
        p = os.path.join(RAW, arc, name + ".fmg.xml")
        if os.path.exists(p):
            out = {int(t.get("id")): t.text for t in ET.parse(p).getroot().iter("text")
                   if t.text and t.text != "%null%"}
            break
    for k, v in dlc_text().get(name.lower(), {}).items():
        if v and v != "%null%":
            out[k] = v
    if not out:
        raise FileNotFoundError(name)
    return out


@lru_cache(None)
def dlc_text():
    """{fmg base name: {id: text}} from data/game/msg/engus/*_dlc*.msgbnd.dcx (BND4 of ER-style FMGs)."""
    import glob
    import struct
    found = {}
    for path in glob.glob(os.path.join(os.path.dirname(__file__), "..", "data", "game", "msg", "engus", "*_dlc*.msgbnd.dcx")):
        b = dcx(path)
        assert b[:4] == b"BND4"
        count, hsize = struct.unpack_from("<iq", b, 0x0C)[0], struct.unpack_from("<q", b, 0x20)[0]
        for i in range(count):
            o = 0x40 + i * hsize  # flags, -1, compressed size, uncompressed size, data offset, id, name offset
            size, _, doff, _, noff = struct.unpack_from("<qqIiI", b, o + 8)
            e = noff
            while b[e:e + 2] != bytes(2):
                e += 2
            fname = b[noff:e].decode("utf-16le").replace("\\", "/").split("/")[-1]
            fmg = b[doff:doff + size]
            groups, strings = struct.unpack_from("<ii", fmg, 0x0C)
            soff = struct.unpack_from("<q", fmg, 0x18)[0]
            texts = {}
            for g in range(groups):
                idx, first, last = struct.unpack_from("<iii", fmg, 0x28 + g * 16)
                for k in range(last - first + 1):
                    so = struct.unpack_from("<q", fmg, soff + (idx + k) * 8)[0]
                    if so:
                        e = so
                        while fmg[e:e + 2] != bytes(2):
                            e += 2
                        texts[first + k] = fmg[so:e].decode("utf-16le")
            base = fname.rsplit(".", 1)[0].lower()
            for suffix in ("_dlc01", "_dlc02"):
                base = base.replace(suffix, "")
            found.setdefault(base, {}).update(texts)
    return found


GAME = r"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game"


def dcx(path):
    """Decompress a DCX_KRAK file with the game's own Oodle DLL (copied into tools/)."""
    import ctypes
    import struct
    data = path if isinstance(path, bytes) else open(path, "rb").read()
    assert data[:4] == b"DCX\0" and data[0x28:0x2C] == b"KRAK", "only DCX_KRAK supported"
    size, csize = struct.unpack(">II", data[0x1C:0x24])
    lib = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), "..", "tools", "oo2core_9_win64.dll"))
    out = ctypes.create_string_buffer(size)
    n = lib.OodleLZ_Decompress(data[0x4C:0x4C + csize], ctypes.c_size_t(csize), out, ctypes.c_size_t(size),
                               0, 0, 0, None, 0, None, None, None, 0, 3)
    assert n == size, f"Oodle returned {n}, expected {size}"
    return out.raw
