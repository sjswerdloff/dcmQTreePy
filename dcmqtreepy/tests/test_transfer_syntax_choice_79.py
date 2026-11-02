"""#79: values too long for Explicit VR are found from raw lengths at load, and the user chooses the encoding.

PS3.5 6.2.2 (CP-1066): a value whose VR has a 16-bit length field and which is longer than 65534 bytes can only be
written in Explicit VR as UN. Keeping Implicit VR is the default; Explicit VR with UN is the user's choice.

Run offscreen (QT_QPA_PLATFORM=offscreen).
"""

from __future__ import annotations

import os
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom  # noqa: E402
import pytest  # noqa: E402
from pydicom.dataelem import RawDataElement  # noqa: E402
from pydicom.dataset import Dataset, FileMetaDataset  # noqa: E402
from pydicom.uid import (  # noqa: E402
    ExplicitVRBigEndian,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEG2000Lossless,
    generate_uid,
)
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

CONTOUR_DATA = pydicom.tag.Tag("ContourData")
FRAME_NUMBERS = pydicom.tag.Tag("ReferencedFrameNumber")  # IS, VM 1-n
BIG_CONTOUR = [f"{i * 0.123456:.6f}" for i in range(15000)]  # about 155 KB as DS text


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _write(ds: Dataset, path: pathlib.Path, implicit: bool = True) -> pathlib.Path:
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian if implicit else ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = implicit
    pydicom.dcmwrite(path, ds, write_like_original=False)
    return path


def _rtss(contours: list[list[str]]) -> Dataset:
    """An RT Structure Set with one ROI holding the given contours."""
    ds = Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.481.3"
    ds.SOPInstanceUID = generate_uid()
    ds.PatientName = "ZZTEST^SEVENTYNINE"
    items = []
    for points in contours:
        c = Dataset()
        c.ContourData = points
        items.append(c)
    roi = Dataset()
    roi.ContourSequence = items
    ds.ROIContourSequence = [roi]
    return ds


def _widget(monkeypatch, path, asked: list, answer) -> M.DCMQtreePy:
    w = M.DCMQtreePy()
    monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
    monkeypatch.setattr(w, "_ask_oversized_choice", lambda oversized: asked.append(list(oversized)) or answer)
    w.populate_tree_widget_from_file(str(path))
    return w


# --- the pure decision -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "oversized", "choice", "expected"),
    [
        (ImplicitVRLittleEndian, False, M.OversizedChoice.KEEP_IMPLICIT, (ExplicitVRLittleEndian, False)),
        (ImplicitVRLittleEndian, True, M.OversizedChoice.KEEP_IMPLICIT, (ImplicitVRLittleEndian, True)),
        (ImplicitVRLittleEndian, True, M.OversizedChoice.EXPLICIT_WITH_UN, (ExplicitVRLittleEndian, False)),
        (None, False, M.OversizedChoice.KEEP_IMPLICIT, (ExplicitVRLittleEndian, False)),
        (None, True, M.OversizedChoice.KEEP_IMPLICIT, (ImplicitVRLittleEndian, True)),
        (ExplicitVRLittleEndian, True, M.OversizedChoice.KEEP_IMPLICIT, (ExplicitVRLittleEndian, False)),
        (ExplicitVRBigEndian, True, M.OversizedChoice.KEEP_IMPLICIT, (ExplicitVRBigEndian, False)),
        (JPEG2000Lossless, True, M.OversizedChoice.KEEP_IMPLICIT, (JPEG2000Lossless, False)),
    ],
)
def test_choose_transfer_syntax(source, oversized, choice, expected) -> None:
    assert M.choose_transfer_syntax(source, oversized, choice) == expected


def test_the_default_choice_keeps_implicit() -> None:
    assert M.choose_transfer_syntax(ImplicitVRLittleEndian, True) == (ImplicitVRLittleEndian, True)


# --- detection ---------------------------------------------------------------------------------------------------


