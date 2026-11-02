"""#87: adding an element never replaces one that exists, and a new private creator never adopts orphaned members.

Before, the add wrote straight over an occupied tag (CT_small's 80-byte OB payload became text) and treated a slot with
members but no creator as free, so the new creator took over those members and could overwrite them. Both were silent.

Run offscreen (QT_QPA_PLATFORM=offscreen). The add dialogs are stubbed so the handlers run headless.
"""

from __future__ import annotations

import os
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from pydicom.data import get_testdata_file  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

GEMS_GROUP = 0x0043  # CT_small: creator GEMS_PARM_01 at (0043,0010), OB member at (0043,1028)
TEST_GROUP = 0x0071  # unused by CT_small


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Text:
    def __init__(self, text: str) -> None:
        self._text = text

    def toPlainText(self) -> str:
        return self._text


def _private_dialog(group: int, creator: str, offset: int, text: str):
    class _Dialog:
        def __init__(self, *_a, **_kw) -> None:
            scratch = pydicom.Dataset()
            self.current_private_block = scratch.private_block(group, creator, create=True)
            self.current_private_block.add_new(offset, "LO", None)
            self.current_byte_offset = offset
            self.ui = type("Ui", (), {"text_edit_element_value": _Text(text)})()

        def setProperty(self, *_a) -> None:
            pass

        def exec(self) -> int:
            return 1

    return _Dialog


def _public_dialog(tag: int, vr: str, text: str):
    class _Dialog:
        def __init__(self, *_a, **_kw) -> None:
            self.current_public_element = pydicom.DataElement(tag, vr, None)
            self.ui = type("Ui", (), {"text_edit_element_value": _Text(text)})()

        def setProperty(self, *_a) -> None:
            pass

        def exec(self) -> int:
            return 1

    return _Dialog


def _widget(monkeypatch, path, fired: list[str]) -> M.DCMQtreePy:
    w = M.DCMQtreePy()
    monkeypatch.setattr(
        w, "non_native_warning_message", lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok
    )
    w.populate_tree_widget_from_file(str(path))
    w.dcm_tree_widget.clearSelection()
    return w


def _orphan_file(tmp_path: pathlib.Path) -> pathlib.Path:
    """Another creator at (0071,0010) with a member, and an orphaned member at (0071,1101) with no (0071,0011)."""
    ds = pydicom.dcmread(get_testdata_file("CT_small.dcm"))
    ds.add_new((TEST_GROUP, 0x0010), "LO", "OTHER VENDOR")
    ds.add_new((TEST_GROUP, 0x1001), "LO", "THEIRS")
    ds.add_new((TEST_GROUP, 0x1101), "LO", "ORPHAN")
    path = tmp_path / "orphan.dcm"
    ds.save_as(path)
    return path


def test_private_add_onto_an_occupied_member_is_refused_and_keeps_the_payload(qapp, monkeypatch) -> None:
    """Sourcery's case on CT_small: GEMS_PARM_01's (0043,1028) is an 80-byte OB."""
    fired: list[str] = []
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), fired)
    creator = w.current_dataset[GEMS_GROUP, 0x0010].value
    before = w.current_dataset[GEMS_GROUP, 0x1028].value
    count = len(w.current_dataset)
    monkeypatch.setattr(M, "AddPrivateElementDialog", _private_dialog(GEMS_GROUP, creator, 0x28, "OVERWRITE"))

    w.on_add_private_element()

    assert w.current_dataset[GEMS_GROUP, 0x1028].value == before
    assert w.current_dataset[GEMS_GROUP, 0x1028].VR == "OB"
    assert len(w.current_dataset) == count, "a refused add wrote something"
    assert fired == ["Add refused"]
    assert not w.has_edits


def test_private_add_at_a_free_offset_under_an_existing_creator_still_works(qapp, monkeypatch) -> None:
    """Control: the refusal is limited to an occupied tag."""
    fired: list[str] = []
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), fired)
    creator = w.current_dataset[GEMS_GROUP, 0x0010].value
    assert (GEMS_GROUP, 0x10FE) not in w.current_dataset
    monkeypatch.setattr(M, "AddPrivateElementDialog", _private_dialog(GEMS_GROUP, creator, 0xFE, "ADDED"))

    w.on_add_private_element()

    assert w.current_dataset[GEMS_GROUP, 0x10FE].value == "ADDED"
    assert fired == []
    assert w.has_edits


def test_a_new_creator_does_not_adopt_an_orphaned_block(qapp, monkeypatch, tmp_path) -> None:
    fired: list[str] = []
    w = _widget(monkeypatch, _orphan_file(tmp_path), fired)
    monkeypatch.setattr(M, "AddPrivateElementDialog", _private_dialog(TEST_GROUP, "MINE", 0x01, "MINE-VALUE"))

    w.on_add_private_element()

    ds = w.current_dataset
    assert (TEST_GROUP, 0x0011) not in ds, "the new creator took the orphaned block's slot"
    assert ds[TEST_GROUP, 0x1101].value == "ORPHAN"
    assert ds[TEST_GROUP, 0x1001].value == "THEIRS"
    assert ds[TEST_GROUP, 0x0012].value == "MINE"
    assert ds[TEST_GROUP, 0x1201].value == "MINE-VALUE"
    assert fired == []


def test_public_add_of_an_existing_element_is_refused(qapp, monkeypatch) -> None:
    """The same defect on the public path: Add replaced PatientID silently."""
    fired: list[str] = []
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), fired)
    before = w.current_dataset.PatientID
    monkeypatch.setattr(M, "AddPublicElementDialog", _public_dialog(0x00100020, "LO", "REPLACED"))

    w.on_add_element()

    assert w.current_dataset.PatientID == before
    assert fired == ["Add refused"]
    assert not w.has_edits
