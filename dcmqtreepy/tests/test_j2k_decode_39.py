"""Signed JPEG 2000 decodes (Refs #39).

pydicom 2.4.5 tries Pillow first for JPEG 2000, and Pillow's handler fails on signed
images under numpy 2 with an int16 OverflowError. With pylibjpeg-openjpeg declared,
pydicom falls back to it. These tests go through ``pixel_array``, the same path
dcm_mini_viewer uses, so they exercise the fallback rather than a chosen handler.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom
import pytest

from dcmqtreepy.selftest import check_signed_j2k_decode

TEST_FILES = Path(pydicom.__file__).parent / "data" / "test_files"


def test_signed_j2k_made_in_memory_decodes_equal() -> None:
    """Contract: a signed image with negative values survives J2K lossless exactly."""
    assert check_signed_j2k_decode() is None


@pytest.mark.parametrize("name", ["JPEG2000.dcm", "693_J2KI.dcm"])
def test_bundled_signed_j2k_files_decode_with_negative_values(name: str) -> None:
    """Contract: real signed J2K files decode, and keep their sign (both hold negative pixels)."""
    ds = pydicom.dcmread(TEST_FILES / name)
    assert ds.PixelRepresentation == 1, "fixture: expected a signed image"
    arr = ds.pixel_array
    assert arr.dtype == np.int16
    assert (arr < 0).any(), "signed image decoded with no negative values"


def test_lossless_j2k_equals_its_uncompressed_original() -> None:
    """Contract: MR_small's J2K lossless copy decodes to exactly MR_small's pixels."""
    original = pydicom.dcmread(TEST_FILES / "MR_small.dcm").pixel_array
    decoded = pydicom.dcmread(TEST_FILES / "MR_small_jp2klossless.dcm").pixel_array
    assert np.array_equal(decoded, original)
