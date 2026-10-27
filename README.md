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

The app opens and displays DICOM images in its bundled viewer (dcm_mini_viewer). Uncompressed transfer syntaxes (Explicit and Implicit VR Little Endian) and RLE Lossless render out of the box: the RLE decoder ships inside pydicom and needs nothing beyond numpy, which is a declared dependency and is included in the packaged builds. JPEG Baseline also renders whenever Pillow is present — in a source install it is, pulled in transitively by streamlit — but Pillow is not a declared dependency of this project, and whether the packaged builds include it is unverified.

Known limitations:

- The syntaxes whose decoders live only in optional packages — JPEG Extended, JPEG Lossless (Non-Hierarchical, including the First-Order Prediction SV1 form), and JPEG-LS — do not render out of the box. pydicom decodes them only when extra decoder packages (such as pylibjpeg with its plugins, or GDCM) are installed, and those packages are not dependencies today.
- JPEG Baseline renders when Pillow is present, but only if the encoder
  declared the color space correctly (a PhotometricInterpretation of YBR_RCT):
  some camera and DCMTK-encoded Baseline files misdeclare it as
  MONOCHROME2/YBR_FULL_422 and fail to decode even with Pillow installed.
- JPEG 2000 (including Lossless) is different: Pillow is chosen as the decoder when present but currently fails on signed images with an int16 OverflowError under numpy 2 (tracked in issue #39), and no other handler is installed for it.

Files in non-rendering syntaxes still open for tag editing; their pixel data will not display. Stuart has accepted these limitations for now; adding compressed decoding is not planned for this release.
