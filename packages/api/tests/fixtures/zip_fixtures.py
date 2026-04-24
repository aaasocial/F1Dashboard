"""Programmatic zip fixture builders for security and happy-path upload tests.

All functions return ``bytes`` produced in-memory — no filesystem writes.
Consumed by Plan 03 (/sessions) security tests and Wave 0 stubs.
"""
from __future__ import annotations

import io
import zipfile


def make_valid_zip() -> bytes:
    """Build a FastF1-cache-shaped zip with a tiny dummy pickle inside.

    Structure:
        2023/2023-03-05_Bahrain_Grand_Prix/Race/
            lap_data.pkl  (~2 KB dummy content)

    Returns:
        bytes of a valid ZIP archive (~2 KB).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Mimic FastF1 cache directory layout
        zf.writestr(
            "2023/2023-03-05_Bahrain_Grand_Prix/Race/lap_data.pkl",
            b"\x80\x04\x95\x10\x00\x00\x00\x00\x00\x00\x00]\x8c\x04test\x85.",
        )
    return buf.getvalue()


def make_zip_slip() -> bytes:
    """Build a zip with a path-traversal member name (zip slip attack).

    The member name is ``'../../../etc/passwd_pwned'`` — a literal path traversal
    attempt. Plan 03 security tests verify the upload endpoint rejects this.

    Returns:
        bytes of a ZIP archive containing one malicious member.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        info = zipfile.ZipInfo("../../../etc/passwd_pwned")
        zf.writestr(info, b"root:x:0:0:root:/root:/bin/bash\n")
    return buf.getvalue()


def make_decompression_bomb() -> bytes:
    """Build a zip with a declared uncompressed size exceeding 500 MB.

    The actual payload is a small repeated byte sequence; the ``file_size``
    field in the central directory is patched in the raw bytes to read
    600_000_000 bytes. The upload endpoint must read ``ZipInfo.file_size``
    from ``ZipFile.infolist()`` BEFORE extraction and reject this.

    Implementation note: ``zipfile.writestr`` overwrites ``ZipInfo.file_size``
    with the actual data length after compression. We therefore write the zip
    normally (with a tiny payload), read it back to find the central-directory
    record, and patch the 4-byte uncompressed-size field (offset +24 in the
    central directory header, struct ``<HHHHHHIIIHHHHHII``).

    Returns:
        bytes of a ZIP archive with a fraudulent file_size header (600 MB declared).
    """
    import struct

    FAKE_SIZE = 600_000_000
    PAYLOAD = b"A" * 256  # small actual payload

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.pkl", PAYLOAD)
    raw = bytearray(buf.getvalue())

    # Locate the central directory signature: PK\x01\x02 (b'\x50\x4b\x01\x02')
    cd_sig = b"PK\x01\x02"
    idx = raw.find(cd_sig)
    if idx == -1:
        # Fallback: return raw (test will notice file_size is wrong)
        return bytes(raw)

    # Central directory fixed record layout (30 bytes before filename):
    # Offset from record start:
    #   0: signature (4)
    #   4: version made by (2)
    #   6: version needed (2)
    #   8: flags (2)
    #  10: compression method (2)
    #  12: mod time (2)
    #  14: mod date (2)
    #  16: crc32 (4)
    #  20: compressed size (4)
    #  24: uncompressed size (4)  ← patch this
    #  28: filename length (2)
    struct.pack_into("<I", raw, idx + 24, FAKE_SIZE)

    # Also patch the local file header at offset 0 (PK\x03\x04):
    # Local header layout:
    #   0: signature (4)
    #   4: version needed (2)
    #   6: flags (2)
    #   8: compression (2)
    #  10: mod time (2)
    #  12: mod date (2)
    #  14: crc32 (4)
    #  18: compressed size (4)
    #  22: uncompressed size (4)  ← patch this
    lh_sig = b"PK\x03\x04"
    lh_idx = raw.find(lh_sig)
    if lh_idx != -1:
        struct.pack_into("<I", raw, lh_idx + 22, FAKE_SIZE)

    return bytes(raw)


def make_symlink_zip() -> bytes:
    """Build a zip with a member whose external_attr encodes POSIX symlink bits.

    POSIX file mode 0o120000 (S_IFLNK) is encoded in the upper 16 bits of
    ``ZipInfo.external_attr``. The upload endpoint must reject members where
    ``(info.external_attr >> 16) & 0o170000 == 0o120000``.

    Returns:
        bytes of a ZIP archive containing one symlink member.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        info = zipfile.ZipInfo("symlink_target")
        # Set POSIX symlink type bits in external_attr
        info.external_attr = 0o120000 << 16
        zf.writestr(info, b"/etc/passwd")
    return buf.getvalue()


def make_non_zip() -> bytes:
    """Return plain bytes that are not a valid ZIP archive.

    Used to test content-type / magic-byte rejection before any extraction
    attempt.

    Returns:
        bytes of plain text (not a ZIP).
    """
    return b"not a zip file, plain bytes"


__all__ = [
    "make_valid_zip",
    "make_zip_slip",
    "make_decompression_bomb",
    "make_symlink_zip",
    "make_non_zip",
]
