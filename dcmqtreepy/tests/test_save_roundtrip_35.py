"""Regression test for issue #35: save round-trip drops private elements.

Tests that opening a DICOM file and saving it via the app's own save path
preserves all elements, private block structure, OB/OW bytes, and produces
byte-identical output for an unmodified file (CT_small.dcm).

Run offscreen (QT_QPA_PLATFORM=offscreen).
"""

from __future__ import annotations

import os
import pathlib
import tempfile

import pydicom
import pytest
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QTreeWidgetItem  # noqa: E402

import dcmqtreepy.dcmQTree as M  # noqa: E402

_CT_SMALL = pathlib.Path(pydicom.__file__).parent / "data" / "test_files" / "CT_small.dcm"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def loaded_widget(qapp):
    """Populate the tree widget from CT_small.dcm and return (widget, orig_bytes)."""
    assert _CT_SMALL.exists(), f"pydicom test file missing: {_CT_SMALL}"
    orig_bytes = _CT_SMALL.read_bytes()
    w = M.DCMQtreePy()
    w.populate_tree_widget_from_file(str(_CT_SMALL))
    return w, orig_bytes


def _save_through_app(w: M.DCMQtreePy, dest: pathlib.Path) -> None:
    """Save through the app own save path (issue #35)."""
    w._save_dataset_to(dest)


class TestSaveRoundtripPreservesPrivateElements:
    """#35: open-then-save must not drop private elements."""

    def test_no_tags_dropped_or_added(self, loaded_widget):
        w, _ = loaded_widget
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "rt.dcm"
            _save_through_app(w, out)
            orig = pydicom.dcmread(_CT_SMALL, force=True)
            saved = pydicom.dcmread(out, force=True)
            orig_tags = {e.tag for e in orig if e.tag.group != 0xFFFC}
            saved_tags = {e.tag for e in saved if e.tag.group != 0xFFFC}
            dropped = orig_tags - saved_tags
            added = saved_tags - orig_tags
            assert not dropped, f"Tags dropped on save: {sorted(str(t) for t in dropped)}"
            assert not added, f"Tags added on save: {sorted(str(t) for t in added)}"

    def test_byte_identical_unmodified(self, loaded_widget):
        """CT_small.dcm must survive open-then-save byte-for-byte."""
        w, orig_bytes = loaded_widget
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "rt.dcm"
            _save_through_app(w, out)
            saved = out.read_bytes()
            assert saved == orig_bytes, (
                f"Round-trip not byte-identical: orig={len(orig_bytes)}B saved={len(saved)}B; "
                f"first diff at byte "
                f"{next((i for i in range(min(len(saved), len(orig_bytes))) if saved[i] != orig_bytes[i]), None)}"
            )

    def test_ob_bytes_preserved(self, loaded_widget):
        """OB/OW private members whose bytes never enter tree text must still be saved."""
        w, _ = loaded_widget
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "rt.dcm"
            _save_through_app(w, out)
            orig = pydicom.dcmread(_CT_SMALL, force=True)
            saved = pydicom.dcmread(out, force=True)
            for tag in (0x00431028, 0x00431029, 0x0043102A):
                assert tag in saved, f"OB element {pydicom.tag.Tag(tag)} missing after save"
                assert saved[tag].value == orig[tag].value, (
                    f"OB bytes changed at {pydicom.tag.Tag(tag)}: orig={orig[tag].value!r} saved={saved[tag].value!r}"
                )

    def test_binary_vr_not_stranded_as_string(self, loaded_widget):
        """Binary numeric VRs must round-trip as ints, not as strings."""
        w, _ = loaded_widget
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "rt.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            numeric_vrs = {
                pydicom.valuerep.VR.SS,
                pydicom.valuerep.VR.US,
                pydicom.valuerep.VR.SL,
                pydicom.valuerep.VR.UL,
                pydicom.valuerep.VR.FL,
                pydicom.valuerep.VR.FD,
            }
            str_drifts = []
            for elem in saved:
                if elem.tag.group % 2 == 1 and elem.VR in numeric_vrs:
                    if isinstance(elem.value, str):
                        str_drifts.append(str(elem.tag))
                if elem.VR in numeric_vrs and isinstance(elem.value, str):
                    str_drifts.append(str(elem.tag))
            assert not str_drifts, f"Binary VRs stranded as str: {str_drifts}"

    def test_edit_roundtrip_value_changes(self, loaded_widget):
        """An edited tree cell must appear in the saved file."""
        w, _ = loaded_widget
        # Find PatientAge row and edit it
        target = None
        top = w.dcm_tree_widget.topLevelItem(0)
        for i in range(top.childCount()):
            child = top.child(i)
            if child.text(0) == "(0010, 1010)":
                target = child
                break
        assert target is not None, "PatientAge row (0010,1010) not found in tree"
        target.setText(2, "045Y")
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "rt.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert saved[0x00101010].value.strip() == "045Y", f"Edited value not written: {saved[0x00101010].value!r}"


# --- Blocker regression tests (cora review 13017, connor review 13018) ---
# One shape per review blocker: deletes that must stick, nested binary that must
# not be root-fished, two creators that must not cross, and edits that cannot be
# applied and must refuse the save instead of silently keeping the original.


def _find_row(item, tag_string: str, name: str = None):
    """Depth-first search for a tree row by tag text (and optionally name text)."""
    for i in range(item.childCount()):
        child = item.child(i)
        if child.text(0) == tag_string and (name is None or child.text(1) == name):
            return child
        found = _find_row(child, tag_string, name)
        if found is not None:
            return found
    return None


def _copy_clean(dataset):
    """A cycle-free save-base copy: write the dataset to a temp file and read it
    back. pydicom 2.4.5 links elements and sequence items to their owners
    (elem.parent, item._parent_dataset, Sequence ReferenceType proxies,
    PrivateBlock.dataset); once the tree's delete/edit paths have mutated a
    loaded dataset those links form cycles that make deepcopy recurse forever
    (measured: spin at dataset.py:2831 -> sequence.py:87 -> dataset.py:477).
    The reload yields a fresh FileDataset carrying exactly the bytes the save
    would write — identical content, no pointers (#35)."""
    tmpdir = tempfile.TemporaryDirectory()
    tmp = pathlib.Path(tmpdir.name) / "copy-base.dcm"
    dataset.ensure_file_meta()
    dataset.is_implicit_VR = False
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    pydicom.dcmwrite(tmp, dataset, write_like_original=False)
    loaded = pydicom.dcmread(tmp, force=True)
    loaded._copy_tmpdir = tmpdir  # keep the backing file alive
    return loaded


def _render_base(widget, dataset):
    """Write `dataset` to a temp file and load it through the app's real loader,
    so the tree carries the exact shapes the renderer produces (creator markers,
    item numbering) — the same file loaded twice (#35)."""
    import tempfile

    tmpdir = tempfile.TemporaryDirectory()
    tmp = pathlib.Path(tmpdir.name) / "render-base.dcm"
    dataset.ensure_file_meta()
    dataset.is_implicit_VR = False
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    pydicom.dcmwrite(tmp, dataset, write_like_original=False)
    widget.setObjectName("dcmQTreeWidget")
    widget.populate_tree_widget_from_file(str(tmp))
    widget._render_tmpdir = tmpdir  # keep the dir alive for the test
    return widget.dcm_tree_widget.topLevelItem(0)


