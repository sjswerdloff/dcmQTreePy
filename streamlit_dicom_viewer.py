import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

import pydicom
import streamlit as st
from pydicom import DataElement, Dataset, Sequence
from pydicom.valuerep import VR

# Initialize session state
if "current_dataset" not in st.session_state:
    st.session_state.current_dataset = None
if "loaded_files" not in st.session_state:
    st.session_state.loaded_files = []
if "has_edits" not in st.session_state:
    st.session_state.has_edits = False
if "private_creators" not in st.session_state:
    st.session_state.private_creators = {}
if "selected_location" not in st.session_state:
    st.session_state.selected_location = None


def load_private_dictionaries():
    """Load private DICOM dictionaries."""
    from dcmqtreepy.impac_privates import impac_private_dict
    from dcmqtreepy.new_privates import new_private_dictionaries

    for creator, private_dict in new_private_dictionaries.items():
        try:
            pydicom.datadict.add_private_dict_entries(creator, private_dict)
            logging.warning(f"Private dictionary for {creator} has been loaded")
        except ValueError:
            logging.error(f"Unable to load private dictionary for {creator}")


def format_dicom_element(elem: DataElement) -> dict:
    """Format a DICOM element for display."""
    if elem.VR != VR.SQ:
        value = ""
        if elem.VR not in [VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF]:
            value = str(elem.value) if elem.value is not None else ""

        return {"tag": str(elem.tag), "name": elem.name, "value": value, "vr": str(elem.VR), "keyword": elem.keyword}
    return None


def format_sequence_element(elem: DataElement, sequence_index: int) -> dict:
    """Format a sequence element for display."""
    return {
        "tag": str(elem.tag),
        "name": elem.name,
        "value": f"Sequence Item {sequence_index + 1}",
        "vr": str(elem.VR),
        "keyword": elem.keyword,
    }


def display_sequence(elem: DataElement, level: int, current_path: str, sequence_dataset=None) -> None:
    """Display a sequence and its items using buttons for expansion."""
    # Use more specific keys to prevent conflicts
    seq_key = f"sequence_{current_path}"

    # Initialize sequence state if not present
    if seq_key not in st.session_state:
        st.session_state[seq_key] = {"expanded": False, "items": {}}

    # Create column layout for sequence header
    col1, col2 = st.columns([8, 1])

    # Display sequence header and expansion button
    with col1:
        expanded = st.session_state[seq_key]["expanded"]
        if st.button(
            f"{'  ' * level}{'▼' if expanded else '▶'} {elem.name} (Sequence)",
            key=f"btn_seq_{current_path}",
            use_container_width=True,
            type="primary" if expanded else "secondary",
        ):
            st.session_state[seq_key]["expanded"] = not expanded

    # Display sequence selection button
    with col2:
        if st.button("Select", key=f"sel_seq_{current_path}"):
            st.session_state.selected_location = {"type": "sequence", "element": elem, "path": current_path}

    # If sequence is expanded, show its items
    if st.session_state[seq_key]["expanded"]:
        # Container for sequence items
        with st.container():
            for idx, sequence_item in enumerate(elem.value):
                # Initialize item state if not present
                item_key = f"item_{current_path}_{idx}"
                if item_key not in st.session_state[seq_key]["items"]:
                    st.session_state[seq_key]["items"][item_key] = False

                # Create columns for item header
                item_col1, item_col2 = st.columns([8, 1])

                # Display item header and expansion button
                with item_col1:
                    item_expanded = st.session_state[seq_key]["items"][item_key]
                    if st.button(
                        f"{'  ' * (level + 1)}{'▼' if item_expanded else '▶'} Item {idx + 1}",
                        key=f"btn_{item_key}",
                        use_container_width=True,
                        type="primary" if item_expanded else "secondary",
                    ):
                        st.session_state[seq_key]["items"][item_key] = not item_expanded

                # Display item selection button
                with item_col2:
                    if st.button("Select", key=f"sel_{item_key}"):
                        st.session_state.selected_location = {
                            "type": "item",
                            "dataset": sequence_item,
                            "path": f"{current_path}_{idx}",
                        }

                # If item is expanded, show its contents
                if st.session_state[seq_key]["items"][item_key]:
                    with st.container():
                        st.markdown("---")
                        display_dataset(sequence_item, level + 2, f"{current_path}_{idx}")
                        st.markdown("---")


