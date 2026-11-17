"""Minimal EMEVD reader (Elden Ring / Nightreign 64-bit layout)."""
import struct
from nr import dcx


def read(path):
    """{event id: {"instr": [(bank, id, args bytes)], "params": [(instr idx, target byte, source byte, length)]}}"""
    b = dcx(path)
    h = struct.unpack_from("<14q", b, 0x10)
    ev_n, ev_o, params_o, args_o = h[0], h[1], h[9], h[13]
    events = {}
    for i in range(ev_n):
        eid, in_n, in_o, p_n, p_o = struct.unpack_from("<5q", b, ev_o + i * 0x30)
        instr = []
        for j in range(in_n):
            bank, iid, alen, aoff = struct.unpack_from("<iiqq", b, in_o + j * 0x20)
            instr.append((bank, iid, b[args_o + aoff:args_o + aoff + alen] if alen else b""))
        params = [struct.unpack_from("<qqqi", b, params_o + p_o + k * 0x20) for k in range(p_n)]
        events[eid] = {"instr": instr, "params": params}
    return events


def calls(events):
    """(event id, parameter bytes) for every InitializeEvent (2000:0) / InitializeCommonEvent (2000:6)."""
    for e in events.values():
        for bank, iid, a in e["instr"]:
            if bank == 2000 and iid in (0, 6) and len(a) >= 8:
                yield struct.unpack_from("<i", a, 4)[0], a[8:]


def resolved(events, eid, k, caller_args):
    """Instruction k of event eid with its parameters substituted from one caller's arguments."""
    a = bytearray(events[eid]["instr"][k][2])
    for idx, target, source, length in events[eid]["params"]:
        if idx == k and source + length <= len(caller_args):
            a[target:target + length] = caller_args[source:source + length]
    return bytes(a)
