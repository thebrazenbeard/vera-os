# Resident browser font-data dependency

The QEMU/VirtIO GPU browser image from source d1167546b136ccab607406b218051ae68e2867d8
rendered the VeraOS dashboard framebuffer layout: backgrounds, panels and borders appeared
on an actual 1280x800 frame. The screenshot was visually inspected.
No TTF fonts were packaged in the root filesystem despite Fontconfig, FreeType
and HarfBuzz being enabled. Consequently WebKit had no glyphs available
and the dashboard showed no readable text.

The resident-browser Buildroot defconfig now includes DejaVu Sans TTF
with nonessential DejaVu font families disabled. This change is specific
to the browser-capable image, not a requirement of the minimal core boot.

An image build must verify that at least one DejaVuSans TTF file exists
inside the root filesystem. A QEMU frame must then show legible text;
without that visual readback, **rendering is not qualified**.
No host OS installation, main merge or protected-effect authority.
