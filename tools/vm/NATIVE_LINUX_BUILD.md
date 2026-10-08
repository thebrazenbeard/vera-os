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
