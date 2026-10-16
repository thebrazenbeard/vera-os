# Cog / Wayland SHM user-data ownership fix

## Observed failure
Pinned Cog 0.18.4 on VirtIO DRM in QEMU loads the VeraOS local
dashboard and sometimes renders a static first frame. Later shared
memory frame metadata becomes impossible, yielding pointer-shaped
negative width/stride, leading to a previous general-protection
fault or the subsequent defensive guards dropping frames. PR27/PR28
diagnostic alternatives were held after black-frame regression.

## Exact source fault
Wayland 1.23.1 wl_shm_buffer_get(resource) obtains the SHM instance
via wl_resource_get_user_data(resource). Cog's
drm_create_buffer_for_shm_buffer (and drm_create_buffer_for_bo)
replaced the very same resource's user data with its renderer pointer.
Next Wayland lookup then interprets a renderer allocation as a
struct wl_shm_buffer, producing corrupt width, height, format and
stride. The Cog destruction listener also overwrote Wayland's user
data with NULL before normal Wayland buffer destruction.

## Narrow repair
Add an owner field to Cog's private buffer_object; store its
renderer there. Remove all three wl_resource_set_user_data calls
from Cog's DRM modeset renderer, and have the destruction listener
read buffer->owner. This leaves Wayland's own SHM resource user data
unchanged, supports regular GBM resource ownership and preserves
existing destroy event cleanup. No WPEBackend-FDO patch is selected;
PR27/PR28 remained on HOLD.

Build/host tests and patch application only prove a source candidate.
Rendering is not qualified until a new source-bound guest boots,
Cog paints readable HTML, and repeated live status changes are
observed in QEMU framebuffer without SHM warnings or crashes. No
physical OS install or protected-effect authority.