def display_dataset(dataset: Dataset, level: int = 0, parent_path: str = "") -> None:
    """Display DICOM dataset in a hierarchical structure."""
    for elem in dataset:
        current_path = f"{parent_path}_{elem.tag}" if parent_path else str(elem.tag)

        if elem.VR != VR.SQ:
            elem_data = format_dicom_element(elem)
            if elem_data:
                col1, col2, col3, col4 = st.columns([2, 3, 4, 2])
                with col1:
                    st.text("  " * level + elem_data["tag"])
                with col2:
                    st.text(elem_data["name"])
                with col3:
                    # Make the value editable if it's not a binary VR
                    if elem.VR not in [VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF]:
                        new_value = st.text_input(
                            f"Value_{elem_data['tag']}",
                            value=elem_data["value"],
                            key=f"value_{current_path}",
                            label_visibility="collapsed",
                        )
                        if new_value != elem_data["value"]:
                            try:
                                elem.value = new_value
                                st.session_state.has_edits = True
                            except Exception as e:
                                st.error(f"Error updating value: {str(e)}")
                with col4:
                    st.text(elem_data["vr"])
        else:
            # Handle sequences with button-based expansion
            display_sequence(elem, level, current_path)


def save_dataset(dataset: Dataset, filepath: str) -> None:
    """Save DICOM dataset to file."""
    try:
        dataset.ensure_file_meta()
        dataset.is_implicit_VR = False
        dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
        pydicom.dcmwrite(filepath, dataset, write_like_original=False)
        st.session_state.has_edits = False
        st.success(f"Successfully saved to {filepath}")
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")


def add_element_ui():
    """UI for adding new DICOM elements."""
    st.subheader("Add DICOM Element")

    # Input fields for new element
    group = st.text_input("Group (hex)", "0008", key="add_elem_group")
    element = st.text_input("Element (hex)", "0020", key="add_elem_element")
    vr = st.selectbox(
        "VR",
        [
            "AE",
            "AS",
            "AT",
            "CS",
            "DA",
            "DS",
            "DT",
            "FL",
            "FD",
            "IS",
            "LO",
            "LT",
            "OB",
            "OD",
            "OF",
            "OW",
            "PN",
            "SH",
            "SL",
            "SQ",
            "SS",
            "ST",
            "TM",
            "UI",
            "UL",
            "UN",
            "US",
            "UT",
        ],
        key="add_elem_vr",
    )
    value = st.text_area("Value", key="add_elem_value")

    # Show current selection status
    if st.session_state.selected_location:
        if st.session_state.selected_location["type"] == "sequence":
            st.info("Will add as new item to selected sequence")
        else:
            st.info("Will add to selected sequence item")
    else:
        st.info("Will add to root dataset")

    if st.button("Add Element", key="add_elem_button"):
        try:
            tag = int(group + element, 16)
            new_element = DataElement(tag, vr, value)

            if st.session_state.selected_location:
                if st.session_state.selected_location["type"] == "sequence":
                    # Add as new item to sequence
                    sequence = st.session_state.selected_location["element"]
                    new_dataset = Dataset()
                    new_dataset.add(new_element)
                    sequence.value.append(new_dataset)
                else:
                    # Add to existing sequence item
                    target_dataset = st.session_state.selected_location["dataset"]
                    target_dataset.add(new_element)
            else:
                # Add to root dataset
                st.session_state.current_dataset.add(new_element)

            st.session_state.has_edits = True
            st.success("Element added successfully")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error adding element: {str(e)}")


def main():
    st.title("DICOM Viewer")

    # Initialize private dictionaries
    load_private_dictionaries()

    # File upload
    uploaded_files = st.file_uploader("Choose DICOM file(s)", accept_multiple_files=True, type=["dcm"])

    # Handle uploaded files
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.loaded_files:
                st.session_state.loaded_files.append(uploaded_file.name)
                # Save uploaded file temporarily
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())

    # File selection
    if st.session_state.loaded_files:
        selected_file = st.selectbox("Select file to view", st.session_state.loaded_files)

        if selected_file:
            if st.session_state.has_edits:
                if st.warning("You have unsaved changes. Do you want to continue?"):
                    st.session_state.has_edits = False
                else:
                    return

            try:
                # Clear all sequence and item states when loading a new file
                for key in list(st.session_state.keys()):
                    if key.startswith("seq_") or key.startswith("selected_"):
                        del st.session_state[key]

                dataset = pydicom.dcmread(selected_file, force=True)
                st.session_state.current_dataset = dataset

                # Display dataset
                st.subheader("DICOM Elements")
                display_dataset(dataset)

                # Save buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save"):
                        save_dataset(dataset, selected_file)
                with col2:
                    save_as = st.text_input("Save as:", selected_file + "_new")
                    if st.button("Save As"):
                        save_dataset(dataset, save_as)

                # Add element button
                if st.button("Add Element"):
                    add_element_ui()

            except Exception as e:
                st.error(f"Error reading file: {str(e)}")


if __name__ == "__main__":
    main()
