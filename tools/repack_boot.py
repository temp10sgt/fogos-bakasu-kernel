#!/usr/bin/env python3
"""Repack Android boot image (header v3) dengan kernel baru.

Dipakai di CI karena magiskboot dari APK Magisk adalah binary bionic yang
tidak bisa dieksekusi di runner Ubuntu.

Struktur yang ditangani (sesuai boot.img fogos):
  [header 1580 + padding ke 4096]
  [kernel][padding]
  [ramdisk][padding]
  [vbmeta][zeros ...][AVB footer 64 byte]

Contoh:
  python3 repack_boot.py --base boot_a.img --kernel Image --out boot_bakasu.img
"""
import argparse
import struct
import sys

PAGE = 4096
AVB_MAGIC = b"AVBf"


def align(n, a=PAGE):
    return (n + a - 1) // a * a


def parse_header(d):
    if d[:8] != b"ANDROID!":
        sys.exit("bukan boot image Android")
    (kernel_size, ramdisk_size, os_version, header_size,
     r0, r1, r2, r3, header_version) = struct.unpack_from("<9I", d, 8)
    if header_version != 3:
        sys.exit(f"header_version {header_version} tidak didukung (butuh 3)")
    return {
        "kernel_size": kernel_size,
        "ramdisk_size": ramdisk_size,
        "os_version": os_version,
        "header_size": header_size,
        "header_version": header_version,
    }


def parse_avb(d):
    t = d[-64:]
    if t[:4] != AVB_MAGIC:
        return None
    magic, maj, mi, orig, vb_off, vb_size = struct.unpack_from(">4sIIQQQ", t, 0)
    return {"major": maj, "minor": mi, "orig_size": orig,
            "vbmeta_offset": vb_off, "vbmeta_size": vb_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="boot.img stok")
    ap.add_argument("--kernel", required=True, help="Image hasil build")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    d = open(a.base, "rb").read()
    h = parse_header(d)
    kernel = open(a.kernel, "rb").read()
    if not kernel:
        sys.exit("kernel kosong")

    k_off = PAGE
    r_off = PAGE + align(h["kernel_size"])
    ramdisk = d[r_off:r_off + h["ramdisk_size"]]
    if len(ramdisk) != h["ramdisk_size"]:
        sys.exit("ramdisk terpotong")

    # header: salin apa adanya, ganti kernel_size
    header = bytearray(d[:PAGE])
    struct.pack_into("<I", header, 8, len(kernel))

    out = bytearray()
    out += header
    out += kernel
    out += b"\x00" * (align(len(out)) - len(out))
    out += ramdisk
    out += b"\x00" * (align(len(out)) - len(out))
    payload_end = len(out)

    avb = parse_avb(d)
    if avb:
        vbmeta = d[avb["vbmeta_offset"]:avb["vbmeta_offset"] + avb["vbmeta_size"]]
        if len(vbmeta) != avb["vbmeta_size"]:
            sys.exit("vbmeta terpotong")
        out += vbmeta

    total = len(d)  # pertahankan ukuran partisi
    if len(out) + 64 > total:
        sys.exit(f"hasil ({len(out)} byte) melebihi ukuran partisi ({total})")
    out += b"\x00" * (total - 64 - len(out))

    if avb:
        footer = struct.pack(">4sIIQQQ", AVB_MAGIC, avb["major"], avb["minor"],
                             payload_end, payload_end, avb["vbmeta_size"])
        footer += b"\x00" * (64 - len(footer))
        out += footer
    else:
        out += b"\x00" * (total - len(out))

    assert len(out) == total, (len(out), total)
    open(a.out, "wb").write(out)
    print(f"OK: {a.out} ({total} byte)")
    print(f"    kernel_size   {len(kernel)}")
    print(f"    ramdisk_size  {len(ramdisk)}")
    print(f"    payload_end   {payload_end}")
    print(f"    vbmeta        {avb['vbmeta_size'] if avb else 0} byte")


if __name__ == "__main__":
    main()
