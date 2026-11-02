"""#69: saving through a symlink must update the file it points to and leave the link in place.

`os.replace(tmp, link)` replaces the link itself, so before the fix the link became a regular file holding the
edit and the target kept its old bytes; anyone opening the target never saw the edit.

Run offscreen (QT_QPA_PLATFORM=offscreen).
"""

from __future__ import annotations

import os
import pathlib
import shutil
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from pydicom.data import get_testdata_file  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

PATIENT_ID = pydicom.tag.Tag(0x00100020)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.skipif(os.name != "posix", reason="symlinks need privileges on Windows")
def test_save_through_symlink_updates_target_and_keeps_link(qapp, monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as td:
        real_dir = pathlib.Path(td) / "real"
        link_dir = pathlib.Path(td) / "links"
        real_dir.mkdir()
        link_dir.mkdir()
        target = real_dir / "ct.dcm"
        shutil.copyfile(get_testdata_file("CT_small.dcm"), target)
        link = link_dir / "ct-link.dcm"
        link.symlink_to(target)

        w = M.DCMQtreePy()
        monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
        w.populate_tree_widget_from_file(str(link))
        w.current_dataset[PATIENT_ID].value = "SAVED-THROUGH-LINK"
        assert w._perform_save(str(link)) is True

        assert link.is_symlink(), "the save replaced the symlink with a regular file"
        assert link.resolve() == target.resolve()
        assert pydicom.dcmread(target)[PATIENT_ID].value == "SAVED-THROUGH-LINK", "the target did not receive the save"
        assert not list(link_dir.glob("*.tmp")) and not list(real_dir.glob("*.tmp")), "a temp file was left behind"