def test_detection_finds_a_nested_value_without_converting_the_others(tmp_path) -> None:
    src = _write(_rtss([["1.0", "2.0", "3.0"], BIG_CONTOUR]), tmp_path / "src.dcm")
    ds = pydicom.dcmread(src)

    found = M.find_oversized_elements(ds)

    contours = ds.ROIContourSequence[0].ContourSequence
    assert found == [(contours[1], CONTOUR_DATA)]
    assert isinstance(contours[0].get_item(CONTOUR_DATA), RawDataElement), "a short value was converted"
    assert isinstance(contours[1].get_item(CONTOUR_DATA), RawDataElement), "the long value was converted"


def test_detection_is_not_limited_to_the_two_known_tags(tmp_path) -> None:
    ds = _rtss([["1.0", "2.0", "3.0"]])
    ds.ReferencedFrameNumber = [str(i) for i in range(20000)]  # IS, about 109 KB
    found = M.find_oversized_elements(pydicom.dcmread(_write(ds, tmp_path / "src.dcm")))

    assert [t for _, t in found] == [FRAME_NUMBERS]


@pytest.mark.parametrize(("count", "flagged"), [(32767, False), (32768, True)])
def test_detection_boundary_is_65534_bytes(tmp_path, count, flagged) -> None:
    """count values of "1" encode as 2*count - 1 bytes, padded to 2*count: 65534 fits, 65536 does not."""
    ds = _rtss([["1.0", "2.0", "3.0"]])
    ds.ReferencedFrameNumber = ["1"] * count
    read = pydicom.dcmread(_write(ds, tmp_path / "src.dcm"))
    assert read.get_item(FRAME_NUMBERS).length == 2 * count

    assert bool(M.find_oversized_elements(read)) is flagged


def test_encoded_value_length_matches_the_written_length(tmp_path) -> None:
    """The measure used after conversion agrees with what pydicom writes."""
    ds = _rtss([BIG_CONTOUR])
    read = pydicom.dcmread(_write(ds, tmp_path / "src.dcm"))
    contour = read.ROIContourSequence[0].ContourSequence[0]
    raw_length = contour.get_item(CONTOUR_DATA).length

    assert M.encoded_value_length(contour[CONTOUR_DATA]) == raw_length


# --- the save ----------------------------------------------------------------------------------------------------


def test_save_asks_and_keep_implicit_preserves_the_values(qapp, monkeypatch, tmp_path) -> None:
    asked: list = []
    w = _widget(monkeypatch, _write(_rtss([BIG_CONTOUR]), tmp_path / "src.dcm"), asked, M.OversizedChoice.KEEP_IMPLICIT)
    out = tmp_path / "out.dcm"

    assert w._perform_save(str(out)) is True

    assert [[t for _, t in a] for a in asked] == [[CONTOUR_DATA]]
    saved = pydicom.dcmread(out)
    assert saved.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian
    assert [str(v) for v in saved.ROIContourSequence[0].ContourSequence[0].ContourData] == BIG_CONTOUR


def test_save_with_explicit_un_writes_un_for_that_element_and_vrs_for_the_rest(qapp, monkeypatch, tmp_path) -> None:
    asked: list = []
    src = _write(_rtss([BIG_CONTOUR]), tmp_path / "src.dcm")
    w = _widget(monkeypatch, src, asked, M.OversizedChoice.EXPLICIT_WITH_UN)
    out = tmp_path / "out.dcm"

    with pytest.warns(UserWarning, match="UN"):
        assert w._perform_save(str(out)) is True

    saved = pydicom.dcmread(out)
    assert saved.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
    assert saved["PatientName"].VR == "PN"
    elem = saved.ROIContourSequence[0].ContourSequence[0][CONTOUR_DATA]
    assert elem.VR == "UN"
    # PS3.5 6.2.2 Note 2: a reader that knows the VR decodes the UN value as Implicit VR LE
    assert elem.value.decode("ascii").rstrip(" \x00").split("\\") == BIG_CONTOUR


