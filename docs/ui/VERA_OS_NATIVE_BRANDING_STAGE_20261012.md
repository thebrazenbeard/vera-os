# VeraOS native desktop artwork — local opt-in stage

Status: **prepared source-level implementation, not installed or rendered**.

The Lappy originals are under Patrick's OneDrive Pictures folder and are not committed to GitHub. The inspected October 12 source set includes:

- `VERA_PC.png` — 1920×1080 landscape, burgundy/rose background with Vera symbol toward the lower right; primary VeraOS desktop-wallpaper choice.
- `VERA_phone_landscape.png` — 1920×1080 alternative background for companion screens.
- `VERA_phone_portrait.png` — 1080×1920, intended for a mobile companion, **not** the desktop image.
- `vera small icon.png` — 255×256 RGBA logo; preferred launcher source.
- `VERA_icon.png` — 1254×1254 RGB artwork, with visible checkerboard-style corners; retained as reference, not the preferred raster launcher.
- `VERA_icon_small.png` and `VERA_icon_tiny.png` — existing small variants, not used by the stage because it generates consistent sizes from the preferred source.
- `VERA_FACE_CANON.png` — portrait reference, **optional** in the UI, excluded by default.

## Stage locally on Lappy

The stage utility needs Pillow (`python -m pip install Pillow` only if absent); it is **not** needed by the image build to verify a completed stage.

```powershell
python tools/ui/Stage-VeraOSBranding.py --create `
    --source-dir "C:\Users\patri\OneDrive\Pictures" `
    --output "D:\VeraOS\vm\local-branding-stage-20261012"
python tools/ui/Stage-VeraOSBranding.py --verify-stage "D:\VeraOS\vm\local-branding-stage-20261012"
```

By default this produces a 1920×1080 desktop wallpaper JPEG and 256/128/64/32 PNG launcher icons, with exact source/asset SHA-256 and dimensions bound by `branding-receipt.json`. It refuses existing output and does not modify the user originals. `--include-avatar` is an explicitly optional **local** build choice; no portrait is copied unless chosen.

For a future **isolated** BROWSER/RESIDENT_BROWSER Buildroot image, the PowerShell build entrypoint accepts:

```powershell
-DesktopAssetStage "D:\VeraOS\vm\local-branding-stage-20261012"
```

The builder binds the stage **read-only** at `/branding`; the Buildroot post-build hook checks hashes and installs only the expected files under `/usr/share/veraos/branding/` and a receipt at `/etc/veraos/architecture/VERA_OS_LOCAL_BRANDING_BUILD_RECEIPT_V1.json`. The resulting build receipt records source receipt digest and retains `DesktopAssetsRenderedQualified=false`.

**Nothing in this change starts a desktop compositor, changes user wallpaper, installs the OS, uploads private photos, or proves Cog/WebKit/P.O.R.T.A.L. rendered anything.** An actual guest compositor and P.O.R.T.A.L. user interface must read these paths to make the artwork visible; that is a separate implementation and live test.

## Privacy / provenance boundaries

Keep all originals, generated stages and any resulting branded OS image containing them **on Patrick-controlled hardware**. Never upload private raster assets, avatar portraits or stages into public repositories, CI artifacts, screenshots or support bundles by default. This source branch contains only the tooling, manifest format, documentation and synthetic tests.

**Hostile review:** Simply embedding the wallpaper in `/usr/share` does not put it on the screen. This objection is accepted; this work is a reproducible asset-package step, not UI completion or proof of runtime selection.
