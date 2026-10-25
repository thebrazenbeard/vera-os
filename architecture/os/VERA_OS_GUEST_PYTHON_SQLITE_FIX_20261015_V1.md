# VeraOS resident guest Python sqlite3 dependency, 2026-10-15

## Direct guest evidence

The Buildroot 2025.02.18 resident-browser image built from exact
a2a91017876df7ca1677ad4afefd7b45dd80165f passed two normal QEMU boots.
An additional isolated no-network, disposable-QCOW2 guest diagnostic
executed Python 3.12.14 as PID 1 and attempted resident package imports.
The first import vera_core failed in behavior_effect_verification.py line 6
with ModuleNotFoundError: No module named sqlite3.
The guest then panicked because its diagnostic Python was PID 1.
This does not negate the normal verified VeraOS boots.

Immutable local log:
D:\VeraOS\vm\resident-image-qualification-logs-20261015\guest-import-probe\guest-imports.stdout.log
SHA-256: 8576687926a323d67ec39692474d728662dfa3ea312d037d6f96285624b3d56e

## Exact source and cause

Buildroot 2025.02.18 at commit
d030e36bbc9669230c015be971b14b6e062cfdde declares a separate
BR2_PACKAGE_PYTHON3_SQLITE symbol in package/python3/Config.in, selecting
BR2_PACKAGE_SQLITE. The completed image's resolved .config had the former
explicitly not set while BR2_PACKAGE_SQLITE was enabled.

This branch adds only BR2_PACKAGE_PYTHON3_SQLITE=y to the resident browser
defconfig and adversarial source regression tests. It preserves Cog DRM
and the other core modules.

## Qualification ceiling

SOURCE FIX CANDIDATE ONLY: no updated image compiled, guest imports not
re-qualified, and original source/build/image/boot receipts remain bound
to the unchanged prior build. Rebuild with distinct output, preserve
cache, and rerun guest import before reporting any runtime fix.

No merge, OS installation, partition/EFI or deployed model change.