class TestBlocker1DeletesRemoveFromBase:
    """cora blocker 1: a deleted tree row must be absent from the saved file."""

    def test_delete_public_element_absent_after_save(self, loaded_widget):
        w, _ = loaded_widget
        top = w.dcm_tree_widget.topLevelItem(0)
        target = _find_row(top, "(0010, 1010)")  # PatientAge
        assert target is not None
        w.dcm_tree_widget.setCurrentItem(target)
        w.handle_tree_delete_pressed(None)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "del.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert 0x00101010 not in saved, "deleted PatientAge reappeared in saved file"

    def test_delete_private_member_absent_after_save(self, qapp):
        # CT_small's OWN block-0x10 member (0011,1010): element name "[Patient
        # Status]", tag shares the creator's low byte — the exact shape the old
        # low-byte scans misread (cora 13017 #3). Deleting it must remove it from
        # the base AND the saved file (#35). Loaded into a FRESH widget: the
        # shared module fixture is already mutated by other tests in this class.
        w = M.DCMQtreePy()
        w.setObjectName("dcmQTreeWidget")
        w.populate_tree_widget_from_file(str(_CT_SMALL))
        top = w.dcm_tree_widget.topLevelItem(0)
        member = _find_row(top, "(0011, 1010)")
        assert member is not None, "private member row (0011,1010) not rendered by the real loader"
        w.dcm_tree_widget.setCurrentItem(member)
        w.handle_tree_delete_pressed(None)
        assert pydicom.tag.Tag(0x0011, 0x1010) not in w.current_dataset, "member survived delete in the base"
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "delpriv.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert pydicom.tag.Tag(0x0011, 0x1010) not in saved, "deleted private member reappeared in saved file"


class TestBlocker2NestedSQBinary:
    """cora blocker 2: binary elements inside a sequence item survive the round-trip
    and are not confused with a same-tag element at the root."""

    def test_nested_pixel_data_byte_equal_not_root_value(self, loaded_widget):
        # loaded_widget is the CT_small-backed fixture; the nested binary SQ is
        # staged into the file ON DISK first (write a new staged file, then load
        # it), so the whole pipeline — loader, renderer, walk, encoder — handles
        # the nested OB exactly as it would any real file (#35).
        w, orig_bytes = loaded_widget
        assert pydicom.tag.Tag(0x00101002) in w.current_dataset, "fixture: CT_small has OtherPatientIDsSequence"
        nested = b"\x01\x02\x03\x04nested"
        staged_item = pydicom.Dataset()
        staged_item[0x00081150] = pydicom.DataElement(0x00081150, "UI", "1.2.840.10008.5.1.4.1.1.2")
        staged_item[0x00081155] = pydicom.DataElement(0x00081155, "UI", generate_uid())
        staged_item[0x7FE00010] = pydicom.DataElement(0x7FE00010, "OW", nested)
        w.current_dataset.OtherPatientIDsSequence[0].add_new(0x00081199, "SQ", pydicom.Sequence([staged_item]))
        assert pydicom.tag.Tag(0x00081199) in w.current_dataset.OtherPatientIDsSequence[0], "fixture: nested SQ staged"
        tmpdir = tempfile.TemporaryDirectory()
        staged = pathlib.Path(tmpdir.name) / "staged-nested.dcm"
        w.current_dataset.ensure_file_meta()
        w.current_dataset.is_implicit_VR = False
        w.current_dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        pydicom.dcmwrite(staged, w.current_dataset, write_like_original=False)
        # the app loads the staged file fresh — no mutated loaded objects
        w.populate_tree_widget_from_file(str(staged))
        assert pydicom.tag.Tag(0x00081199) in w.current_dataset.OtherPatientIDsSequence[0], "loader lost the nested SQ"
        root_before = bytes(w.current_dataset.PixelData)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "nested.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert bytes(saved.PixelData) == root_before, "root PixelData changed"
            assert pydicom.tag.Tag(0x00081199) in saved.OtherPatientIDsSequence[0], "nested SQ lost from saved file"
            got = saved.OtherPatientIDsSequence[0][0x00081199][0][0x7FE00010].value
            assert bytes(got) == nested, f"nested PixelData lost or replaced: {got!r}"


class TestBlocker3TwoCreators:
    """cora blocker 3: two creators in one private group resolve by block byte —
    editing one member must never land in the other creator's block."""

    @staticmethod
    def _two_creator_dataset():
        # fresh Dataset with both creators — CT_small's own private groups must not
        # collide with the fixture's creator names (#35)
        ds = pydicom.Dataset()
        ds.PatientName = "TEST^TWO"
        ds.PatientID = "TWOCREATOR"
        # ensure_file_meta copies SOPClass/InstanceUID into the media-storage
        # elements — a bare Dataset has neither and the write refuses (verified)
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        # verified on pydicom 2.4.5: PrivateBlock.add_new(offset) takes the LOW
        # byte; the creator signature sits at 0x10, so block-0x20's creator is
        # (0059,2010) only when add_new is given 0x20 — passing 0x10 wrote the
        # value into block 0x10's space as (0059,0011) (verified tree dump).
        # verified on pydicom 2.4.5: private_block(..., create=True) assigns the
        # NEXT free creator slot: CREATORA -> (0059,0010)/block 0x10, CREATORB ->
        # (0059,0011)/block 0x11; add_new's offset is the LOW byte. Two distinct
        # blocks, exactly the shape this test needs (#35).
        block_a = ds.private_block(0x0059, "CREATORA", create=True)
        block_a.add_new(0x11, "LO", "A-original")  # (0059,1011)
        block_b = ds.private_block(0x0059, "CREATORB", create=True)
        block_b.add_new(0x11, "LO", "B-original")  # (0059,1111)
        return ds

    def test_edit_one_creator_member_leaves_other_untouched(self, qapp):
        w = M.DCMQtreePy()
        ds = self._two_creator_dataset()
        top = _render_base(w, ds)
        row_a = _find_row(top, "(0059, 1011)")
        assert row_a is not None, "creator A member row not rendered"
        row_a.setText(2, "A-edited")
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "twocreator.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert saved.private_block(0x0059, "CREATORA")[0x11].value == "A-edited"
            assert saved.private_block(0x0059, "CREATORB")[0x11].value == "B-original", "creator B block corrupted"

    def test_block0x10_member_edit_stays_own_block(self, qapp):
        """connor's hard shape: a block-0x10 member sharing the creator's low byte
        (0011,1010) — CT_small's own. Editing it must land in ITS creator's block;
        a second creator's block stays untouched (#35).

        Verified on pydicom 2.4.5: private_block(create=True) assigns the NEXT free
        creator slot — ZHIMINGSECOND lands at (0011,0011)/block 0x11, and its
        member add_new(0x11, ...) becomes (0011,1111). The tree rows are built to
        match that verified reality; the base is staged through write+reload so the
        save walks exactly what the encoder will see."""
        w = M.DCMQtreePy()
        w.setObjectName("dcmQTreeWidget")
        w.populate_tree_widget_from_file(str(_CT_SMALL))
        block_b = w.current_dataset.private_block(0x0011, "ZHIMINGSECOND", create=True)
        block_b.add_new(0x11, "SS", 999)  # (0011,1111) — verified slot
        top = _render_base(w, w.current_dataset)
        row_a = _find_row(top, "(0011, 1010)")
        assert row_a is not None, "block-0x10 member row not rendered"
        vr = row_a.text(3)
        assert vr in ("SS", "US"), f"unexpected VR for (0011,1010): {vr}"
        second_row = _find_row(top, "(0011, 1111)")
        assert second_row is not None, "second-creator member row not rendered"
        row_a.setText(2, "7")
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "block10.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert saved.private_block(0x0011, "GEMS_PATI_01")[0x10].value == 7, "block-0x10 member edit lost"
            assert saved.private_block(0x0011, "ZHIMINGSECOND")[0x11].value == 999, "second creator mis-written"

    @staticmethod
    def _dirty(item):
        import dcmqtreepy.dcmQTree as _M

        _M  # noqa: B018  (documenting the module under test)
        # rows the add-dialog flow creates are dirty by definition (#35)
        return item

    def test_delete_creator_b_keeps_creator_a(self, qapp):
        w = M.DCMQtreePy()
        ds = self._two_creator_dataset()
        top = _render_base(w, ds)
        creator_b = _find_row(top, "(0059, 0011)")
        assert creator_b is not None
        w.dcm_tree_widget.setCurrentItem(creator_b)
        w.handle_tree_delete_pressed(None)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "delcreator.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert "CREATORA" in saved.private_creators(0x0059)
            # verified 2.4.5: block_a.add_new(0x11, ...) lands at (0059,1011) — the
            # read must use the same offset the fixture wrote (16 == 0x10 would look
            # for a member the fixture never created)
            assert saved.private_block(0x0059, "CREATORA")[0x11].value == "A-original"
            assert pydicom.tag.Tag(0x0059, 0x0011) not in saved, "deleted creator element reappeared"
            assert "CREATORB" not in saved.private_creators(0x0059), "deleted creator block survived"


