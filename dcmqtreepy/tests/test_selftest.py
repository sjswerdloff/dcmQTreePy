"""Unit tests for dcmqtreepy.selftest — the packaged-build smoke entry point.

connor's #34 review ask: selftest.py ships in the app but nothing in ordinary CI
runs it, so a break there would first surface on a release dispatch. These tests
run the same code path headless (Qt offscreen), off the pydicom sample in the
locked venv — the same file CI passes by path.

Not a substitute for the packaged run: this proves selftest.py itself works;
the release workflow's --selftest step proves the PyInstaller bundle does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dcmqtreepy.selftest import _parse_args, run_selftest, selftest_main


@pytest.fixture(scope="module")
def ct_small() -> Path:
    import pydicom

    sample = Path(pydicom.__file__).parent / "data" / "test_files" / "CT_small.dcm"
    if not sample.is_file():
        pytest.skip(f"pydicom sample missing at {sample}")
    return sample


class TestParseArgs:
    def test_path_platform_report(self, tmp_path):
        report = tmp_path / "r.txt"
        path, qpa, rep, rc = _parse_args(["a.dcm", "--platform", "offscreen", "--report", str(report)])
        assert rc == 0
        assert str(path) == "a.dcm"
        assert qpa == "offscreen"
        assert rep == report

    def test_platform_missing_value_is_usage_error(self):
        assert _parse_args(["--platform"])[3] == 2

    def test_report_missing_value_is_usage_error(self):
        assert _parse_args(["--report"])[3] == 2

    def test_unknown_option_is_usage_error(self):
        assert _parse_args(["--bogus"])[3] == 2

    def test_two_paths_is_usage_error(self):
        assert _parse_args(["a.dcm", "b.dcm"])[3] == 2


class TestSelftest:
    def test_passes_on_ct_small_offscreen(self, ct_small):
        assert run_selftest(ct_small, "offscreen") == 0

    def test_writes_report_file(self, ct_small, tmp_path):
        report = tmp_path / "sub" / "selftest.txt"
        rc = run_selftest(ct_small, "offscreen", report)
        assert rc == 0
        text = report.read_text(encoding="utf-8")
        assert "selftest OK" in text
        assert text.endswith("exit=0\n")

    def test_missing_file_exits_2(self, tmp_path):
        assert run_selftest(tmp_path / "nope.dcm", "offscreen") == 2

    def test_garbage_file_fails_loudly(self, tmp_path):
        junk = tmp_path / "garbage.dcm"
        junk.write_bytes(b"not a dicom file at all, just bytes")
        report = tmp_path / "garbage-report.txt"
        rc = run_selftest(junk, "offscreen", report)
        assert rc == 1
        text = report.read_text(encoding="utf-8")
        assert "selftest FAIL:" in text
        assert text.endswith("exit=1\n")

    def test_main_dispatch_and_catchall(self, ct_small):
        assert selftest_main([str(ct_small), "--platform", "offscreen"]) == 0
        assert selftest_main(["--bogus"]) == 2
