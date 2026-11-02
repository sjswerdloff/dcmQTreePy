"""#85: when the directory fsync after the replace fails, the save is reported as saved and the user is warned.

The file is already written, synced and replaced, so "save failed" would be false; what is not confirmed is that the
rename survives a power loss. Stuart's ruling (3 Nov): saved, with a warning.

Run offscreen (QT_QPA_PLATFORM=offscreen).
"""

from __future__ import annotations

import os
import stat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from pydicom.data import get_testdata_file  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the directory fsync runs on POSIX only")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _loaded(monkeypatch, fired: list[str]) -> M.DCMQtreePy:
    w = M.DCMQtreePy()
    monkeypatch.setattr(
        w, "non_native_warning_message", lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok
    )
    w.populate_tree_widget_from_file(get_testdata_file("CT_small.dcm"))
    w.current_dataset.PatientID = "SAVED-85"
    w.has_edits = True
    return w


def _fail_directory_fsync(monkeypatch) -> list[str]:
    """Make os.fsync raise for a directory descriptor only; file fsyncs still run. Returns what was refused."""
    real_fsync = M.os.fsync
    refused: list[str] = []

    def fsync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            refused.append("dir")
            raise OSError(5, "Input/output error (injected)")
        real_fsync(fd)

    monkeypatch.setattr(M.os, "fsync", fsync)
    return refused


def test_directory_fsync_failure_reports_saved_and_warns(qapp, monkeypatch, tmp_path) -> None:
    fired: list[str] = []
    w = _loaded(monkeypatch, fired)
    refused = _fail_directory_fsync(monkeypatch)
    out = tmp_path / "saved.dcm"
    out.write_bytes(b"PREVIOUS")

    assert w._perform_save(str(out)) is True

    assert refused == ["dir"], "the injected failure never ran"
    assert pydicom.dcmread(out).PatientID == "SAVED-85", "the new bytes are not in place"
    assert fired == ["Saved, not confirmed durable"]
    assert not w.has_edits


def test_save_dataset_to_returns_false_and_shows_nothing(qapp, monkeypatch, tmp_path) -> None:
    """The core reports it; only the save handler shows a dialog (#79)."""
    fired: list[str] = []
    w = _loaded(monkeypatch, fired)
    _fail_directory_fsync(monkeypatch)

    assert w._save_dataset_to(tmp_path / "saved.dcm") is False
    assert fired == []


def test_normal_save_shows_no_warning(qapp, monkeypatch, tmp_path) -> None:
    fired: list[str] = []
    w = _loaded(monkeypatch, fired)
    out = tmp_path / "saved.dcm"

    assert w._perform_save(str(out)) is True

    assert w._save_dataset_to(tmp_path / "again.dcm") is True
    assert pydicom.dcmread(out).PatientID == "SAVED-85"
    assert fired == []