class TestBlocker1bNestedDeletes:
    """cora 13021 blocker 1: delete must resolve the row's container from its
    ANCESTOR CHAIN — a nested element delete must not touch a same-tag element
    at the root, and deleting one item must not delete its whole sequence."""

    def _nested_dataset(self):
        ds = pydicom.Dataset()
        ds.PatientName = "NEST^TEST"
        ds.PatientID = "ROOTID"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        item1 = pydicom.Dataset()
        item1.PatientID = "ITEM1"
        item2 = pydicom.Dataset()
        item2.PatientID = "ITEM2"
        item3 = pydicom.Dataset()
        item3.PatientID = "ITEM3"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item1, item2, item3])
        return ds

    def test_nested_patientid_delete_keeps_root(self, qapp):
        w = M.DCMQtreePy()
        top = _render_base(w, self._nested_dataset())

        def find_val(item, val):
            for i in range(item.childCount()):
                c = item.child(i)
                if c.text(2) == val:
                    return c
                r = find_val(c, val)
                if r:
                    return r
            return None

        row = find_val(top, "ITEM2")
        assert row is not None and row.text(0) == "(0010, 0020)"
        w.dcm_tree_widget.setCurrentItem(row)
        w.handle_tree_delete_pressed(None)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "nesteddel.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert saved.PatientID == "ROOTID", "nested delete removed the ROOT PatientID"
            ids = [it.get("PatientID") for it in saved.OtherPatientIDsSequence]
            # Cyril 2026-11-01: keep empty items — ITEM2's element was deleted
            # but the emptied item stays in the sequence
            assert ids == ["ITEM1", None, "ITEM3"], f"unexpected items after nested delete: {ids}"

    def test_delete_one_item_keeps_the_sequence(self, qapp):
        w = M.DCMQtreePy()
        top = _render_base(w, self._nested_dataset())

        def find_sq_header(item):
            for i in range(item.childCount()):
                c = item.child(i)
                if c.text(0) == "(0010, 1002)" and not c.text(2).isdigit():
                    return c
                r = find_sq_header(c)
                if r:
                    return r
            return None

        header = find_sq_header(top)
        assert header is not None
        item_rows = [header.child(k) for k in range(header.childCount()) if header.child(k).text(2).isdigit()]
        assert len(item_rows) == 3
        w.dcm_tree_widget.setCurrentItem(item_rows[1])
        w.handle_tree_delete_pressed(None)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "itemdel.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert "OtherPatientIDsSequence" in saved, "deleting one item removed the whole sequence"
            ids = [it.get("PatientID") for it in saved.OtherPatientIDsSequence]
            assert ids == ["ITEM1", "ITEM3"], f"unexpected items: {ids}"

    def test_nested_private_member_delete_keeps_root_member(self, qapp):
        # nested SQ item carries its own block; deleting the NESTED member must
        # leave the root member (same element number) in place (cora 13021 #3)
        w = M.DCMQtreePy()
        ds = pydicom.Dataset()
        ds.PatientName = "PN^PRIV"
        ds.PatientID = "PRIVNEST"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        item1 = pydicom.Dataset()
        item1.PatientID = "ITEM1"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item1])
        # root block member (0059,1020) — verified 2.4.5: creator at (0059,0010),
        # add_new takes the LOW byte
        ds.private_block(0x0059, "BLOCKOWNER", create=True).add_new(0x20, "LO", "root-private")
        with tempfile.TemporaryDirectory() as td:
            staged = pathlib.Path(td) / "privnest.dcm"
            ds.ensure_file_meta()
            ds.is_implicit_VR = False
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            pydicom.dcmwrite(staged, ds, write_like_original=False)
            reloaded = pydicom.dcmread(staged, force=True)
            # add a nested member of the same creator inside item[0] through the
            # reloaded base, then re-stage and render
            blk = reloaded.OtherPatientIDsSequence[0].private_block(0x0059, "BLOCKOWNER", create=True)
            blk.add_new(0x20, "LO", "nested-private")
            staged2 = pathlib.Path(td) / "privnest2.dcm"
            reloaded.ensure_file_meta()
            reloaded.is_implicit_VR = False
            reloaded.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            pydicom.dcmwrite(staged2, reloaded, write_like_original=False)
            top = _render_base(w, pydicom.dcmread(staged2, force=True))

            def find_nested_private(item):
                # the row under the ITEM row of OtherPatientIDsSequence whose value
                # is nested-private
                for i in range(item.childCount()):
                    c = item.child(i)
                    if c.text(2) == "nested-private":
                        return c
                    r = find_nested_private(c)
                    if r:
                        return r
                return None

            row = find_nested_private(top)
            assert row is not None, "nested private member row not rendered"
            w.dcm_tree_widget.setCurrentItem(row)
            w.handle_tree_delete_pressed(None)
            out = pathlib.Path(td) / "privnest-del.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert saved.private_block(0x0059, "BLOCKOWNER")[0x20].value == "root-private", (
                "nested private delete removed the ROOT member"
            )
            nested = saved.OtherPatientIDsSequence[0]
            assert pydicom.tag.Tag(0x0059, 0x1020) not in nested, "nested member survived its delete"


class TestBlocker2bEmptySequencesSurvive:
    """cora 13021 blocker 2: a file whose Type 2 sequence is present-and-empty
    must round-trip with it PRESENT — _prune_empty_sequences used to delete
    every empty SQ, including source-empty ones that CT_small cannot reveal."""

    def test_empty_type2_sequence_roundtrips_present(self, qapp):
        w = M.DCMQtreePy()
        ds = pydicom.Dataset()
        ds.PatientName = "EMPTY^SQ"
        ds.PatientID = "EMPTY1"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.ReferencedStudySequence = pydicom.Sequence()
        with tempfile.TemporaryDirectory() as td:
            staged = pathlib.Path(td) / "emptysq.dcm"
            ds.ensure_file_meta()
            ds.is_implicit_VR = False
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            pydicom.dcmwrite(staged, ds, write_like_original=False)
            _render_base(w, pydicom.dcmread(staged, force=True))
            out = pathlib.Path(td) / "emptysq-out.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert "ReferencedStudySequence" in saved, "unedited save dropped an empty Type 2 sequence"
            assert len(saved.ReferencedStudySequence) == 0
            # and the untouched-nothing path stays byte-exact when re-encoded the
            # same way the save pipeline encodes (file was re-staged through the
            # app; compare element SET rather than bytes because the save rewrites
            # transfer syntax handling at the preamble level)
            tags_orig = {e.tag for e in pydicom.dcmread(staged, force=True) if e.tag.group != 0x0002}
            tags_saved = {e.tag for e in saved if e.tag.group != 0x0002}
            assert tags_orig == tags_saved, f"element sets differ: {tags_orig ^ tags_saved}"