def test_cancel_writes_nothing(qapp, monkeypatch, tmp_path) -> None:
    w = _widget(monkeypatch, _write(_rtss([BIG_CONTOUR]), tmp_path / "src.dcm"), [], None)
    out = tmp_path / "out.dcm"

    assert w._perform_save(str(out)) is False

    assert not out.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_no_long_value_no_question_and_explicit(qapp, monkeypatch, tmp_path) -> None:
    asked: list = []
    w = _widget(monkeypatch, _write(_rtss([["1.0", "2.0", "3.0"]]), tmp_path / "src.dcm"), asked, None)
    out = tmp_path / "out.dcm"

    assert w._perform_save(str(out)) is True

    assert asked == []
    assert pydicom.dcmread(out).file_meta.TransferSyntaxUID == ExplicitVRLittleEndian


def test_explicit_source_is_never_asked(qapp, monkeypatch, tmp_path) -> None:
    """An Explicit VR source already carries its VRs; pydicom writes its long value as UN, as it was read."""
    asked: list = []
    src = _write(_rtss([["1.0", "2.0", "3.0"]]), tmp_path / "src.dcm", implicit=False)
    w = _widget(monkeypatch, src, asked, None)

    assert w._perform_save(str(tmp_path / "out.dcm")) is True
    assert asked == []


def test_a_long_value_in_a_deleted_item_is_not_asked_about(qapp, monkeypatch, tmp_path) -> None:
    asked: list = []
    w = _widget(monkeypatch, _write(_rtss([["1.0", "2.0", "3.0"], BIG_CONTOUR]), tmp_path / "src.dcm"), asked, None)
    del w.current_dataset.ROIContourSequence[0].ContourSequence[1]
    out = tmp_path / "out.dcm"

    assert w._perform_save(str(out)) is True

    assert asked == []
    assert pydicom.dcmread(out).file_meta.TransferSyntaxUID == ExplicitVRLittleEndian


def test_an_edit_that_makes_a_value_too_long_is_asked_about(qapp, monkeypatch, tmp_path) -> None:
    ds = _rtss([["1.0", "2.0", "3.0"]])
    ds.ImageComments = "short"  # LT: 16-bit length in Explicit VR
    asked: list = []
    w = _widget(monkeypatch, _write(ds, tmp_path / "src.dcm"), asked, M.OversizedChoice.KEEP_IMPLICIT)
    row = next(
        w.dcm_tree_widget.topLevelItem(0).child(i)
        for i in range(w.dcm_tree_widget.topLevelItem(0).childCount())
        if w.dcm_tree_widget.topLevelItem(0).child(i).text(0) == "(0020, 4000)"
    )
    row.setText(2, "x" * 70000)

    assert w._perform_save(str(tmp_path / "out.dcm")) is True

    assert [[t for _, t in a] for a in asked] == [[pydicom.tag.Tag("ImageComments")]]


def test_pending_error_refuses_without_asking(qapp, monkeypatch, tmp_path) -> None:
    asked: list = []
    w = _widget(monkeypatch, _write(_rtss([BIG_CONTOUR]), tmp_path / "src.dcm"), asked, M.OversizedChoice.KEEP_IMPLICIT)
    w._pending_errors[0] = ValueError("bad edit")
    out = tmp_path / "out.dcm"

    assert w._perform_save(str(out)) is False

    assert asked == []
    assert not out.exists()


# --- the dialog's buttons map to the choice ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("button_text", "expected"),
    [
        ("Keep Implicit VR", M.OversizedChoice.KEEP_IMPLICIT),
        ("Explicit VR with UN", M.OversizedChoice.EXPLICIT_WITH_UN),
        ("Cancel", None),
    ],
)
def test_dialog_buttons_map_to_the_choice(qapp, monkeypatch, tmp_path, button_text, expected) -> None:
    src = _write(_rtss([BIG_CONTOUR]), tmp_path / "src.dcm")
    w = M.DCMQtreePy()
    w.populate_tree_widget_from_file(str(src))
    shown: list[str] = []

    def click(dlg: QMessageBox) -> int:
        shown.append(dlg.text())
        button = next(b for b in dlg.buttons() if b.text().replace("&", "") == button_text)
        button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", click)

    assert w._ask_oversized_choice(w._current_oversized()) is expected
    assert "(3006, 0050) ContourData" in shown[0]
