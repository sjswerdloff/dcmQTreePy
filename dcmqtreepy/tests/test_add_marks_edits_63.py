"""#63: adding an element with no tree row selected must mark the file as edited.

Without that, a file switch shows no "Current Tree Has Edits" warning and the addition is discarded silently.
The element also has to appear in the tree, under the root row, since that is the dataset it went into.

Run offscreen (QT_QPA_PLATFORM=offscreen). The add dialogs are stubbed so the handlers run headless.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from pydicom.data import get_testdata_file  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

DESCRIPTION = pydicom.tag.Tag(0x0008103E)  # SeriesDescription: absent from CT_small (StudyDescription is present)
PRIVATE_GROUP = 0x0071  # not used by CT_small, so nothing existing is overwritten
PRIVATE_CREATOR = "TRIAGE 63"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Text:
    def __init__(self, text: str) -> None:
        self._text = text

    def toPlainText(self) -> str:
        return self._text


class _Ui:
    def __init__(self, text: str) -> None:
        self.text_edit_element_value = _Text(text)


class _FakeAddDialog:
    """Stands in for AddPublicElementDialog: offers StudyDescription with a value."""

    def __init__(self, *_a, **_kw) -> None:
        self.current_public_element = pydicom.DataElement(DESCRIPTION, "LO", None)
        self.ui = _Ui("TRIAGE ADD")

    def setProperty(self, *_a) -> None:
        pass

    def exec(self) -> int:
        return 1


class _FakeAddPrivateDialog:
    """Stands in for AddPrivateElementDialog: a scratch private block with one LO member at offset 0x01."""

    def __init__(self, *_a, **_kw) -> None:
        scratch = pydicom.Dataset()
        self.current_private_block = scratch.private_block(PRIVATE_GROUP, PRIVATE_CREATOR, create=True)
        self.current_private_block.add_new(0x01, "LO", None)
        self.current_byte_offset = 0x01
        self.ui = _Ui("PRIVATE ADD")

    def setProperty(self, *_a) -> None:
        pass

    def exec(self) -> int:
        return 1


def _loaded_widget(monkeypatch) -> M.DCMQtreePy:
    w = M.DCMQtreePy()
    monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
    w.populate_tree_widget_from_file(get_testdata_file("CT_small.dcm"))
    w.dcm_tree_widget.clearSelection()
    assert not w.dcm_tree_widget.selectedItems()
    assert not w.has_edits
    return w


def _root_child_tags(w: M.DCMQtreePy) -> list[str]:
    top = w.dcm_tree_widget.topLevelItem(0)
    return [top.child(i).text(0) for i in range(top.childCount())]


def test_public_add_with_no_selection_marks_edits_and_shows_the_row(qapp, monkeypatch) -> None:
    w = _loaded_widget(monkeypatch)
    monkeypatch.setattr(M, "AddPublicElementDialog", _FakeAddDialog)

    w.on_add_element()

    assert w.current_dataset[DESCRIPTION].value == "TRIAGE ADD"
    assert w.has_edits, "addition with no selection not marked as an edit"
    assert str(DESCRIPTION) in _root_child_tags(w), "added element not shown under the root row"


def test_private_add_with_no_selection_marks_edits_and_shows_creator_and_member(qapp, monkeypatch) -> None:
    w = _loaded_widget(monkeypatch)
    monkeypatch.setattr(M, "AddPrivateElementDialog", _FakeAddPrivateDialog)

    w.on_add_private_element()

    member = pydicom.tag.Tag(PRIVATE_GROUP, 0x1001)
    assert w.current_dataset[member].value == "PRIVATE ADD"
    assert w.has_edits, "private addition with no selection not marked as an edit"
    shown = _root_child_tags(w)
    assert str(pydicom.tag.Tag(PRIVATE_GROUP, 0x0010)) in shown, "private creator not shown under the root row"
    assert str(member) in shown, "private member not shown under the root row"


def test_public_add_with_a_row_selected_still_marks_edits(qapp, monkeypatch) -> None:
    """The selected-row path keeps working: the row goes beside the selected element, and the edit is marked."""
    w = _loaded_widget(monkeypatch)
    top = w.dcm_tree_widget.topLevelItem(0)
    w.dcm_tree_widget.setCurrentItem(top.child(0))
    monkeypatch.setattr(M, "AddPublicElementDialog", _FakeAddDialog)

    w.on_add_element()

    assert w.has_edits
    assert str(DESCRIPTION) in _root_child_tags(w)


def test_private_add_with_no_selection_then_save_writes_creator_and_member(qapp, monkeypatch, tmp_path) -> None:
    """Cora's case: the creator must be in the dataset, not only in the tree, or the save is refused."""
    w = _loaded_widget(monkeypatch)
    monkeypatch.setattr(M, "AddPrivateElementDialog", _FakeAddPrivateDialog)

    w.on_add_private_element()
    out = tmp_path / "saved.dcm"
    w._save_dataset_to(out)

    assert not w._pending_errors
    saved = pydicom.dcmread(out)
    assert saved[PRIVATE_GROUP, 0x0010].value == PRIVATE_CREATOR
    assert saved[PRIVATE_GROUP, 0x1001].value == "PRIVATE ADD"