class TestReview13021DeletePrune:
    """cora 13021 #3/#4 and connor 13022 #5: nested private deletes anchor to
    their own container, unresolvable deletes REFUSE loudly (the row stays),
    the private prune actually finds creators, and the save handlers turn the
    walk's refusal into a visible dialog with the file left untouched."""

    def _nested_private_dataset(self, tmpdir):
        ds = pydicom.Dataset()
        ds.PatientName = "PN^PRIV"
        ds.PatientID = "PRIVNEST"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        item1 = pydicom.Dataset()
        item1.PatientID = "ITEM1"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item1])
        # creator (0059,0010) at the root, member (0059,1020) in the block
        ds.private_block(0x0059, "BLOCKOWNER", create=True).add_new(0x20, "LO", "root-private")
        staged = pathlib.Path(tmpdir) / "privnest.dcm"
        ds.ensure_file_meta()
        ds.is_implicit_VR = False
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        pydicom.dcmwrite(staged, ds, write_like_original=False)
        return staged

    def test_root_private_delete_survives_save(self, qapp):
        # exact-shape delete of the root member (0059,1020): marker + low-byte
        # offset must resolve through the block the row's parent owns
        w = M.DCMQtreePy()
        with tempfile.TemporaryDirectory() as td:
            staged = self._nested_private_dataset(td)
            top = _render_base(w, pydicom.dcmread(staged, force=True))

            def find_val(item, val):
                for i in range(item.childCount()):
                    c = item.child(i)
                    if c.text(2) == val:
                        return c
                    r = find_val(c, val)
                    if r:
                        return r
                return None

            row = find_val(top, "root-private")
            assert row is not None, "root private member row not rendered"
            w.dcm_tree_widget.setCurrentItem(row)
            w.handle_tree_delete_pressed(None)
            assert pydicom.tag.Tag(0x0059, 0x1020) not in w.current_dataset, "member survived delete in the base"
            out = pathlib.Path(td) / "privdel.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert pydicom.tag.Tag(0x0059, 0x1020) not in saved, "deleted private member reappeared"

    def test_unresolvable_delete_refuses_and_keeps_row(self, qapp, monkeypatch):
        # cora #3: a private member whose creator cannot be resolved must NOT
        # vanish silently — the dialog fires and the row stays in the tree
        w = M.DCMQtreePy()
        ds = pydicom.Dataset()
        ds.PatientName = "GHOST^DEL"
        ds.PatientID = "GHOSTDEL"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.add_new(pydicom.tag.Tag(0x0059, 0x2010), "LO", "orphan-member")
        top = _render_base(w, ds)
        assert pydicom.tag.Tag(0x0059, 0x2010) in w.current_dataset, "fixture: ghost tag staged"

        def find_tag(item, ts):
            for i in range(item.childCount()):
                c = item.child(i)
                if c.text(0) == ts:
                    return c
                r = find_tag(c, ts)
                if r:
                    return r
            return None

        row = find_tag(top, "(0059, 2010)")
        assert row is not None
        w.dcm_tree_widget.setCurrentItem(row)
        # loud refusal = the handler catches the ValueError, SHOWS the dialog
        # naming the tag (cora 13025: a refused delete must be visible in the
        # windowed build), and the element and row both stay untouched. The
        # dialog is patched — a modal QMessageBox blocks headless runs (faulthandler
        # proved it at :1533 on this head); patching verifies the refusal routes
        # through it, which is the behaviour under test (connor 13022 #5 shape).
        fired = []
        w.non_native_warning_message = lambda title="", text="", buttons=None: fired.append((title, text)) or QMessageBox.Ok
        w.handle_tree_delete_pressed(None)
        assert fired, "refused delete showed no dialog"
        assert fired[0][0] == "Delete refused", fired[0][0]
        assert "(0059, 2010)" in fired[0][1], fired[0][1]
        assert pydicom.tag.Tag(0x0059, 0x2010) in w.current_dataset, "refused delete still removed the element"
        assert any(top.child(k).text(0) == "(0059, 2010)" for k in range(top.childCount())), (
            "row was taken out of the tree despite the refusal"
        )
        assert pydicom.tag.Tag(0x0059, 0x2010) in w.current_dataset, "base mutated despite refusal"

    def test_prune_removes_creator_after_all_members_deleted(self, qapp):
        # cora #4: the prune must actually find the creator (old byte test made
        # it a no-op). Delete the member through the API-shaped path, then save:
        # the creator signature must not survive its emptied block.
        w = M.DCMQtreePy()
        ds = pydicom.Dataset()
        ds.PatientName = "PRUNE^ME"
        ds.PatientID = "PRUNE1"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.private_block(0x0059, "SOLOBLOCK", create=True).add_new(0x20, "LO", "only-member")
        top = _render_base(w, ds)

        def find_val(item, val):
            for i in range(item.childCount()):
                c = item.child(i)
                if c.text(2) == val:
                    return c
                r = find_val(c, val)
                if r:
                    return r
            return None

        row = find_val(top, "only-member")
        assert row is not None
        w.dcm_tree_widget.setCurrentItem(row)
        w.handle_tree_delete_pressed(None)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "prune.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert "SOLOBLOCK" not in saved.private_creators(0x0059), "creator survived its emptied block"
            assert pydicom.tag.Tag(0x0059, 0x1020) not in saved

    def test_save_handler_dialog_on_refusal_file_untouched(self, qapp, monkeypatch):
        # connor #5: through on_file_save_as's shared _perform_save — a refused
        # walk shows a dialog, writes nothing, and leaves has_edits true
        w = M.DCMQtreePy()
        ds = pydicom.Dataset()
        ds.PatientName = "REFUSE^SAVE"
        ds.PatientID = "REFUSE1"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        _render_base(w, ds)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "refused.dcm"
            out.write_bytes(b"PRE-EXISTING CONTENT")
            # force the refuse: an edited row whose element is not in the base
            ghost = QTreeWidgetItem(w.dcm_tree_widget.topLevelItem(0))
            ghost.setText(0, "(0009, 2010)")
            ghost.setText(1, "Private tag data")
            ghost.setText(2, "EDITED")
            ghost.setText(3, "LO")
            w._set_item_dirty(ghost, 2)
            w.has_edits = True
            fired = []
            monkeypatch.setattr(
                w,
                "non_native_warning_message",
                lambda title="", text="", buttons=None: fired.append((title, text)) or QMessageBox.Ok,
            )
            ok = w._perform_save(str(out))
            assert ok is False, "refused save reported success"
            assert fired, "no dialog shown on refusal"
            assert "Save refused" in fired[0][0]
            assert out.read_bytes() == b"PRE-EXISTING CONTENT", "refused save overwrote the file"
            assert w.has_edits is True, "has_edits cleared on refusal"


