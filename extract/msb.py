"""Minimal Nightreign MSB reader: just enemies (NpcParam ids) and treasure events (map item lots)."""
import struct
from nr import dcx


class MSB:
    def __init__(self, path):
        self.b = dcx(path)
        self.sections = {}
        o = 0x10
        while o and o < len(self.b):
            _, cnt = struct.unpack_from("<ii", self.b, o)
            name = self.str(struct.unpack_from("<q", self.b, o + 8)[0])
            offs = struct.unpack_from(f"<{cnt}q", self.b, o + 16)
            self.sections[name] = list(offs[:-1])
            o = offs[-1]

    def str(self, o):
        e = o
        while self.b[e:e + 2] != b"\0\0":
            e += 2
        return self.b[o:e].decode("utf-16le")

    def entries(self, sec):
        """(name, type, offset) for each entry; in-entry offsets are relative to the entry start."""
        for e in self.sections.get(sec, []):
            name = self.str(e + struct.unpack_from("<q", self.b, e)[0])
            _, typ = struct.unpack_from("<ii", self.b, e + 8)
            yield name, typ, e

    def i32(self, o):
        return struct.unpack_from("<i", self.b, o)[0]


def entity(m, e):
    """(entity id, entity group ids, map variation index or -1 for every variation) of the part at e."""
    a = struct.unpack_from("<18i", m.b, e + struct.unpack_from("<q", m.b, e + 0x60)[0])
    return a[0], [g for g in a[7:15] if g > 0], a[17]


def treasures(m):
    """(event name, map item lot, variation) for each treasure event; variation comes from the chest/corpse part."""
    parts = [e for _, _, e in m.entries("PARTS_PARAM_ST")]
    for name, typ, e in m.entries("EVENT_PARAM_ST"):
        if typ == 4:
            td = e + m.i32(e + 0x20)
            pi = m.i32(td + 0x08)
            yield name, m.i32(td + 0x10), entity(m, parts[pi])[2] if 0 <= pi < len(parts) else -1


def enemies(m):
    """(part name, NpcParam id, entity id, group ids, variation) for each enemy / dummy enemy part."""
    for name, typ, e in m.entries("PARTS_PARAM_ST"):
        if typ in (2, 10):
            yield (name, m.i32(e + 0x2BC)) + entity(m, e)


def group_battles(m):
    """(event name, group entity id, reward lot, Cataclysm reward lot) for each group-battle event (type 27).
    Group bosses get their reward picks here instead of from NpcParam."""
    for name, typ, e in m.entries("EVENT_PARAM_ST"):
        if typ == 27:
            group, lot, _, _, chaos = struct.unpack_from("<5i", m.b, e + m.i32(e + 0x20))
            yield name, group, lot, chaos
