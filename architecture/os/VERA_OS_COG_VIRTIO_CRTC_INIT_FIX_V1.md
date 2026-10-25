# VeraOS Cog 0.18.4 virtio display cold-boot compatibility

Observed only in an isolated QEMU guest, with a virtual GPU and no networking:
Cog enumerated DRM primary /dev/dri/card0, discovered a connected connector,
and selected preferred mode 1280x800, but rejected the encoder with
no crtc for encoder found! and then Failed to initialize DRM.

The pinned upstream Cog 0.18.4 helper find_crtc_for_encoder requires an
already assigned encoder->crtc_id, even though a new VirtIO display may have
crtc_id == 0 until the first mode set. This patch permits the first CRTC
within encoder->possible_crtcs only when no CRTC has been assigned. It does
not override a different established CRTC mapping.

Buildroot applies this version-specific patch from the source-bound
BR2_GLOBAL_PATCH_DIR to the Cog source at the next clean package build.
An existing compiled Cog 0.18.4 binary does not pick up this change until
Cog is rebuilt and a new image is generated.

**Rendering is not qualified** merely because the patch applies, compiles,
the OS boots or Cog launches. Require live guest DRM rendering and observed
VNC framebuffer evidence. No host disk/EFI/partition changes or main merge.
