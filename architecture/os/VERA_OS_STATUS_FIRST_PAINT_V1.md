# VeraOS truthful first-paint resident status

The latest qualified readable static QEMU dashboard image belongs to
font-bearing source dc39f7ce38d5a334d3951ffc6bf300c4e839c97a under
Draft PR #26. Cog DRM can display HTML/CSS with glyphs, but repeated
later frames have corrupted Wayland SHM metadata; live DOM refresh
was not qualified. Diagnostic WPEBackend-FDO Draft PR #27 at
4038a709d5e3d6c805fac5a8c53eaf240beb70eb did not repair this
and yielded a black framebuffer. That candidate is explicitly on HOLD.

The local-only VeraOS dashboard now renders a status snapshot at page load
from the existing in-process resident status dictionary rather than showing
an indefinite placeholder requiring JavaScript. It HTML-escapes all
dynamic fields, caps the component lists and requires strict true for
capability claims. CSP forbids scripts. It retains the read-only live JSON
endpoint at 127.0.0.1:18765/api/status.

No live browser frame-refresh qualification is claimed. No cognition
route or QualifiedVeraRuntime is activated; conversation remains disabled
and protected-effect authority remains false. An image build is separate
from a QEMU framebuffer proof. Windows disks, EFI, and earlier images remain
untouched. Do not merge source without live authority.
