# WPEBackend-FDO 1.14.3 bufferless SHM export boundary

The earlier Cog 0.18.4 image booted with a readable first dashboard
frame but did not refresh status; its subsequent Wayland shared-memory
metadata was corrupt: width -803434736, height 32734, and stride
-803435312 were observed repeatedly. These values resemble dangling
pointer content, not dimensions. The separate Cog 0002 bounds guard
prevented the earlier general protection fault and retained the first
displayed frame.

Source inspection located a plausible cause: in WPEBackend-FDO 1.14.3,
both ImplEGL::surfaceCommit and ImplSHM::surfaceCommit clear
surface.bufferResource but continue exporting surface.shmBuffer when
the next bufferless surface commit arrives. A stale buffer pointer can
then enter Cog's copy path. This patch makes bufferless surface commit
a no-export operation, preserving normal export and release for a
non-null wl_buffer resource. It changes neither upstream package
versions nor package-selection policies.

The source tests, clean Buildroot patch application, and a successful
image build do not establish guest behavior. **Rendering refresh is not qualified**
until live WebKit dashboard status changes are visibly observed on an
actual QEMU framebuffer without memory faults. Do not merge or install.
