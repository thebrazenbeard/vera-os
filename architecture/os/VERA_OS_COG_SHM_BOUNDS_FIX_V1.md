# Cog 0.18.4 shared-memory row-bounds guard

Guest evidence from source 6d33a30d60263b91f89ff67c64f339a6b9be7260:
Cog loaded the local VeraOS URL but its DRM renderer crashed with a general
protection fault at drm_copy_shm_buffer_into_bo+0x104; ELF relative PC
0xc0f4 faulted reading a byte from the Wayland shared-memory source. A second
test with GLES rendering segfaulted at address 0. QEMU VNC captured a black
display showing "Display output is not active", not a successful desktop.

This patch validates positive source dimensions, source stride, target GBM
dimensions and target stride; a valid input is copied one bounded row at a
time. Invalid metadata is dropped with a warning. A valid size still does
not prove that external Wayland SHM backing actually contains that many bytes.

**Rendering is not qualified** without a real framebuffer output that
contains the local dashboard and a running browser with no crash.
Source tests and successful compilation are weaker evidence.
No private OS install, source merge or protected authority.