class TestReview13021bLevelAnchoredDeletes:
    """cora 13021 #3 pinned directly: the NESTED and ROOT private member rows
    share tag (0059,1020) and creator name across levels. A delete at one level
    must touch only that level's element — verified live, the resolver returns
    the block bound to the dataset that OWNS the row."""

    def _staged(self, td):
        ds = pydicom.Dataset()
        ds.PatientName = "LEVEL^DEL"
        ds.PatientID = "LEVEL1"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        item1 = pydicom.Dataset()
        item1.PatientID = "ITEM1"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item1])
        ds.private_block(0x0059, "BLOCKOWNER", create=True).add_new(0x20, "LO", "root-private")
        staged = pathlib.Path(td) / "lvl.dcm"
        ds.ensure_file_meta()
        ds.is_implicit_VR = False
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        pydicom.dcmwrite(staged, ds, write_like_original=False)
        rel = pydicom.dcmread(staged, force=True)
        blk = rel.OtherPatientIDsSequence[0].private_block(0x0059, "BLOCKOWNER", create=True)
        blk.add_new(0x20, "LO", "nested-private")
        staged2 = pathlib.Path(td) / "lvl2.dcm"
        rel.ensure_file_meta()
        rel.is_implicit_VR = False
        rel.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        pydicom.dcmwrite(staged2, rel, write_like_original=False)
        return staged2

    def _find_level_row(self, top, want_item_level):
        # the (0059, 1020) content row at the item level (under a digit row) or
        # at the root level (direct child of top)
        for i in range(top.childCount()):
            c = top.child(i)
            if c.text(0) == "(0059, 1020)" and not want_item_level:
                return c
            if c.text(0) == "(0010, 1002)":
                for j in range(c.childCount()):
                    item_row = c.child(j)
                    if not item_row.text(2).isdigit():
                        continue
                    for k in range(item_row.childCount()):
                        cc = item_row.child(k)
                        if cc.text(0) == "(0059, 1020)" and want_item_level:
                            return cc
        return None

    def test_delete_nested_member_keeps_root(self, qapp):
        w = M.DCMQtreePy()
        with tempfile.TemporaryDirectory() as td:
            staged2 = self._staged(td)
            top = _render_base(w, pydicom.dcmread(staged2, force=True))
            item0 = w.current_dataset.OtherPatientIDsSequence[0]
            nb = item0.private_block(0x0059, "BLOCKOWNER")
            assert 0x20 in nb, "fixture: nested block member present"
            row = self._find_level_row(top, True)
            assert row is not None, "nested (0059,1020) row not rendered"
            # delete through the HANDLER at the nested row (cora 13021 #3):
            # the handler anchors the block at the ROW'S container; a manual
            # del leaves the row in the tree, and the save walk then sees it
            # as an edited row whose block member is gone — a base/tree state
            # mismatch no real flow produces. The sibling test below (root
            # member delete) already drives the handler and passes.
            w.dcm_tree_widget.setCurrentItem(row)
            w.handle_tree_delete_pressed(None)
            assert pydicom.tag.Tag(0x0059, 0x1020) not in item0, "nested delete failed at item level"
            assert pydicom.tag.Tag(0x0059, 0x1020) in w.current_dataset, "ROOT member must survive"
            w.has_edits = True
            out = pathlib.Path(td) / "lvlnested.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert saved.private_block(0x0059, "BLOCKOWNER")[0x20].value == "root-private"
            assert pydicom.tag.Tag(0x0059, 0x1020) not in saved.OtherPatientIDsSequence[0]

    def test_delete_root_member_keeps_nested(self, qapp):
        w = M.DCMQtreePy()
        with tempfile.TemporaryDirectory() as td:
            staged2 = self._staged(td)
            top = _render_base(w, pydicom.dcmread(staged2, force=True))
            row = self._find_level_row(top, False)
            assert row is not None, "root (0059,1020) row not rendered"
            w.dcm_tree_widget.setCurrentItem(row)
            w.handle_tree_delete_pressed(None)
            assert pydicom.tag.Tag(0x0059, 0x1020) not in w.current_dataset, "root delete failed"
            assert pydicom.tag.Tag(0x0059, 0x1020) in w.current_dataset.OtherPatientIDsSequence[0], (
                "nested member must survive the root-level delete (cora 13021 #3)"
            )
            out = pathlib.Path(td) / "lvlroot.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert pydicom.tag.Tag(0x0059, 0x1020) not in saved, "deleted root member reappeared"
            assert saved.OtherPatientIDsSequence[0].private_block(0x0059, "BLOCKOWNER")[0x20].value == "nested-private"


