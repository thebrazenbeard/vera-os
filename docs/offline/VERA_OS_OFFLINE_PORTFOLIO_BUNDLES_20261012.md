# VeraOS local/offline portfolio source layer

This is the **local source-cache layer** for the entire owned GitHub portfolio, not a claim that 90 independent systems can run without internet.

## Captured scope (2026-10-12)

The authenticated owned-repository census records **90** repositories, including **21 private** and **5 archived**; `RSLinux` is the current GitHub name of the formerly inventoried `RSLinux5000000`. The census lives in `architecture/offline/VERA_OS_OWNED_OFFLINE_PORTFOLIO_CENSUS_20261012.json`.

Each captured repository has its own Git bundle containing the local snapshot of its advertised Git refs, plus a receipt binding the current default-branch commit, repository identity, SHA-256, privacy classification and byte count. The capture is **per repository, not an atomic 90-repo commit**. Files under `bundles/`, `receipts/` and `portfolio-snapshot-summary.json` are the immutable local input set; never put the private bundle content into a public GitHub PR, web upload or shared installer.

On Lappy, the October 12 verified snapshot is:

`D:\VeraOS\vm\offline-portfolio-vault-20261012`

The independently rerun readback returned `ALL_REPOSITORIES_BYTES_VERIFIED_SOURCE_ONLY`: 90/90 repositories, 21 private, 5 archived, 601,795,187 total Git bundle bytes. It did **not** exercise all 90 applications.

## Create and verify source archives

For a future capture, with Git credential access already configured and an approved **local private** output directory:

```sh
python tools/offline/Freeze-VeraPortfolio.py --output /private/path/offline-portfolio
python tools/offline/Freeze-VeraPortfolio.py --verify-only --output /private/path/offline-portfolio
```

Capture is resumable, validates previously published receipts, refuses overwrite and fails closed on incorrect identity or altered bytes. It does not save credential values in the receipts. **The first capture requires internet** to GitHub; subsequent verification and Git bundle restores do not. Archival refs do not include GitHub Issues, PR discussion, Wiki contents, LFS payloads, release assets or external dependency caches unless those files were independently committed to Git.

To create a **supplementary filesystem image file** on a Linux build machine:

```sh
python3 tools/offline/Build-VeraOSOfflineVault.py \
  --vault /private/path/offline-portfolio \
  --output /private/path/VeraOS-Offline-Portfolio.ext4
```

This command verifies the full snapshot, creates a new standalone ext4 filesystem image with label `VERAOFFLINE`, and reads all 90 bundles back from the ext4 image through `debugfs` to verify their checksums. It refuses an existing target or receipt. Neither `Freeze` nor `Build` invokes `mount`, `dd`, `parted`, `diskpart`, bootloader installation, host partition mutation, or VM activation.

The image contains 21 private repositories. **Keep it on Patrick-controlled storage** and do not distribute, upload, or treat it as safely portable to unrelated users. A SHA-256 receipt is integrity evidence, not confidentiality or independent review.

## Planned VeraOS consumer boundary

The ext4 output is a *data filesystem*, not a bootable ISO, partitioned disk, live provider, or an automatically mounted volume. After a separately qualified guest boot, an explicitly configured guest can attach it as a secondary read-only disk and mount the correctly identified partition/device at `/opt/veraos/offline-portfolio`. Do not hardcode a physical disk number or automatically mount untrusted media. The device identity, filesystem read-only policy and mounting effect require separate runtime authority.

Once present and verified, a governed on-demand tool can clone a bundle to a workspace using local Git alone, e.g.:

```sh
git clone /opt/veraos/offline-portfolio/bundles/thebrazenbeard--portal-<head12>.bundle /var/lib/vera/projects/portal
```

Only treat an individual project as executable once its native dependencies, target ABI, runtime permissions, providers, and offline tests are satisfied. The preferred continuous runtime identity remains **Vera Mono**; P.O.R.T.A.L., Pre-Active, Volition and the eventual local Vera cognition model occupy separately governed roles. Source archives are never a shortcut around `vera_core.QualifiedVeraRuntime` or effect authority.

## Gaps before “same Vera, offline” can be claimed

- Build and boot the Python >=3.12 **RESIDENT_BROWSER** guest with Vera Mono, P.O.R.T.A.L., Pre-Active and Volition actually packaged; verify imports, services, memory/state and routing in the guest.
- Supply and qualify an actual local GGUF Vera model and a trustworthy KoboldCPP/Pre-Active active-target binding. Cached Docker images alone are **not** model weights or model consumption evidence.
- Cache Python wheels/native shared libraries, JavaScript dependency lockfiles, Go/Rust modules, model weights and optional on-demand specialist binaries **for the exact target architecture**. Git bundles alone do not provide these.
- Replace cloud-only functions (GitHub collaboration, hosted email, external inference, SaaS databases) with deliberately supported local equivalents where possible, or report **UNAVAILABLE_OFFLINE** instead of silently falling back online.
- Implement and qualify a VeraOS human interface for P.O.R.T.A.L. and the governed resident runtime. Including WebKit/Cog in Buildroot doesn't establish a usable browser window.
- Probe physical Lappy hardware, suspend/resume, peripherals, thermal/resource limits, boot recovery, disk encryption and dual-boot safety in a lab before proposing native installation to the reserved **300.39 GB unallocated space**. Do not touch that region without new exact authorization.

> **HOSTILE REVIEWER:** “All 90 bundled” could be misread as “all 90 function offline.”
>
> **Accepted.** Bundle count measures portable **source custody**, not executable integration. Offline availability and behavior must be individually verified; sensitive source must not be published merely because it was fetched into a local volume.

The source and volume build create files in isolated build directories only. They do not merge, deploy, install, change permissions/trust/credentials, or authorize any protected effect.
