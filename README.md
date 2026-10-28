dcmQTreePy

A multi-platform DICOM object Editor

An homage to DCMTree from IMPAC &reg;

Requirements:

Python 3.12, 3.13 or 3.14, on one of these systems (the oldest that PySide6 6.12.0's wheels support):

- macOS 14 Sonoma or later (Apple silicon or Intel)
- Linux x86_64 with glibc 2.34 or later (for example Ubuntu 22.04, RHEL 9), or Linux aarch64 with glibc 2.39 or later (for example Ubuntu 24.04)
- Windows, x64 or ARM64

macOS 13 and older, and older Linux such as RHEL 8 or Ubuntu 20.04, cannot install it.

Installation:

git clone https://github.com/sjswerdloff/dcmQTreePy.git

or

git clone git@github.com:sjswerdloff/dcmQTreePy.git

cd dcmQTreePy

Install uv (https://docs.astral.sh/uv/), then create the project environment (uv creates .venv automatically):

uv sync --dev

uv run python dcmqtreepy/dcmQTree.py

or

uv run streamlit run streamlit_dicom_viewer (if you want a web based editor)

Image viewing and transfer syntaxes:

The app opens and displays DICOM images in its bundled viewer (dcm_mini_viewer). Uncompressed transfer syntaxes (Explicit and Implicit VR Little Endian) and RLE Lossless render out of the box: the RLE decoder ships inside pydicom and needs nothing beyond numpy, which is a declared dependency and is included in the packaged builds. JPEG Baseline also renders whenever Pillow is present — in a source install it is, pulled in transitively by streamlit — but Pillow is not a declared dependency of this project, and whether the packaged builds include it is unverified. JPEG 2000 (including Lossless) renders, signed images included: pylibjpeg and pylibjpeg-openjpeg are declared dependencies. pydicom 2.4.5 tries Pillow first, whose handler fails on signed images with an int16 OverflowError under numpy 2, and then falls back to pylibjpeg-openjpeg (issue #39). The packaged builds' self-test decodes a signed JPEG 2000 image, so a build that loses the decoder fails its release check.

Known limitations:

- The syntaxes whose decoders live only in optional packages — JPEG Lossless (Non-Hierarchical, including the First-Order Prediction SV1 form) and JPEG-LS — do not render out of the box: pydicom selects no handler for them without the pylibjpeg-libjpeg plugin or GDCM. pylibjpeg-libjpeg is GPL-3.0, so this Apache-2.0 app does not declare it.
- JPEG Baseline renders when Pillow is present (in a source install, only via streamlit; not declared; unverified in packaged builds) — except some RGB-declared files, which fail with an AttributeError under pydicom 2.4.5 and Pillow 13 (its Pillow handler predates Pillow 13's read-only image.mode; issue #40). pydicom's fallback for these is also pylibjpeg-libjpeg, the GPL-3.0 plugin above; pylibjpeg-openjpeg does not decode JPEG Baseline.
- JPEG Extended is registered with Pillow too, so Pillow is chosen as its decoder: 8-bit Extended takes the handler's supported path and is expected to render, though no 8-bit sample has been tested here; pydicom's only bundled Extended files are 12-bit (`JPEG-lossy.dcm`, `JPGExtended.dcm`, BitsStored 12), and 12-bit Extended fails in pydicom 2.4.5 with NotImplementedError.

Files in non-rendering syntaxes still open for tag editing; their pixel data will not display. Stuart has accepted these limitations for now; adding compressed decoding is not planned for this release.
