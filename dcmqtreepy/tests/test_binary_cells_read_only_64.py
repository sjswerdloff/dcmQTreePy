"""#64: a binary value cell is not editable, and a change to one leaves the payload alone.

The value cell's text used to be written over the element, so typing into an OB cell replaced its bytes with a str
and the save went through cleanly.

Run offscreen (QT_QPA_PLATFORM=offscreen).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from pydicom.data import get_testdata_file  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

OB_TAG = "(0043, 1028)"  # OB in CT_small, 80 bytes
NAME_TAG = "(0010, 0010)"
UN_TAG = pydicom.tag.Tag(0x00711001)
UN_BYTES = b"\x01\x02\x00\xff\x5c\x10"  # includes a NUL, 0xFF and a backslash


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _rows(item):
    for i in range(item.childCount()):
        c = item.child(i)
        yield c
        yield from _rows(c)


def _row(w, tag_string: str):
    return next(r for r in _rows(w.dcm_tree_widget.topLevelItem(0)) if r.text(0) == tag_string)


def _widget(monkeypatch, path: str, fired: list[str]) -> M.DCMQtreePy:
    w = M.DCMQtreePy()
    monkeypatch.setattr(
        w, "non_native_warning_message", lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok
    )
    w.populate_tree_widget_from_file(path)
    return w


def test_edit_of_an_ob_cell_keeps_the_payload_and_is_refused(qapp, monkeypatch, tmp_path) -> None:
    """Cora's reproduction, plus the save."""
    fired: list[str] = []
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), fired)
    before = w.current_dataset[0x00431028].value
    assert isinstance(before, bytes) and len(before) == 80

    row = _row(w, OB_TAG)
    row.setText(2, "typed text")

    assert w.current_dataset[0x00431028].value == before
    assert row.text(2) == "", "the cell was not put back"
    assert fired == ["Edit refused"]
    assert not w.has_edits
    assert not w._pending_errors
    out = tmp_path / "o.dcm"
    w._save_dataset_to(out)
    assert pydicom.dcmread(out)[0x00431028].value == before


def test_edit_of_an_un_cell_keeps_the_payload(qapp, monkeypatch, tmp_path) -> None:
    """UN is shown as text, so it is the binary cell a user is most likely to type into."""
    ds = pydicom.dcmread(get_testdata_file("CT_small.dcm"))
    ds.add_new(UN_TAG, "UN", UN_BYTES)
    src = tmp_path / "un.dcm"
    ds.save_as(src)
    fired: list[str] = []
    w = _widget(monkeypatch, str(src), fired)
    assert w.current_dataset[UN_TAG].VR == "UN"

    _row(w, str(UN_TAG)).setText(2, "typed text")

    assert w.current_dataset[UN_TAG].value == UN_BYTES
    assert fired == ["Edit refused"]
    assert not w.has_edits


def test_binary_value_cells_are_not_editable_and_text_cells_are(qapp, monkeypatch) -> None:
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), [])

    assert not (_row(w, OB_TAG).flags() & Qt.ItemFlag.ItemIsEditable)
    assert _row(w, NAME_TAG).flags() & Qt.ItemFlag.ItemIsEditable


def test_text_edit_still_reaches_the_dataset(qapp, monkeypatch) -> None:
    """Control: the refusal is limited to binary VRs."""
    fired: list[str] = []
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), fired)

    _row(w, NAME_TAG).setText(2, "EDITED^NAME")

    assert str(w.current_dataset.PatientName) == "EDITED^NAME"
    assert w.has_edits
    assert not fired


def _saved(w, tmp_path) -> pydicom.Dataset:
    out = tmp_path / "saved.dcm"
    w._save_dataset_to(out)
    return pydicom.dcmread(out)


def test_multivalued_cs_is_shown_with_backslashes_and_edits_back_to_three_values(qapp, monkeypatch, tmp_path) -> None:
    """Cora's reproduction: change one component of ImageType and save."""
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), [])
    row = _row(w, "(0008, 0008)")
    assert row.text(2) == "ORIGINAL\\PRIMARY\\AXIAL"

    row.setText(2, row.text(2).replace("AXIAL", "LOCALIZER"))

    assert not w._pending_errors
    assert list(_saved(w, tmp_path).ImageType) == ["ORIGINAL", "PRIMARY", "LOCALIZER"]


def test_multivalued_ds_edits_back_to_numbers(qapp, monkeypatch, tmp_path) -> None:
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), [])
    row = _row(w, "(0020, 0032)")  # ImagePositionPatient, DS, VM 3
    assert row.text(2).count("\\") == 2

    row.setText(2, "-158.135803\\-179.035797\\-75.7")

    assert not w._pending_errors
    assert [float(v) for v in _saved(w, tmp_path).ImagePositionPatient] == [-158.135803, -179.035797, -75.7]


def test_a_backslash_in_lt_text_stays_text(qapp, monkeypatch, tmp_path) -> None:
    ds = pydicom.dcmread(get_testdata_file("CT_small.dcm"))
    ds.ImageComments = "before"
    src = tmp_path / "lt.dcm"
    ds.save_as(src)
    w = _widget(monkeypatch, str(src), [])

    _row(w, "(0020, 4000)").setText(2, "left\\right")

    assert _saved(w, tmp_path).ImageComments == "left\\right"


def test_an_empty_numeric_cell_clears_the_value(qapp, monkeypatch, tmp_path) -> None:
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), [])

    _row(w, "(0028, 0010)").setText(2, "")  # Rows, US

    assert not w._pending_errors
    assert _saved(w, tmp_path)[0x00280010].value is None


def test_a_component_that_does_not_convert_is_a_pending_error(qapp, monkeypatch) -> None:
    w = _widget(monkeypatch, get_testdata_file("CT_small.dcm"), [])
    before = list(w.current_dataset.ImagePositionPatient)

    _row(w, "(0020, 0032)").setText(2, "1.0\\not-a-number\\3.0")

    assert w._pending_errors
    assert list(w.current_dataset.ImagePositionPatient) == before
