dcmQTreePy

A multi-platform DICOM object Editor

An homage to DCMTree from IMPAC &reg;

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
