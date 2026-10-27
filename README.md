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

The app opens and displays DICOM images in its bundled viewer (dcm_mini_viewer). Uncompressed transfer syntaxes (Explicit and Implicit VR Little Endian) and RLE Lossless render out of the box: the RLE decoder ships inside pydicom and needs only numpy, which is a dependency and is included in the packaged builds.

Known limitation: the compressed syntaxes that depend on external codecs — JPEG Baseline, JPEG 2000 (including JPEG 2000 Lossless), and JPEG-LS — are not decodable out of the box: pydicom decodes them only when extra decoder packages (such as pylibjpeg with its plugins, or GDCM) are installed, and those packages are not dependencies today. Files in those syntaxes still open for tag editing; their pixel data will not render. Stuart has accepted this limitation for now; decoding compressed images is not planned for this release.
