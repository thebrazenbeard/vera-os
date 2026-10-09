# Native Linux VeraOS image build and QEMU qualification

These scripts are a Docker-free alternative to the Windows/Docker wrappers on Draft PR #2. They do not install VeraOS, repartition the host, merge branches, or grant protected-effect authority.

Prerequisites: a Linux build host with Buildroot dependencies (see `tools/vm/buildroot-builder.Dockerfile`), sufficient free disk space for the Buildroot toolchain and output, and QEMU system/x86_64 plus qemu-img for qualification.

From a **clean** VeraOS checkout of this branch:

```sh
bash tools/vm/Build-VeraOSNative.sh "$PWD" /path/out/veraos CORE_BOOT 4
bash tools/vm/Test-VeraOSNative.sh "$PWD" /path/out/veraos /path/out/logs 300
```

To build the larger WPE WebKit + Cog browser-capable image, substitute `BROWSER` for `CORE_BOOT`. Browser package inclusion is **not** evidence of browser runtime functionality. Core boot qualification checks two QEMU boots and a lifecycle-persistence marker, not GUI or canonical memory.

The native builder pins Buildroot 2024.02.4 to exact commit `e0a2687421a4f93e65aa00a30bcb0b4817f7a195`, refuses dirty source, and emits `veraos-build-result.json`. The native QEMU qualifier validates hashes and source commit before booting, uses a temporary copy-on-write overlay, disables guest networking, checks both boot markers, and emits `veraos-vm-qualification.json`. Its timeout runs for each boot even after markers appear; adjust it to suit the host. The temporary overlay is removed on exit.

**Evidence ceiling:** source implementation only until the native path has been run on an actual Linux build host and its receipts/logs inspected. The existing PR #2 Docker-based CORE_BOOT qualification is separate evidence and must not be represented as qualification of this native path.

Run source guard tests on Linux:

```sh
python3 -m unittest tools/vm/test_native_builder.py -v
```


## Package a VirtualBox boot disk (VDI)

A built kernel and root filesystem are **not** directly bootable as a VirtualBox installation disk. The standalone packager creates a GPT disk with a FAT32 EFI partition (GRUB x86_64 EFI plus the kernel) and an ext4 filesystem partition containing the original VeraOS rootfs. It converts that raw disk to a dynamically allocated VDI. Run it from a Linux host with `grub-mkstandalone`, `mkfs.fat`, `mmd`, `mcopy`, and `qemu-img` available. The packager does not install packages or modify host partitions.

```sh
python3 tools/vm/Pack-VeraOSVirtualBox.py /path/to/exact-clean-build-source /path/to/existing-artifacts /path/to/veraos.vdi
```

**Important:** The source directory passed to the packager must be a clean Git checkout at the **exact commit recorded in the build receipt**, not necessarily the commit containing the packager itself. Keep packaged images and their `.receipt.json` files outside both source and original build-artifact directories. The tool refuses output overwrites and records SHA-256 hashes.

For a host where Linux reports an IO-APIC timer panic under VirtualBox's Windows Hypervisor Platform (NEM) backend, `--virtualbox-noapic` adds the Linux `noapic` boot parameter to GRUB. This is opt-in and may reduce hardware/interrupt compatibility; do not silently enable it for other hosts.

**Observed VirtualBox qualification:** A CORE_BOOT disk made from source commit `fa9eb3999a2301f5c617d15869d29e37dd3c3f24` booted under VirtualBox 7.2.14 on Windows with UEFI, 1 virtual CPU, 2048 MiB RAM, isolated SATA disk, no guest networking, and the explicit `noapic` workaround. GRUB loaded Linux 6.6.69, which mounted its ext4 rootfs and started `/sbin/vera-init`. Two boots yielded `boot_ordinal=1` and then `boot_ordinal=2 previous_boot_ordinal=1`; both emitted `VERAOS_BOOT_READY_V1`. See `architecture/os/VERA_OS_VIRTUALBOX_QUALIFICATION_20261008.json` for hashes and claim boundaries. This is **not** independent review, generic-platform qualification, browser-runtime qualification, installation, or activation of Vera Mono.

Keep the pristine packaged VDI unchanged; attach a disposable **clone** to a test VM. A boot test modifies the clone's root filesystem. For this qualification, the VM was powered off after testing and host partition tables were not changed.

Run the corresponding packaging tests with `python3 tools/vm/test_virtualbox_packager.py`. Synthetic/mocked tests are distinct from observed guest-boot evidence.
