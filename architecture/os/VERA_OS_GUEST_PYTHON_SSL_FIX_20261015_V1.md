# Resident VeraOS Python HTTPS fix - 2026-10-15

## Guest evidence and root cause

The isolated, no-network QEMU import probe against the new SQLite-capable VeraOS image found that vera_core loads further but fails in ingest/adapters/http.py when importing HTTPSConnection from http.client. In Buildroot 2025.02.18, that class is unavailable when Python ssl is omitted. The resolved .config had BR2_PACKAGE_PYTHON3_SSL unset although OpenSSL was packaged.

Buildroot package/python3/Config.in declares BR2_PACKAGE_PYTHON3_SSL, selects OpenSSL, and documents that the Python _ssl module is required for HTTPS support.

## Smallest source change

Add BR2_PACKAGE_PYTHON3_SSL=y to the resident browser defconfig, preserving BR2_PACKAGE_PYTHON3_SQLITE=y and Cog DRM-only settings. The missing-option regression test was observed failing first, then passed. This source fix is not evidence of a qualified new image, successful guest imports, secure HTTPS connections, or running Vera services.

The previous Docker-built SQLite image and guest stdout logs remain separate evidence. Future tests must bind new artifacts to this exact source head and not infer runtime qualification from successful source tests.