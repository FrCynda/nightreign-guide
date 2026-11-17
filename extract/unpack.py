"""Pull map + event files straight out of the game's encrypted archives (data0-3.bdt, dlc01.bdt) into ../data/game.
Archive keys: tools/SmithboxArchiveKeys.cs (from vawser/Smithbox, MIT). Format: Elden Ring BHD5.
File names are only stored as hashes, so we hash every name we can think of and keep the matches."""
import base64
import mmap
import os
import re
import struct
import sys

from Crypto.Cipher import AES

sys.path.insert(0, os.path.dirname(__file__))
from nr import GAME

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "game")
ARCHIVES = ["data0", "data1", "data2", "data3", "dlc01"]


def keys():
    src = open(os.path.join(ROOT, "tools", "SmithboxArchiveKeys.cs"), encoding="utf-8-sig").read()
    block = src[src.index("NightreignKeys"):]
    return {k: v for k, v in re.findall(r'\["([^"]+)"\]\s*=\s*@"-----BEGIN RSA PUBLIC KEY-----(.*?)-----END', block, re.S)}


def der_ints(der):
    """n, e from a PKCS#1 RSAPublicKey (SEQUENCE { INTEGER n, INTEGER e })."""
    def tlv(b, o):
        t, ln = b[o], b[o + 1]
        o += 2
        if ln & 0x80:
            k = ln & 0x7F
            ln, o = int.from_bytes(b[o:o + k], "big"), o + k
        return t, b[o:o + ln], o + ln
    _, seq, _ = tlv(der, 0)
    _, n, o = tlv(seq, 0)
    _, e, _ = tlv(seq, o)
    return int.from_bytes(n, "big"), int.from_bytes(e, "big")


def rsa_open(path, pem):
    """Raw RSA 'decrypt' with the public key, block by block (what BouncyCastle RsaEngine does)."""
    n, e = der_ints(base64.b64decode("".join(pem.split())))
    ib = (n.bit_length() + 7) // 8
    ob = (n.bit_length() - 1) // 8
    data = open(path, "rb").read()
    return b"".join(pow(int.from_bytes(data[i:i + ib], "big"), e, n).to_bytes(ob, "big") for i in range(0, len(data), ib))


def entries(bhd):
    """(name hash, offset, padded size, unpadded size, aes key, ranges) for every file in a decrypted BHD5."""
    assert bhd[:4] == b"BHD5", "bad key or format"
    buckets, boff = struct.unpack_from("<ii", bhd, 0x10)
    for b in range(buckets):
        cnt, off = struct.unpack_from("<ii", bhd, boff + b * 8)
        for i in range(cnt):
            h, padded, unpadded, foff, _, aoff = struct.unpack_from("<QiiqqQ", bhd, off + i * 0x28)
            key, ranges = None, []
            if aoff:
                key = bhd[aoff:aoff + 16]
                rc = struct.unpack_from("<i", bhd, aoff + 16)[0]
                ranges = [struct.unpack_from("<qq", bhd, aoff + 20 + r * 16) for r in range(rc)]
            yield h, foff, padded, unpadded, key, ranges


def fhash(path):
    h = 0
    for c in path.lower():
        h = (h * 0x85 + ord(c)) & 0xFFFFFFFFFFFFFFFF
    return h


def candidates():
    """Every map/event file name worth trying. ponytail: brute-forces id ranges; widen them if a new area appears."""
    ids = {f"m{a:02}_{b:02}_00_00" for a in range(10, 70) for b in range(100)}
    ids |= {f"m{a:02}_{x:02}_{y:02}_{s:02}" for a in (60, 61) for x in range(0, 60) for y in range(0, 60)
            for s in (0, 10, 20, 30, 40, 50, 60, 70, 80, 90)}
    ids |= {f"m{a:02}_{b:02}_{c:02}_00" for a in range(10, 70) for b in range(100) for c in range(1, 20)}
    names = {}
    for i in ids:
        for p in (f"/map/mapstudio/{i}.msb.dcx", f"/event/{i}.emevd.dcx"):
            names[fhash(p)] = p
    for p in ["/event/common.emevd.dcx", "/event/common_func.emevd.dcx"] + [
            f"/msg/engus/{k}{d}.msgbnd.dcx" for k in ("item", "menu") for d in ("", "_dlc01", "_dlc02")]:
        names[fhash(p)] = p
    return names


def main():
    names, pems, found = candidates(), keys(), 0
    for arc in ARCHIVES:
        bhd = rsa_open(os.path.join(GAME, arc + ".bhd"), pems[arc])
        with open(os.path.join(GAME, arc + ".bdt"), "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as bdt:
            total = hit = 0
            for h, foff, padded, unpadded, key, ranges in entries(bhd):
                total += 1
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
                hit += 1
        found += hit
        print(f"{arc}: {hit} map/event/text files of {total} total")
    assert found, "nothing matched"


if __name__ == "__main__":
    main()
