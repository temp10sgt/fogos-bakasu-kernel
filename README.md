# fogos-bakasu-kernel

Build recipe for a **BakaSU + SUSFS** kernel on the **Motorola Moto G45 5G (`fogos`)**.

The device ships a non-GKI kernel (5.4.302), so KernelSU cannot be loaded as a
module — the driver has to be compiled into the kernel and the boot image has to
be rebuilt. This repository automates that with GitHub Actions.

## Device

| | |
|---|---|
| Model | Motorola Moto G45 5G, `fogos` (XT2363-9) |
| SoC | Qualcomm SM6375 / holi |
| Kernel | 5.4.302, **non-GKI** |
| Partitions | A/B (`boot_a`, `boot_b`) |
| ROM used for the config | PixelOS 17.0, build 2026-11-18 |
| Bootloader | must be unlocked |

## What gets built

| Component | Source |
|---|---|
| Kernel | `moto-fogos/android_kernel_motorola_sm6375` @ `d526d46d` |
| Root driver | BakaSU (KernelSU manual hook + driver) |
| Root hiding | SUSFS v2.3.0 |
| Toolchain | AOSP clang 22.0.2 (`clang-r596125`) |

`patches/` contains the three patches applied on top of the base commit, so the
build does not depend on any external commit URL.

## Hard requirements

These are not optional. Changing any of them produces a kernel that boots but
cannot load the vendor modules (`camera.ko`, `wlan.ko`, …).

1. **`kernelrelease` must be exactly `5.4.302-WKCW/d526d46d`.**
   Achieved with `CONFIG_LOCALVERSION="-WKCW"` plus `.scmversion` containing
   `/d526d46d`. Module `vermagic` and symbol CRCs depend on it.
2. **`CONFIG_LTO_CLANG`, `CONFIG_CFI_CLANG`, `CONFIG_CFI_CLANG_SHADOW`,
   `CONFIG_MODVERSIONS`, `CONFIG_SHADOW_CALL_STACK` must be enabled.**
   The resulting `Image` must contain `__cfi_slowpath`.
3. **Use the same compiler as the ROM** (clang 22.0.2 / r596125).
4. **Every `make` invocation needs `LLVM=1 LLVM_IAS=1`.** Without it
   `olddefconfig` silently falls back to the host gcc and drops LTO/CFI.

The workflow enforces all four and fails the build if anything is missing.

## Building

1. Fork this repository.
2. Enable Actions on your fork (Actions tab → *I understand my workflows, go ahead*).
3. Run **Build BakaSU + SUSFS kernel (fogos)** → *Run workflow*.

Inputs:

| Input | Default | Meaning |
|---|---|---|
| `mode` | `patch` | `patch` = base commit + local patches, `branch` = upstream `lineage-24.0-bakasu` |
| `susfs` | `true` | build SUSFS support |
| `localversion` | `/d526d46d` | localversion suffix, keep it unless your ROM differs |

A build takes roughly 45 minutes.

## Outputs

```
WakacaW-bakasu-fogos.zip   AnyKernel3 package (flash with Kernel Flasher)
Image                      raw kernel
config.txt                 final .config
Module.symvers             exported symbols + CRCs
```

## Installing

### Option A — AnyKernel3 zip

Flash `WakacaW-bakasu-fogos.zip` with an on-device kernel flasher such as
Kernel Flasher. The zip patches the **currently active** boot slot, so keep a
working image of the other slot as a fallback.

### Option B — repack your own boot.img

This is the safer route and the only one that works from fastboot.

1. Extract the stock `boot.img` from your ROM package.
   For an OTA zip, `boot.img` lives inside `payload.bin`
   (use `payload-dumper-go -p boot`).
2. Repack it with the freshly built kernel:

   ```bash
   python3 tools/repack_boot.py --base boot.img --kernel Image --out boot_bakasu.img
   ```

   The script keeps the original ramdisk, header and partition size, and
   rewrites the AVB footer offsets.

3. Flash to the **inactive** slot:

   ```bash
   fastboot getvar current-slot
   fastboot flash boot_a boot_bakasu.img   # use boot_b if current slot is a
   fastboot --set-active=a
   fastboot reboot
   ```

   Do **not** use `fastboot flash boot` without a suffix: on A/B devices that
   writes to the active slot and removes your fallback.

4. To roll back, switch slots again — no reflash needed:

   ```bash
   fastboot --set-active=b
   fastboot reboot
   ```

## Verifying a build

```bash
uname -v                                  # build timestamp of your Image
su -c 'cat /proc/version'
su -c 'lsmod | wc -l'                     # vendor modules must load
su -c '/data/adb/ksu/bin/ksud susfs show version'          # v2.3.0
su -c '/data/adb/ksu/bin/ksud susfs show enabled_features'
```

`grep susfs /proc/kallsyms` returns nothing on purpose:
`CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS=y` hides the symbols.

Module compatibility can be checked offline:

```bash
python3 scripts/crcaudit.py Module.symvers /path/to/modules
```

It compares every `__versions` entry of the `.ko` files against the CRCs in
`Module.symvers`. A mismatch means the module will refuse to load.

## Notes

- **AVB is not re-signed.** The vbmeta blob inside the boot image is copied from
  the stock image, so its hash still describes the old kernel. This is harmless
  on an unlocked bootloader (`verifiedbootstate=orange`), which skips
  verification, but it means the image will not boot on a locked device.
- **`mm/pgsize_migration.c` warning.** The vendor code creates a VMA that is
  entirely padding in `split_pad_vma()` case 1, while `vma_pad_pages()` asserts
  that at least one data page exists. Every `/proc/<pid>/maps` read by
  `CachedAppOptimizer` then prints a `WARN`. The workflow relaxes the check to
  `WARN_ON_ONCE(nr_pad > nr_pages)`, which also makes `vma_data_pages()`
  return 0 so fault-around is correctly skipped inside the padding area.
- **Artifacts expire.** GitHub keeps workflow artifacts for 90 days. If you need
  a long-lived copy, attach the zip to a release.

## Credits

- [KernelSU](https://github.com/tiann/KernelSU) — kernel-based root
- [BakaSU](https://bakasu.org) — KernelSU fork with manual hook support
- [SUSFS](https://gitlab.com/simonpunk/susfs4ksu) by simonpunk — root hiding
- [AnyKernel3](https://github.com/heybyben/AnyKernel3-hey) — flashable zip template
- [moto-fogos](https://github.com/moto-fogos) — kernel source and device trees

## Disclaimer

Flashing a custom kernel can brick your device or wipe your data. Unlock the
bootloader, keep a copy of the stock boot image, and know how to restore it
before you start. Use at your own risk.
