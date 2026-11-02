"""#68: a load that fails while the tree is being built must not leave the tree's signals blocked.

Blocked signals stop `on_tree_item_changed` from running, so every later edit changes only the displayed row
and a save writes the old value. The failure is injected after the rows are built, so editable rows exist.

Run offscreen (QT_QPA_PLATFORM=offscreen).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from pydicom.data import get_testdata_file  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

PATIENT_ID = "(0010, 0020)"


class _InjectedLoadError(RuntimeError):
    """Stands in for any exception raised while the tree is built."""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _find_row(item, tag_string: str):
    for i in range(item.childCount()):
        child = item.child(i)
        if child.text(0) == tag_string:
            return child
        found = _find_row(child, tag_string)
        if found is not None:
            return found
    return None


def test_failed_load_leaves_edits_reaching_the_dataset(qapp, monkeypatch) -> None:
    w = M.DCMQtreePy()
    monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
    original = M.DCMQtreePy._populate_tree_widget_item_from_dataset

    def build_then_fail(self, parent, ds):
        original(self, parent, ds)
        if parent is self.dcm_tree_widget.topLevelItem(0):
            raise _InjectedLoadError("injected after the rows were built")

    monkeypatch.setattr(M.DCMQtreePy, "_populate_tree_widget_item_from_dataset", build_then_fail)
    with pytest.raises(_InjectedLoadError):
        w.populate_tree_widget_from_file(get_testdata_file("CT_small.dcm"))

    assert not w.dcm_tree_widget.signalsBlocked(), "tree signals left blocked after a failed load"
    row = _find_row(w.dcm_tree_widget.topLevelItem(0), PATIENT_ID)
    assert row is not None
    row.setText(2, "EDITED-AFTER-FAILURE")
    assert w.current_dataset[pydicom.tag.Tag(0x00100020)].value == "EDITED-AFTER-FAILURE", "edit did not reach the dataset"