class TestReview13025PruneDiscipline:
    """cora review 13025: the prunes must not change an UNEDITED file. #1:
    same-tag sequences in different parents are judged against their OWN
    header rows (RT Plan: every Beam has a ControlPointSequence with different
    counts). #2: only this session\'s deletes prune — items and creators that
    were empty in the source survive byte for byte. #3: offset 0x00 is a legal
    private member; a block whose only member sits there is not empty."""

    def _two_beams_dataset(self):
        # RTPlan-like shape without needing the RT dictionary: a sequence of
        # items, each holding the SAME-tag nested sequence with DIFFERENT
        # item counts (Beam 1: 3 control points, Beam 2: 1)
        ds = pydicom.Dataset()
        ds.PatientName = "RT^TEST"
        ds.PatientID = "RT1"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        beam_set = pydicom.Sequence()
        for n in (3, 1):
            beam = pydicom.Dataset()
            cp_seq = pydicom.Sequence()
            for i in range(n):
                cp = pydicom.Dataset()
                cp.ReferencedControlPointIndex = str(i)
                cp_seq.append(cp)
            beam.ControlPointSequence = cp_seq
            beam_set.append(beam)
        ds.BeamSequence = beam_set
        return ds

    def _staged(self, td, ds, name="beams.dcm"):
        staged = pathlib.Path(td) / name
        ds.ensure_file_meta()
        ds.is_implicit_VR = False
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        pydicom.dcmwrite(staged, ds, write_like_original=False)
        return staged

    def test_unedited_same_tag_nested_sequences_keep_all_items(self, qapp):
        # cora 13025 #1: unedited save of two same-tag nested SQs with
        # 3 and 1 items keeps 3 and 1 — never counts against one header row
        w = M.DCMQtreePy()
        with tempfile.TemporaryDirectory() as td:
            staged = self._staged(td, self._two_beams_dataset())
            _render_base(w, pydicom.dcmread(staged, force=True))
            out = pathlib.Path(td) / "beams-out.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            counts = [len(b.ControlPointSequence) for b in saved.BeamSequence]
            assert counts == [3, 1], f"nested same-tag sequences pruned: {counts}"

    def test_delete_one_beam_keeps_the_other_intact(self, qapp):
        # deleting beam 1\'s ControlPointSequence row must not touch beam 2\'s
        w = M.DCMQtreePy()
        with tempfile.TemporaryDirectory() as td:
            staged = self._staged(td, self._two_beams_dataset())
            top = _render_base(w, pydicom.dcmread(staged, force=True))

            def find_all(item, ts):
                found = []
                for i in range(item.childCount()):
                    c = item.child(i)
                    if c.text(0) == ts:
                        found.append(c)
                    found.extend(find_all(c, ts))
                return found

            def find_headers(item):
                found = []
                for i in range(item.childCount()):
                    c = item.child(i)
                    if c.text(0) == "(300a, 0111)" and c.text(3) == "SQ" and not c.text(2).isdigit():
                        found.append(c)
                    found.extend(find_headers(c))
                return found

            headers = find_headers(top)
            assert len(headers) == 2, f"expected two ControlPointSequence headers, got {len(headers)}"
            w.dcm_tree_widget.setCurrentItem(headers[0])
            w.handle_tree_delete_pressed(None)
            out = pathlib.Path(td) / "beams-del1.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            beams = list(saved.BeamSequence)
            assert len(beams) == 2, (
                "a whole beam vanished (circular: the walker rebuilt a deleted sequence and the keep-set spliced the item)"
            )
            assert pydicom.tag.Tag(0x300A, 0x111) not in beams[0], "deleted sequence reappeared"
            assert len(beams[1].ControlPointSequence) == 1, f"second beam pruned: {len(beams[1].ControlPointSequence)}"

    def test_source_empty_item_survives_unedited_save(self, qapp):
        # cora 13025 #2: an item that was EMPTY in the source is not trash
        ds = pydicom.Dataset()
        ds.PatientName = "EMPTY^ITEM"
        ds.PatientID = "EMPTYITEM"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        item_a = pydicom.Dataset()
        item_a.PatientID = "A"
        item_b = pydicom.Dataset()  # empty in the source
        ds.OtherPatientIDsSequence = pydicom.Sequence([item_a, item_b])
        with tempfile.TemporaryDirectory() as td:
            staged = self._staged(td, ds, "emptyitem.dcm")
            _render_base(w := M.DCMQtreePy(), pydicom.dcmread(staged, force=True))
            out = pathlib.Path(td) / "emptyitem-out.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert len(saved.OtherPatientIDsSequence) == 2, "source-empty item was pruned"
            if "PatientID" in saved.OtherPatientIDsSequence[1]:
                assert saved.OtherPatientIDsSequence[1].PatientID == ""
            assert pydicom.tag.Tag(0x0010, 0x0020) not in saved.OtherPatientIDsSequence[1]

    def test_source_creator_without_members_survives(self, qapp):
        # cora 13025 #2: a creator that shipped with no members stays —
        # the prune may only remove creators THIS session emptied
        ds = pydicom.Dataset()
        ds.PatientName = "SOLO^CR"
        ds.PatientID = "SOLOCR"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.private_block(0x0059, "NOMEMBERS", create=True)
        with tempfile.TemporaryDirectory() as td:
            staged = self._staged(td, ds, "solocr.dcm")
            _render_base(w := M.DCMQtreePy(), pydicom.dcmread(staged, force=True))
            out = pathlib.Path(td) / "solocr-out.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert "NOMEMBERS" in saved.private_creators(0x0059), "source creator without members was pruned"

    def test_member_at_offset_zero_keeps_creator(self, qapp):
        # cora 13025 #3: (gggg,xx00) is a legal member — a block whose only
        # member sits at offset 0x00 is NOT empty; the creator must survive
        ds = pydicom.Dataset()
        ds.PatientName = "ZERO^OFF"
        ds.PatientID = "ZEROOFF"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.private_block(0x0059, "BLOCKZERO", create=True).add_new(0x00, "LO", "offset-zero")
        with tempfile.TemporaryDirectory() as td:
            staged = self._staged(td, ds, "zeroff.dcm")
            _render_base(w := M.DCMQtreePy(), pydicom.dcmread(staged, force=True))
            out = pathlib.Path(td) / "zeroff-out.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert "BLOCKZERO" in saved.private_creators(0x0059), "creator of a 0x00-member block was pruned"
            assert saved.private_block(0x0059, "BLOCKZERO")[0x00].value == "offset-zero"

    def test_nested_sequence_header_delete_keeps_parent_item(self, qapp):
        """Deleting a Beam's ControlPointSequence (nested header) removes the
        SEQUENCE from that beam ONLY: the beam itself survives (empty or
        edited), every OTHER beam survives untouched, and the root is kept.
        journal kinds must be seq/subtree at the NESTED header's own path —
        never item_emptied/dropped_item at the parent (that splices the beam
        itself — cora 13025 #1/#2: nothing inferred at save time)."""
        w = M.DCMQtreePy()
        w.non_native_warning_message = lambda title="", text="", buttons=None: None
        ds = pydicom.Dataset()
        ds.PatientName = "RT^TEST"
        ds.PatientID = "RT1"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        beam_set = pydicom.Sequence()
        for n in (2, 1):
            beam = pydicom.Dataset()
            beam.BeamName = f"BEAM{n}"
            cp_seq = pydicom.Sequence()
            for i in range(n):
                cp = pydicom.Dataset()
                cp.ReferencedControlPointIndex = str(i)
                cp_seq.append(cp)
            beam.ControlPointSequence = cp_seq
            beam_set.append(beam)
        ds.BeamSequence = beam_set
        top = _render_base(w, ds)

        def find_nested_header(item):
            for i in range(item.childCount()):
                c = item.child(i)
                if c.text(0) == "(300a, 0111)" and c.text(3) == "SQ" and not c.text(2).isdigit():
                    return c
                r = find_nested_header(c)
                if r:
                    return r
            return None

        hdr = find_nested_header(top)
        assert hdr is not None
        w.dcm_tree_widget.setCurrentItem(hdr)
        w.handle_tree_delete_pressed(None)
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "nestedsq.dcm"
            _save_through_app(w, out)
            saved = pydicom.dcmread(out, force=True)
            assert saved.PatientID == "RT1", "root PatientID vanished"
            assert len(saved.BeamSequence) == 2, f"beams lost: {len(saved.BeamSequence)}"
            assert pydicom.tag.Tag(0x300A, 0x0111) not in saved.BeamSequence[0], "deleted sequence reappeared in beam 0"
            assert saved.BeamSequence[0].BeamName == "BEAM2", f"beam identity drifted: {saved.BeamSequence[0].BeamName}"
            assert len(saved.BeamSequence[1].ControlPointSequence) == 1, "beam 1 lost its control points"


class TestBlocker4EditedRowMustFailLoud:
    """connor blocker 4: an edited row whose element cannot be applied to the base
    must REFUSE the save, naming the tag — never silently write the original."""

    def test_ghost_edited_member_raises(self, loaded_widget):
        # connor 13018 blocker 4, exact shape: an EDITED member at a block byte
        # with NO creator element in the base — the save must REFUSE, naming the
        # tag, never silently drop it or write the original.
        w, _ = loaded_widget
        top = w.dcm_tree_widget.topLevelItem(0)
        assert pydicom.tag.Tag(0x0009, 0x2010) not in w.current_dataset, "ghost creator must be absent"
        ghost = M.QTreeWidgetItem(top)
        ghost.setText(0, "(0009, 2001)")
        ghost.setText(1, "Ghost Member")
        ghost.setText(2, "edited-value")
        ghost.setText(3, "LO")
        ghost.setText(4, "")
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "ghost.dcm"
            with pytest.raises(ValueError, match="0009"):
                _save_through_app(w, out)

    def test_unparseable_numeric_edit_raises(self, qapp):
        w = M.DCMQtreePy()
        w.setObjectName("dcmQTreeWidget")
        ds = pydicom.dcmread(_CT_SMALL, force=True)
        ds.add_new(0x00101010, "IS", 42)  # numeric element rendered as "42"
        top = _render_base(w, ds)
        row = _find_row(top, "(0010, 1010)")
        assert row is not None
        row.setText(2, "not-a-number")
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "badnum.dcm"
            with pytest.raises(ValueError, match="0010"):
                _save_through_app(w, out)


# --- Cora 13021 re-review repro tests (f07e4ae) ---


def _base():
    ds = pydicom.Dataset()
    ds.PatientName = "TEST^BASE"
    ds.PatientID = "BASE"
    ds.InstanceNumber = "1"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = generate_uid()
    return ds


def _save(w):
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "out.dcm"
        w._save_dataset_to(out)
        return pydicom.dcmread(out, force=True)


