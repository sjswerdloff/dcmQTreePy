"""#65: after a sequence item is deleted, every later item still resolves to its own dataset.

Rows used to be resolved by their displayed item number, which a delete left stale, so an edit to a later item landed
on the next one and saved cleanly. Resolution now uses the row's position under its header, and the remaining rows are
renumbered for display.

Run offscreen (QT_QPA_PLATFORM=offscreen).
"""

from __future__ import annotations

import os
import pathlib
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

ROI_NAME = "(3006, 0026)"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _rows(item):
    for i in range(item.childCount()):
        c = item.child(i)
        yield c
        yield from _rows(c)


def _is_seq_item(row) -> bool:
    p = row.parent()
    return p is not None and row.text(2).isdigit() and row.text(0) == p.text(0)


def _select(w, row) -> None:
    w.dcm_tree_widget.clearSelection()
    row.setSelected(True)


def _base_ds() -> pydicom.Dataset:
    ds = pydicom.Dataset()
    ds.PatientName = "TRIAGE^65"
    ds.PatientID = "T65"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.481.3"
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    return ds


def _roi_items(names: list[str]) -> pydicom.Sequence:
    items = []
    for n in names:
        it = pydicom.Dataset()
        it.ROIName = n
        items.append(it)
    return pydicom.Sequence(items)


def _load(w, ds):
    td = tempfile.TemporaryDirectory()
    p = pathlib.Path(td.name) / "src.dcm"
    ds.ensure_file_meta()
    ds.is_implicit_VR = False
    ds.is_little_endian = True
    ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    pydicom.dcmwrite(p, ds, write_like_original=False)
    w.populate_tree_widget_from_file(str(p))
    w._td = td
    return w.dcm_tree_widget.topLevelItem(0)


def _widget(monkeypatch) -> M.DCMQtreePy:
    w = M.DCMQtreePy()
    monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
    return w


def _header(top, tag: str):
    return next(r for r in _rows(top) if r.text(0) == tag and r.text(3) == "SQ" and not _is_seq_item(r))


def _name_row(item_row):
    return next(item_row.child(i) for i in range(item_row.childCount()) if item_row.child(i).text(0) == ROI_NAME)


def _delete_item(w, header, index: int) -> None:
    _select(w, header.child(index))
    w.handle_tree_delete_pressed(None)


def test_edit_after_item_delete_lands_on_its_own_item(qapp, monkeypatch) -> None:
    """Cora's reproduction: four items, delete TWO, edit the THREE row."""
    ds = _base_ds()
    ds.StructureSetROISequence = _roi_items(["ONE", "TWO", "THREE", "FOUR"])
    w = _widget(monkeypatch)
    hdr = _header(_load(w, ds), "(3006, 0020)")

    _delete_item(w, hdr, 1)
    three = hdr.child(1)
    assert _name_row(three).text(2) == "THREE"
    _name_row(three).setText(2, "EDITED")

    assert [i.ROIName for i in w.current_dataset.StructureSetROISequence] == ["ONE", "EDITED", "FOUR"]
    assert not w._pending_errors


def test_edit_of_the_last_item_after_a_delete_does_not_run_past_the_end(qapp, monkeypatch) -> None:
    """Three items: the last row's stale number used to index past the end and fall back to the root."""
    ds = _base_ds()
    ds.StructureSetROISequence = _roi_items(["ONE", "TWO", "THREE"])
    w = _widget(monkeypatch)
    hdr = _header(_load(w, ds), "(3006, 0020)")

    _delete_item(w, hdr, 0)
    _name_row(hdr.child(1)).setText(2, "EDITED")

    assert [i.ROIName for i in w.current_dataset.StructureSetROISequence] == ["TWO", "EDITED"]
    assert not w._pending_errors


def test_second_delete_after_a_delete_removes_the_selected_item(qapp, monkeypatch) -> None:
    ds = _base_ds()
    ds.StructureSetROISequence = _roi_items(["ONE", "TWO", "THREE", "FOUR"])
    w = _widget(monkeypatch)
    hdr = _header(_load(w, ds), "(3006, 0020)")

    _delete_item(w, hdr, 1)  # TWO
    _delete_item(w, hdr, 1)  # the row now showing THREE

    assert [i.ROIName for i in w.current_dataset.StructureSetROISequence] == ["ONE", "FOUR"]


def test_remaining_rows_are_renumbered_without_marking_cells_edited(qapp, monkeypatch) -> None:
    ds = _base_ds()
    ds.StructureSetROISequence = _roi_items(["ONE", "TWO", "THREE", "FOUR"])
    w = _widget(monkeypatch)
    hdr = _header(_load(w, ds), "(3006, 0020)")

    _delete_item(w, hdr, 1)

    assert [hdr.child(i).text(2) for i in range(hdr.childCount())] == ["1", "2", "3"]
    assert not w._pending_errors


def test_nested_sequence_edit_after_a_nested_item_delete(qapp, monkeypatch) -> None:
    """The same shape one level down: ROIs inside an item of an outer sequence."""
    ds = _base_ds()
    outer = pydicom.Dataset()
    outer.StructureSetROISequence = _roi_items(["ONE", "TWO", "THREE", "FOUR"])
    ds.ReferencedFrameOfReferenceSequence = pydicom.Sequence([outer])
    w = _widget(monkeypatch)
    top = _load(w, ds)
    hdr = _header(top, "(3006, 0020)")

    _delete_item(w, hdr, 1)
    _name_row(hdr.child(1)).setText(2, "EDITED")

    inner = w.current_dataset.ReferencedFrameOfReferenceSequence[0].StructureSetROISequence
    assert [i.ROIName for i in inner] == ["ONE", "EDITED", "FOUR"]
    assert not w._pending_errors
