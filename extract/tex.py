"""Menu texture readers: BHF4/BDT pairs (00_solo), TPF (DDS containers), and sblyt sprite layouts."""
import io
import os
import struct

from nr import dcx

MENU = os.path.join(os.path.dirname(__file__), "..", "data", "game", "menu")


def wstr(b, o):
    e = o
    while b[e:e + 2] != bytes(2):
        e += 2
    return b[o:e].decode("utf-16le")


def bnd_entries(b):
    """(name, offset, size) for a BHF4 header or BND4 (both: entries from 0x40, header size at 0x20)."""
    count, hsize = struct.unpack_from("<i", b, 0x0C)[0], struct.unpack_from("<q", b, 0x20)[0]
    for i in range(count):
        size, _, off, _, noff = struct.unpack_from("<qqIiI", b, 0x40 + i * hsize + 8)
        yield wstr(b, noff).replace("\\", "/").split("/")[-1], off, size


def tpf(b):
    """{texture name: dds bytes} from a (decompressed) TPF."""
    assert b[:4] == b"TPF\0"
    count, unicode = struct.unpack_from("<i", b, 8)[0], b[0xE]
    out = {}
    for i in range(count):
        off, size, _, _, _, _, noff = struct.unpack_from("<IiBBBBI", b, 0x10 + i * 0x14)
        if unicode:
            name = wstr(b, noff)
        else:
            name = b[noff:b.index(b"\0", noff)].decode("shift_jis")
        out[name] = b[off:off + size]
    return out


def solo():
    """{texture name: dds bytes} for every icon in 00_solo (one TPF per entry)."""
    bhd = open(os.path.join(MENU, "00_solo_h.tpfbhd"), "rb").read()
    out = {}
    with open(os.path.join(MENU, "00_solo_h.tpfbdt"), "rb") as f:
        for name, off, size in bnd_entries(bhd):
            f.seek(off)
            out.update(tpf(dcx(f.read(size))))
    return out


def png(dds, box=None, size=None):
    from PIL import Image
    im = Image.open(io.BytesIO(dds))
    im.load()
    im = im.convert("RGBA")
    if box:
        im = im.crop(box)
    if size:
        im.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()
