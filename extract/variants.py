"""What a map's event script says about its variations and bosses."""
import os
import struct
from nr import dcx

EVENTS = os.path.join(os.path.dirname(__file__), "..", "data", "game", "event")  # fresh from unpack.py


def ints(path):
    b = dcx(path)
    return struct.unpack_from(f"<{len(b) // 4}i", b)


def scan(fname):
    """{variation index: [entity]}, {entity: health bar NpcName id} for one map's emevd.
    ponytail: pattern-matches common-event calls in the raw ints instead of parsing EMEVD; enough for these 3 events."""
    p = os.path.join(EVENTS, fname[:12] + ".emevd.dcx")
    try:
        a = ints(p)
    except (OSError, AssertionError):
        return {}, {}
    var, names = {}, {}
    for i, x in enumerate(a[:-9]):
        if x == 90085700 and a[i + 1] == 701:  # enable entity when map variation == arg
            var.setdefault(a[i + 3], []).append(a[i + 4])
        elif x == 90015007:  # boss health bar: (slot, entity, region, radius, name)
            names[a[i + 2]] = a[i + 5]
        elif x == 90015002:  # boss fight setup: (.., entity, bar entity, .., .., .., name)
            names.setdefault(a[i + 3], a[i + 8])
            names.setdefault(a[i + 4], a[i + 8])
    return var, names