def test_private_add_into_a_group_whose_first_slot_is_taken_uses_the_next_slot(qapp, monkeypatch, tmp_path) -> None:
    """Another creator already holds (0071,0010): the new block goes to slot 0x11, never under the other creator."""
    ds = pydicom.dcmread(get_testdata_file("CT_small.dcm"))
    ds.add_new((PRIVATE_GROUP, 0x0010), "LO", "OTHER VENDOR")
    ds.add_new((PRIVATE_GROUP, 0x1001), "LO", "THEIRS")
    src = tmp_path / "src.dcm"
    ds.save_as(src)
    w = M.DCMQtreePy()
    monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
    w.populate_tree_widget_from_file(str(src))
    w.dcm_tree_widget.clearSelection()
    monkeypatch.setattr(M, "AddPrivateElementDialog", _FakeAddPrivateDialog)

    w.on_add_private_element()
    out = tmp_path / "saved.dcm"
    w._save_dataset_to(out)

    saved = pydicom.dcmread(out)
    assert saved[PRIVATE_GROUP, 0x1001].value == "THEIRS", "the other creator's member was overwritten"
    assert saved[PRIVATE_GROUP, 0x0011].value == PRIVATE_CREATOR
    assert saved[PRIVATE_GROUP, 0x1101].value == "PRIVATE ADD"
    shown = _root_child_tags(w)
    assert str(pydicom.tag.Tag(PRIVATE_GROUP, 0x0011)) in shown
    assert str(pydicom.tag.Tag(PRIVATE_GROUP, 0x1101)) in shown


def test_private_creator_slot_reuses_finds_free_and_refuses_when_full() -> None:
    ds = pydicom.Dataset()
    ds.add_new((PRIVATE_GROUP, 0x0010), "LO", "OTHER VENDOR")
    assert M.DCMQtreePy._private_creator_slot(ds, PRIVATE_GROUP, "OTHER VENDOR") == 0x10
    before = len(ds)
    assert M.DCMQtreePy._private_creator_slot(ds, PRIVATE_GROUP, PRIVATE_CREATOR) == 0x11
    assert len(ds) == before, "finding a slot must not write anything (#87)"
    # members with no creator still occupy their slot (#87)
    ds.add_new((PRIVATE_GROUP, 0x1101), "LO", "ORPHAN")
    assert M.DCMQtreePy._private_creator_slot(ds, PRIVATE_GROUP, PRIVATE_CREATOR) == 0x12
    for slot in range(0x12, 0x100):
        ds.add_new((PRIVATE_GROUP, slot), "LO", f"FILLER {slot:02X}")
    before = len(ds)
    assert M.DCMQtreePy._private_creator_slot(ds, PRIVATE_GROUP, "NO ROOM") is None
    assert len(ds) == before, "a refused allocation must not write anything"
