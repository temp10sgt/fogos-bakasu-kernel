#!/usr/bin/env python3
"""Bandingkan CRC symbol di __versions setiap .ko ROM dengan Module.symvers hasil build."""
import glob, os, struct, sys

SYMVERS = sys.argv[1] if len(sys.argv) > 1 else "Module.symvers"
MODDIR = sys.argv[2] if len(sys.argv) > 2 else "rommods"

def load_symvers(path):
    d = {}
    with open(path, "r", errors="replace") as f:
        for line in f:
            p = line.split("\t")
            if len(p) < 3:
                continue
            try:
                crc = int(p[0], 16)
            except ValueError:
                continue
            d[p[1]] = crc
    return d

def versions_of(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF":
        return None
    is64 = data[4] == 2
    if not is64:
        return None
    e_shoff = struct.unpack_from("<Q", data, 0x28)[0]
    e_shentsize = struct.unpack_from("<H", data, 0x3A)[0]
    e_shnum = struct.unpack_from("<H", data, 0x3C)[0]
    e_shstrndx = struct.unpack_from("<H", data, 0x3E)[0]
    secs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        name, stype, flags, addr, offset, size, link, info, align, entsize = struct.unpack_from("<IIQQQQIIQQ", data, off)
        secs.append((name, stype, offset, size, link, entsize))
    strtab_off = secs[e_shstrndx][2]
    def sname(n):
        end = data.index(b"\0", strtab_off + n)
        return data[strtab_off + n:end].decode("latin1")
    out = {}
    for name, stype, offset, size, link, entsize in secs:
        if sname(name) == "__versions":
            step = 64
            for o in range(offset, offset + size, step):
                crc = struct.unpack_from("<Q", data, o)[0]
                nm = data[o + 8:o + 8 + 56].split(b"\0")[0].decode("latin1")
                if nm:
                    out[nm] = crc
    return out

def main():
    sym = load_symvers(SYMVERS)
    print(f"Module.symvers: {len(sym)} symbol diekspor")
    total = mism = missing = checked = 0
    bad_mods = {}
    for ko in sorted(glob.glob(os.path.join(MODDIR, "*.ko"))):
        vers = versions_of(ko)
        if not vers:
            print(f"  ! {os.path.basename(ko)}: tidak bisa dibaca")
            continue
        for nm, crc in vers.items():
            checked += 1
            if nm not in sym:
                missing += 1
                bad_mods.setdefault(os.path.basename(ko), []).append(f"MISSING {nm}")
            elif sym[nm] != crc:
                mism += 1
                bad_mods.setdefault(os.path.basename(ko), []).append(
                    f"CRC {nm}: modul=0x{crc:08x} kernel=0x{sym[nm]:08x}")
    print(f"Symbol dicek: {checked}")
    print(f"CRC cocok   : {checked - mism - missing}")
    print(f"CRC beda    : {mism}")
    print(f"Tidak ada   : {missing}")
    if bad_mods:
        print("\n=== MODUL BERMASALAH ===")
        for m, items in bad_mods.items():
            print(f"{m}: {len(items)} masalah")
            for it in items[:5]:
                print("   ", it)
    else:
        print("\nSEMUA modul ROM kompatibel dengan kernel hasil build.")

if __name__ == "__main__":
    main()