def _find_row_in(root, tag_string):
    for i in range(root.childCount()):
        c = root.child(i)
        if c.text(0) == tag_string:
            return c
        r = _find_row_in(c, tag_string)
        if r:
            return r
    return None


class TestCoraReproNestedOps:
    """Repro tests from Cora's re-review at f07e4ae: nested ops must hit the
    right dataset, not the root."""

    def test_nested_edit_lands_in_item(self, qapp):
        w = M.DCMQtreePy()
        ds = _base()
        item = pydicom.Dataset()
        item.PatientID = "ITEM"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item])
        top = _render_base(w, ds)
        # find the NESTED PatientID (inside the item, not root)
        seq_header = _find_row(top, "(0010, 1002)")
        nested_row = None
        if seq_header is not None:
            for k in range(seq_header.childCount()):
                child = seq_header.child(k)
                for j in range(child.childCount()):
                    if child.child(j).text(0) == "(0010, 0020)":
                        nested_row = child.child(j)
                        break
        assert nested_row is not None
        nested_row.setText(2, "EDITED")
        s = _save(w)
        assert s.PatientID == "BASE", "root PatientID was overwritten"
        assert s.OtherPatientIDsSequence[0].PatientID == "EDITED"

    def test_nested_all_digit_delete_keeps_root(self, qapp):
        w = M.DCMQtreePy()
        ds = _base()
        ds.InstanceNumber = "1"
        item = pydicom.Dataset()
        item.PatientID = "ITEM"
        item.InstanceNumber = "5"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item])
        top = _render_base(w, ds)
        # find the nested InstanceNumber "5"
        seq_header = _find_row(top, "(0010, 1002)")
        nested_row = None
        if seq_header is not None:
            for k in range(seq_header.childCount()):
                child = seq_header.child(k)
                for j in range(child.childCount()):
                    if child.child(j).text(0) == "(0020, 0013)":
                        nested_row = child.child(j)
                        break
        assert nested_row is not None
        w.dcm_tree_widget.setCurrentItem(nested_row)
        w.handle_tree_delete_pressed(None)
        s = _save(w)
        assert s.InstanceNumber == "1", "root InstanceNumber was deleted"
        assert "InstanceNumber" not in s.OtherPatientIDsSequence[0]

    def test_creator_delete_same_group_only(self, qapp):
        w = M.DCMQtreePy()
        ds = _base()
        ds.private_block(0x0059, "A", create=True).add_new(0x11, "LO", "a-member")
        ds.private_block(0x0061, "B", create=True).add_new(0x11, "LO", "b-member")
        top = _render_base(w, ds)
        row = _find_row(top, "(0059, 0010)")
        assert row is not None
        w.dcm_tree_widget.setCurrentItem(row)
        w.handle_tree_delete_pressed(None)
        s = _save(w)
        assert "B" in s.private_creators(0x0061), "cross-group creator deleted"
        assert s.private_block(0x0061, "B")[0x11].value == "b-member"

    def test_prune_by_exact_tag_not_name(self, qapp):
        w = M.DCMQtreePy()
        ds = _base()
        ds.private_block(0x0059, "SAME", create=True).add_new(0x11, "LO", "live")
        ds.private_block(0x0061, "SAME", create=True).add_new(0x11, "LO", "other-live")
        top = _render_base(w, ds)
        # empty the 0059 block
        row = _find_row(top, "(0059, 1011)")
        assert row is not None
        w.dcm_tree_widget.setCurrentItem(row)
        w.handle_tree_delete_pressed(None)
        s = _save(w)
        assert "SAME" in s.private_creators(0x0061), "prune matched by name across groups"
        assert s.private_block(0x0061, "SAME")[0x11].value == "other-live"

    def test_compressed_ts_preserved(self, qapp):
        w = M.DCMQtreePy()
        ds = _base()
        _render_base(w, ds)
        # set TS on current_dataset after render (render may not preserve file_meta)
        w.current_dataset.ensure_file_meta()
        w.current_dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.4.90"
        s = _save(w)
        assert s.file_meta.TransferSyntaxUID == "1.2.840.10008.1.2.4.90", "compressed TS relabelled"

    def test_G_nested_creator_delete_keeps_root(self, qapp):
        w = M.DCMQtreePy()
        ds = _base()
        ds.private_block(0x0059, "P", create=True).add_new(0x11, "LO", "root")
        it = pydicom.Dataset()
        it.private_block(0x0059, "P", create=True).add_new(0x11, "LO", "nested")
        ds.ReferencedImageSequence = pydicom.Sequence([it])
        top = _render_base(w, ds)
        seq = _find_row(top, "(0008, 1140)")
        assert seq is not None
        item = seq.child(0)
        row = _find_row(item, "(0059, 0010)")
        assert row is not None
        w.dcm_tree_widget.setCurrentItem(row)
        w.handle_tree_delete_pressed(None)
        s = _save(w)
        assert s.private_block(0x0059, "P")[0x11].value == "root"

    def test_H_nested_sequence_item_delete_hits_own_sequence(self, qapp):
        w = M.DCMQtreePy()
        ds = _base()
        root_items = [pydicom.Dataset(), pydicom.Dataset()]
        root_items[0].PatientID = "R1"
        root_items[1].PatientID = "R2"
        ds.OtherPatientIDsSequence = pydicom.Sequence(root_items)
        inner = pydicom.Dataset()
        n1 = pydicom.Dataset()
        n1.PatientID = "N1"
        n2 = pydicom.Dataset()
        n2.PatientID = "N2"
        inner.OtherPatientIDsSequence = pydicom.Sequence([n1, n2])
        ds.ReferencedImageSequence = pydicom.Sequence([inner])
        top = _render_base(w, ds)
        rseq = _find_row(top, "(0008, 1140)")
        assert rseq is not None
        nseq = _find_row(rseq, "(0010, 1002)")
        assert nseq is not None
        w.dcm_tree_widget.setCurrentItem(nseq.child(0))
        w.handle_tree_delete_pressed(None)
        s = _save(w)
        assert [i.PatientID for i in s.OtherPatientIDsSequence] == ["R1", "R2"]
        assert [i.PatientID for i in s.ReferencedImageSequence[0].OtherPatientIDsSequence] == ["N2"]

    def test_refusal_from_on_file_save(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        _render_base(w, _base())
        ghost = QTreeWidgetItem(w.dcm_tree_widget.topLevelItem(0))
        ghost.setText(0, "(0009, 2010)")
        ghost.setText(2, "EDITED")
        w._set_item_dirty(ghost, 2)
        w.has_edits = True
        fired = []
        monkeypatch.setattr(
            w, "non_native_warning_message",
            lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok,
        )
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "refused.dcm"
            out.write_bytes(b"PRE-EXISTING")
            # set current_list_item so on_file_save works
            from PySide6.QtWidgets import QListWidgetItem
            w.current_list_item = QListWidgetItem(str(out))
            w.on_file_save()
            assert any("refused" in t.lower() for t in fired), f"no refusal dialog: {fired}"
            assert out.read_bytes() == b"PRE-EXISTING", "refused save overwrote the file"

    def test_pending_error_blocks_save(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        top = _render_base(w, _base())
        row = _find_row(top, "(0020, 0013)")
        assert row is not None
        row.setText(2, "not-a-number")
        assert w._pending_errors, "bad edit did not set _pending_errors"
        fired = []
        monkeypatch.setattr(
            w, "non_native_warning_message",
            lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok,
        )
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "blocked.dcm"
            from PySide6.QtWidgets import QListWidgetItem
            w.current_list_item = QListWidgetItem(str(out))
            w.on_file_save()
            assert any("refused" in t.lower() or "save" in t.lower() for t in fired), f"no dialog: {fired}"

        # Correct the value — save should succeed
        row.setText(2, "1")
        assert not w._pending_errors, "corrected edit did not clear _pending_errors"
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "fixed.dcm"
            w.current_list_item = QListWidgetItem(str(out))
            w.on_file_save()
            assert out.exists(), "save failed after correcting the value"

    def test_two_bad_edits_one_corrected_save_refused(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        ds = _base()
        ds.SliceLocation = "1.0"
        top = _render_base(w, ds)
        row1 = _find_row(top, "(0020, 0013)")  # InstanceNumber (IS)
        row2 = _find_row(top, "(0020, 1041)")  # SliceLocation (DS)
        assert row1 is not None and row2 is not None
        row1.setText(2, "bad-first")
        row2.setText(2, "bad-second")
        assert len(w._pending_errors) == 2, f"expected 2 errors, got {w._pending_errors}"
        # correct only the second
        row2.setText(2, "1.0")
        assert len(w._pending_errors) == 1, f"expected 1 error after correction, got {w._pending_errors}"
        fired = []
        monkeypatch.setattr(
            w, "non_native_warning_message",
            lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok,
        )
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "stillblocked.dcm"
            from PySide6.QtWidgets import QListWidgetItem
            w.current_list_item = QListWidgetItem(str(out))
            w.on_file_save()
            assert any("refused" in t.lower() or "save" in t.lower() for t in fired), f"no dialog: {fired}"

    def test_root_edit_does_not_clear_nested_error(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        ds = _base()
        item = pydicom.Dataset()
        item.InstanceNumber = "5"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item])
        top = _render_base(w, ds)
        # root InstanceNumber = direct child of top
        root_row = None
        for i in range(top.childCount()):
            if top.child(i).text(0) == "(0020, 0013)":
                root_row = top.child(i)
                break
        # nested InstanceNumber = inside the sequence item
        seq_header = _find_row(top, "(0010, 1002)")
        nested_row = None
        if seq_header is not None:
            for k in range(seq_header.childCount()):
                child = seq_header.child(k)
                for j in range(child.childCount()):
                    if child.child(j).text(0) == "(0020, 0013)":
                        nested_row = child.child(j)
                        break
        assert root_row is not None and nested_row is not None and root_row is not nested_row
        # bad edit to nested InstanceNumber
        nested_row.setText(2, "bad-nested")
        assert len(w._pending_errors) == 1
        # good edit to root InstanceNumber — must NOT clear the nested error
        root_row.setText(2, "1")
        assert len(w._pending_errors) == 1, "root edit cleared nested error (keyed by tag, not row)"
        fired = []
        monkeypatch.setattr(
            w, "non_native_warning_message",
            lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok,
        )
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "stillblocked.dcm"
            from PySide6.QtWidgets import QListWidgetItem
            w.current_list_item = QListWidgetItem(str(out))
            w.on_file_save()
            assert any("refused" in t.lower() or "save" in t.lower() for t in fired), f"no dialog: {fired}"

    def test_add_element_under_nested_item(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
        ds = _base()
        item = pydicom.Dataset()
        item.PatientID = "ITEM"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item])
        top = _render_base(w, ds)
        seq_header = _find_row(top, "(0010, 1002)")
        assert seq_header is not None
        item_row = seq_header.child(0)
        w.dcm_tree_widget.setCurrentItem(item_row)

        # Monkeypatch the dialog to return a PatientID element
        mock_elem = pydicom.DataElement(0x00100020, "LO", None)

        class FakeDialog:
            current_public_element = mock_elem
            ui = type("UI", (), {"text_edit_element_value": type("TE", (), {"toPlainText": lambda self: "NESTEDID"})()})()

            def __init__(self, *a, **kw):
                pass

            def setProperty(self, *a):
                pass

            def exec(self):
                pass

        monkeypatch.setattr(M, "AddPublicElementDialog", FakeDialog)
        w.on_add_element()
        s = _save(w)
        assert s.OtherPatientIDsSequence[0].PatientID == "NESTEDID", "add-element wrote to wrong dataset"
        assert s.PatientID == "BASE", "root PatientID was overwritten"

    def test_add_refused_on_sequence_header(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        ds = _base()
        ds.OtherPatientIDsSequence = pydicom.Sequence([pydicom.Dataset()])
        top = _render_base(w, ds)
        seq_header = _find_row(top, "(0010, 1002)")
        assert seq_header is not None
        w.dcm_tree_widget.setCurrentItem(seq_header)
        fired = []
        monkeypatch.setattr(
            w, "non_native_warning_message",
            lambda title="", text="", buttons=None: fired.append(title) or QMessageBox.Ok,
        )
        mock_elem = pydicom.DataElement(0x00100020, "LO", None)

        class FakeDialog:
            current_public_element = mock_elem
            ui = type("UI", (), {"text_edit_element_value": type("TE", (), {"toPlainText": lambda self: "X"})()})()
            def __init__(self, *a, **kw): pass
            def setProperty(self, *a): pass
            def exec(self): pass

        monkeypatch.setattr(M, "AddPublicElementDialog", FakeDialog)
        w.on_add_element()
        assert any("refused" in t.lower() for t in fired), f"no refusal dialog: {fired}"
        s = _save(w)
        assert s.PatientID == "BASE", "refused add modified root"
        assert not s.OtherPatientIDsSequence[0].get("PatientID"), "refused add landed in item"

    def test_deleted_row_drops_pending_error(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
        top = _render_base(w, _base())
        row = _find_row(top, "(0020, 0013)")
        assert row is not None
        row.setText(2, "bad-value")
        assert len(w._pending_errors) == 1
        w.dcm_tree_widget.setCurrentItem(row)
        w.handle_tree_delete_pressed(None)
        assert len(w._pending_errors) == 0, "deleted row kept its pending error"

    def test_delete_item_drops_descendant_errors(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
        ds = _base()
        item = pydicom.Dataset()
        item.InstanceNumber = "5"
        ds.OtherPatientIDsSequence = pydicom.Sequence([item])
        top = _render_base(w, ds)
        # find the nested InstanceNumber and make a bad edit
        seq_header = _find_row(top, "(0010, 1002)")
        nested_row = None
        for k in range(seq_header.childCount()):
            child = seq_header.child(k)
            for j in range(child.childCount()):
                if child.child(j).text(0) == "(0020, 0013)":
                    nested_row = child.child(j)
                    break
        assert nested_row is not None
        nested_row.setText(2, "bad-value")
        assert len(w._pending_errors) == 1
        # delete the item (which removes the nested row)
        item_row = seq_header.child(0)
        w.dcm_tree_widget.setCurrentItem(item_row)
        w.handle_tree_delete_pressed(None)
        assert len(w._pending_errors) == 0, "deleted item kept descendant errors"

    def test_creator_delete_drops_member_errors(self, qapp, monkeypatch):
        w = M.DCMQtreePy()
        monkeypatch.setattr(w, "non_native_warning_message", lambda *a, **kw: QMessageBox.Ok)
        ds = _base()
        ds.private_block(0x0059, "A", create=True).add_new(0x11, "US", 42)
        top = _render_base(w, ds)
        member_row = _find_row(top, "(0059, 1011)")
        assert member_row is not None
        member_row.setText(2, "bad-value")
        assert len(w._pending_errors) == 1
        creator_row = _find_row(top, "(0059, 0010)")
        assert creator_row is not None
        w.dcm_tree_widget.setCurrentItem(creator_row)
        w.handle_tree_delete_pressed(None)
        assert len(w._pending_errors) == 0, "creator delete kept member errors"
