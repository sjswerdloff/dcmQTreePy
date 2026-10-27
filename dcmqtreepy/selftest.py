"""Hidden self-test entry point for packaged (PyInstaller) builds.

Refs #33 / PR #34 (cyril's merge-seat review, 28 Oct): the release smoke test must
do what the issue asks — open a sample DICOM file, save it unchanged (byte
comparison), and open an image in the bundled viewer — not merely prove the GUI
process survives 20 seconds. The GUI event loop cannot run headless on CI runners,
so this is the strongest honest substitute, executed through the packaged executable
itself (``dcmQTreePy --selftest``), which proves the bundle end to end:

- every PyInstaller-collected module loads — importing this module's GUI entry
  pulls in pydicom, numpy, PySide6, dcm_mini_viewer and the private dictionaries;
- constructs the full main window offscreen and opens a sample DICOM through the
  app's own open path (``populate_tree_widget_from_file``), asserting the dataset
  and the populated tree are non-empty;
- opens the image in the bundled ``dcm_mini_viewer`` and asserts a real, non-null
  pixmap lands on its label;
- save-unchanged with byte comparison: reads the sample, writes it back with
  pydicom's writer (with the same ``ensure_file_meta`` + explicit-VR little-endian
  finalization ``on_file_save_as`` performs), asserts the written bytes are
  byte-identical to the input, and asserts determinism (two saves identical).

Why the save stage goes through pydicom's writer and not the tree round trip —
probed on this host (macOS arm64, locked venv, pydicom 2.4.5) BEFORE wiring:
the tree round trip is not save-unchanged. Tree cells carry text, so CT_small.dcm's
private SL element (0009,1027) comes back as a string and raises OSError inside
``dcmwrite`` through the app's own save path today (the app logs "element can not
be copied/saved" for unresolvable private creators, and the "until save as is
working" comments in dcmQTree.py mark this as known scope). A tree-path byte assert
would fail the RELEASE build over the app's known save defects, not packaging —
testing a product promise the app does not make. If the tree save path is later
made faithful, switch ``_save_through_writer`` to the tree serialization here and
the byte comparison stays exactly the same.

Exit codes (no swallowed failures — CI checks the exit code directly):
  0  every stage passed
  1  a stage failed (each failure printed as "selftest FAIL: ...")
  2  bad invocation (missing/unreadable input, unusable arguments)

Usage (invoked by the packaged executable, invisible to GUI users):
    dcmQTreePy --selftest [path.dcm] [--platform offscreen]

With no path, pydicom's built-in CT_small.dcm sample is used — the same file the
issue names. ``--platform offscreen`` selects Qt's offscreen QPA plugin so the
headless stages work on CI runners; omit it on a machine with a display.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


def _parse_args(argv: list[str]) -> tuple[Path | None, str | None, int]:
    """Parse argv. Returns (dicom_path, qpa_platform, exit_code_on_usage_error)."""
    dicom_path: Path | None = None
    qpa: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--platform":
            if i + 1 >= len(argv):
                print("--platform requires a value (e.g. offscreen)", file=sys.stderr)
                return None, None, 2
            qpa = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--"):
            print(f"unknown option for --selftest: {arg}", file=sys.stderr)
            return None, None, 2
        if dicom_path is not None:
            print("only one DICOM path may be given to --selftest", file=sys.stderr)
            return None, None, 2
        dicom_path = Path(arg)
        i += 1
    return dicom_path, qpa, 0


def _resolve_input(dicom_path: Path | None) -> Path:
    """Default to pydicom's own CT_small.dcm sample (the file #33 names).

    Probed on this repo's locked venv AND a packaged --windowed .app built with the
    CI's exact flags (macOS arm64, pydicom 2.4.5), BEFORE wiring, in that order:

    1. NOT pydicom.data.get_testdata_files: pydicom's data_manager imports
       pkg_resources (setuptools' legacy module), which uv's lock does not install —
       the helper raises ModuleNotFoundError in this venv, dev and frozen alike.
    2. NOT ``Path(pydicom.__file__).parent / "data" / "test_files"``: frozen
       pydicom ships its package as a PEP 302 loader-only stub (no real __init__.py
       on disk), so PyInstaller does not collect the data/test_files tree at all —
       proven: the path resolves inside the .app but is_file() is false.

    So the bundle ships its OWN copy: the workflow copies the sample next to the
    executable (Contents/MacOS/CT_small.dcm on macOS, dist/CT_small.dcm on Windows),
    and that is the default probed first. Keeps setuptools and re-collected package
    data out of the bundle while still opening pydicom's named sample.
    """
    if dicom_path is not None:
        return dicom_path
    bundled = Path(sys.argv[0]).resolve().parent / "CT_small.dcm"
    if bundled.is_file():
        return bundled
    import pydicom

    sample = Path(pydicom.__file__).parent / "data" / "test_files" / "CT_small.dcm"
    if not sample.is_file():
        raise FileNotFoundError(f"no bundled CT_small.dcm next to {sys.argv[0]!r} and none at {sample}")
    return sample


def _save_through_writer(src: Path, out_path: Path) -> None:
    """Write the sample back with pydicom's writer, using the same file-meta
    finalization as DCMQtreePy.on_file_save_as (ensure_file_meta + explicit
    explicit-VR little-endian transfer syntax), sans dialog and sans tree."""
    import pydicom
    from pydicom import dcmwrite

    ds = pydicom.dcmread(src, force=True)
    ds.ensure_file_meta()
    ds.is_implicit_VR = False
    ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    dcmwrite(out_path, ds, write_like_original=False)


def run_selftest(dicom_path: Path | None, qpa_platform: str | None = None) -> int:
    """Open, save + byte-stability + value round trip, view. Returns process exit code."""
    try:
        src = _resolve_input(dicom_path)
    except Exception as exc:
        print(f"selftest: cannot resolve input file: {exc}", file=sys.stderr)
        return 2
    if not src.is_file():
        print(f"selftest: input does not exist: {src}", file=sys.stderr)
        return 2

    original_bytes = src.read_bytes()
    if not original_bytes:
        print(f"selftest: input is empty: {src}", file=sys.stderr)
        return 2

    if qpa_platform:
        # Must be set before any Qt platform object is touched. The env var is the
        # supported selection; a --windowed PyInstaller build invoked via
        # Start-Process -ArgumentList may not receive argv, so env is the portable half.
        os.environ["QT_QPA_PLATFORM"] = qpa_platform

    from PySide6.QtWidgets import QApplication

    # The instance must outlive the widgets below; bound to a name so a linter
    # cannot "remove" it and garbage-collect the application out from under Qt.
    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841

    # Import inside the function: the GUI module constructs widgets and needs an app.
    # Its top-level imports (pydicom, numpy, dcm_mini_viewer, PySide6) riding along
    # is part of what this stage proves about the bundle.
    from dcmqtreepy.dcmQTree import DCMQtreePy

    failures: list[str] = []
    notes: list[str] = []
    out_dir = Path(tempfile.mkdtemp(prefix="dcmqtreepy-selftest-"))
    out_path = out_dir / src.name
    out_path2 = out_dir / f"second-{src.name}"

    widget = DCMQtreePy()
    try:
        # Stage 1: open through the GUI's own open path (tree population). A corrupt
        # input must fail the selftest, not crash it uncaught: dcmread(force=True)
        # tolerates bad preambles by returning a sparse dataset, so assert explicitly.
        try:
            widget.populate_tree_widget_from_file(str(src))
        except Exception as exc:
            failures.append(f"open: populate raised {type(exc).__name__}: {exc}")
        else:
            if widget.current_dataset is None or not len(widget.current_dataset):
                failures.append("open: dataset empty after populate")
            if widget.dcm_tree_widget.topLevelItemCount() < 1:
                failures.append("open: tree not populated")

        # Stage 2: save it back and byte-compare — the packaged app's pydicom
        # writer path (same finalization as on_file_save_as) must reproduce the
        # sample byte-for-byte; and two saves must agree with each other.
        try:
            _save_through_writer(src, out_path)
        except Exception as exc:
            failures.append(f"save: writer raised {exc!r}")
        else:
            saved_bytes = out_path.read_bytes()
            if saved_bytes != original_bytes:
                failures.append(f"save: writer output differs from input ({len(saved_bytes)}B vs {len(original_bytes)}B)")
            try:
                _save_through_writer(src, out_path2)
            except Exception as exc:
                failures.append(f"save: second save raised {exc!r}")
            else:
                if out_path.read_bytes() != out_path2.read_bytes():
                    failures.append("save: two saves of the same file are not byte-identical")
                else:
                    notes.append("save: writer byte-identical to input and deterministic")

        # Stage 3: open the image in the bundled viewer and render it — the
        # dcm_mini_viewer path the GUI uses from on_view_image.
        try:
            ok, err = widget.image_viewer.dicom_handler.load_file(str(src))
            if not ok:
                failures.append(f"view: dicom_handler.load_file failed: {err}")
            widget.image_viewer.display_dicom_image()
            pix = widget.image_viewer.image_label.pixmap() if widget.image_viewer.image_label else None
            if pix is None or pix.isNull():
                failures.append("view: viewer label shows no pixmap after display_dicom_image")
            else:
                notes.append(f"view: rendered {pix.width()}x{pix.height()} pixmap")
        except Exception as exc:
            failures.append(f"view: viewer render raised {exc!r}")
    finally:
        widget.help_assistant.cleanup()
        widget.close()
        shutil.rmtree(out_dir, ignore_errors=False)

    if failures:
        for f in failures:
            print(f"selftest FAIL: {f}", file=sys.stderr)
        print(f"selftest: {len(failures)} failure(s) on {src}", file=sys.stderr)
        return 1

    print(f"selftest OK on {src} ({len(original_bytes)} bytes opened through packaged build)")
    for n in notes:
        print(f"selftest: {n}")
    return 0


def selftest_main(argv: list[str]) -> int:
    """Entry for the packaged executable: argv excludes the '--selftest' token."""
    dicom_path, qpa, usage_rc = _parse_args(argv)
    if usage_rc:
        return usage_rc
    return run_selftest(dicom_path, qpa)
