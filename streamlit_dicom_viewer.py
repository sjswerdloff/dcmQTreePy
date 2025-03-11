import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import pydicom
import streamlit as st
from pydicom import DataElement, Dataset, Sequence
from pydicom.valuerep import VR


def make_state_key(key_type: str, path: str) -> str:
    """
    Create a flat state key for any UI element.
    key_type: Type of state (e.g., 'expanded', 'selected', 'value')
    path: Path in DICOM hierarchy (e.g., '00080020_item_1')
    """
    return f"state_{key_type}_{path}"


def get_state(key_type: str, path: str, default: any = None) -> any:
    """Get state value with default if not set."""
    key = make_state_key(key_type, path)
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def set_state(key_type: str, path: str, value: any):
    """Set state value."""
    key = make_state_key(key_type, path)
    st.session_state[key] = value


def format_tag(tag) -> str:
    """Format DICOM tag as 8-character hex string."""
    return f"{tag:08x}"


def load_private_dictionaries():
    """Load private DICOM dictionaries."""
    try:
        from dcmqtreepy.impac_privates import impac_private_dict
        from dcmqtreepy.new_privates import new_private_dictionaries

        for creator, private_dict in new_private_dictionaries.items():
            try:
                pydicom.datadict.add_private_dict_entries(creator, private_dict)
            except ValueError as e:
                logging.error(f"Failed to load private dictionary for {creator}: {e}")
    except ImportError as e:
        logging.warning(f"Could not load private dictionaries: {e}")


def format_dicom_element(elem: DataElement) -> Optional[Dict]:
    """Format a DICOM element for display."""
    if elem.VR == VR.SQ:
        return None

    value = ""
    if elem.VR not in [VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF]:
        value = str(elem.value) if elem.value is not None else ""

    return {"tag": format_tag(elem.tag), "name": elem.name, "value": value, "vr": str(elem.VR), "keyword": elem.keyword}


def display_sequence(elem: DataElement, path: str, level: int = 0) -> None:
    """
    Display a DICOM sequence with expandable items.
    Uses flat state management for expansion and selection.
    """
    is_expanded = get_state("expanded", path, False)
    is_selected = get_state("selected", path, False)

    # Sequence header with indent and visual container
    with st.container():
        # Add left border and padding for visual hierarchy
        st.markdown(
            f"""
            <div style="
                border-left: 2px solid #e0e0e0;
                margin-left: {level * 20}px;
                padding-left: 10px;
                background-color: #f8f9fa;
                border-radius: 4px;
            ">
            </div>
            """,
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns([8, 2])

        with col1:
            if st.button(
                f"{'  ' * level}{'▼' if is_expanded else '▶'} {elem.name} (Sequence)",
                key=f"btn_{path}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                set_state("expanded", path, not is_expanded)

        with col2:
            if st.button("Select", key=f"sel_{path}"):
                # Clear all other selections
                for key in st.session_state:
                    if key.startswith("state_selected_"):
                        st.session_state[key] = False
                set_state("selected", path, True)

        # Display sequence items if expanded
        if is_expanded:
            for idx, item in enumerate(elem.value):
                item_path = f"{path}_item_{idx}"
                item_expanded = get_state("expanded", item_path, False)
                item_selected = get_state("selected", item_path, False)

                # Add visual container for items with increased indent
                st.markdown(
                    f"""
                    <div style="
                        border-left: 2px solid #90caf9;
                        margin-left: {(level + 1) * 20}px;
                        padding-left: 10px;
                        background-color: #f5f5f5;
                        border-radius: 4px;
                        margin-top: 4px;
                        margin-bottom: 4px;
                    ">
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                item_col1, item_col2 = st.columns([8, 2])

                with item_col1:
                    if st.button(
                        f"{'  ' * (level + 1)}{'▼' if item_expanded else '▶'} Item {idx + 1}",
                        key=f"btn_{item_path}",
                        use_container_width=True,
                        type="primary" if item_selected else "secondary",
                    ):
                        set_state("expanded", item_path, not item_expanded)

                with item_col2:
                    if st.button("Select", key=f"sel_{item_path}"):
                        # Clear all other selections
                        for key in st.session_state:
                            if key.startswith("state_selected_"):
                                st.session_state[key] = False
                        set_state("selected", item_path, True)

                # Display item contents if expanded
                if item_expanded:
                    display_dataset(item, item_path, level + 2)


def get_selected_dataset() -> Optional[Union[Dataset, DataElement]]:
    """Get currently selected dataset or sequence item."""
    selected_path = None

    # Find the selected path
    for key in st.session_state:
        if key.startswith("state_selected_") and st.session_state[key]:
            selected_path = key.replace("state_selected_", "")
            break

    if not selected_path or not st.session_state.get("current_dataset"):
        return st.session_state.get("current_dataset")

    # Navigate to selected dataset
    current = st.session_state["current_dataset"]
    path_parts = selected_path.split("_")

    try:
        for i in range(0, len(path_parts), 3):
            if i + 2 < len(path_parts) and path_parts[i + 1] == "item":
                tag = int(path_parts[i], 16)
                idx = int(path_parts[i + 2])
                current = current[tag].value[idx]
            elif i < len(path_parts):
                tag = int(path_parts[i], 16)
                current = current[tag]
    except Exception:
        return st.session_state.get("current_dataset")

    return current


def display_dataset(dataset: Dataset, path: str = "", level: int = 0) -> None:
    """Display DICOM dataset with editable fields."""
    for elem in dataset:
        current_path = f"{path}_{format_tag(elem.tag)}" if path else format_tag(elem.tag)

        if elem.VR != VR.SQ:
            elem_data = format_dicom_element(elem)
            if elem_data:
                # Container for the entire row
                st.markdown(
                    f"""
                    <div style="
                        margin-left: {level * 20}px;
                        padding: 2px 0;
                    ">
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Adjusted column widths to prevent overlap
                col1, col2, col3, col4 = st.columns([2.5, 3.5, 3.5, 1.5])

                with col1:
                    st.markdown(
                        f"""
                        <div style="
                            font-family: monospace;
                            padding: 8px 4px;
                            white-space: nowrap;
                            overflow: hidden;
                            text-overflow: ellipsis;
                        ">
                            {elem_data["tag"]}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.markdown(
                        f"""
                        <div style="
                            padding: 8px 4px;
                            white-space: nowrap;
                            overflow: hidden;
                            text-overflow: ellipsis;
                        ">
                            {elem_data["name"]}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col3:
                    if elem.VR not in [VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF]:
                        value_key = make_state_key("value", current_path)
                        new_value = st.text_input(
                            f"Value_{current_path}", value=elem_data["value"], key=value_key, label_visibility="collapsed"
                        )
                        if new_value != elem_data["value"]:
                            try:
                                elem.value = new_value
                                set_state("modified", "", True)
                            except Exception as e:
                                st.error(f"Error updating value: {str(e)}")
                with col4:
                    st.markdown(
                        f"""
                        <div style="
                            padding: 8px 4px;
                            text-align: center;
                        ">
                            {elem_data["vr"]}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            display_sequence(elem, current_path, level)


def add_element_to_sequence(sequence: DataElement, tag: int, vr: str, value: str) -> None:
    """Add a new sequence item with the given element."""
    new_dataset = Dataset()
    new_element = DataElement(tag, vr, value)
    new_dataset.add(new_element)
    sequence.value.append(new_dataset)


def add_element_ui():
    """UI for adding new DICOM elements."""
    st.subheader("Add DICOM Element")

    # Get selected location and display context
    selected_path = None
    selected_type = None

    for key in st.session_state:
        if key.startswith("state_selected_") and st.session_state[key]:
            selected_path = key.replace("state_selected_", "")
            if "_item_" in selected_path:
                selected_type = "item"
            else:
                selected_type = "sequence"
            break

    # Show appropriate context message
    if selected_type == "sequence":
        st.info("Adding new sequence item to selected sequence")
    elif selected_type == "item":
        st.info("Adding element to selected sequence item")
    else:
        st.info("Adding to root dataset")

    col1, col2 = st.columns(2)
    with col1:
        group = st.text_input("Group (hex)", "0008")
    with col2:
        element = st.text_input("Element (hex)", "0020")

    vr = st.selectbox(
        "Value Representation (VR)",
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
    )

    value = st.text_area("Value")

    if st.button("Add Element"):
        try:
            tag = int(group + element, 16)
            new_element = DataElement(tag, vr, value)

            if selected_type == "sequence":
                # Navigate to the selected sequence
                current = st.session_state["current_dataset"]
                path_parts = selected_path.split("_")
                for i in range(0, len(path_parts), 3):
                    if i < len(path_parts):
                        current = current[int(path_parts[i], 16)]
                # Add new sequence item with element
                add_element_to_sequence(current, tag, vr, value)
                st.success("Added new sequence item with element")

            elif selected_type == "item":
                # Navigate to the selected item
                current = st.session_state["current_dataset"]
                path_parts = selected_path.split("_")
                for i in range(0, len(path_parts), 3):
                    if i + 2 < len(path_parts) and path_parts[i + 1] == "item":
                        seq_tag = int(path_parts[i], 16)
                        item_idx = int(path_parts[i + 2])
                        current = current[seq_tag].value[item_idx]
                # Add element to existing item
                current.add(new_element)
                st.success("Added element to sequence item")

            else:
                # Adding to root dataset
                if vr == "SQ":
                    # Creating a new empty sequence
                    new_element.value = []
                st.session_state["current_dataset"].add(new_element)
                st.success("Added element to root dataset")

            set_state("modified", "", True)

        except Exception as e:
            st.error(f"Error adding element: {str(e)}")
        except Exception as e:
            st.error(f"Error adding element: {str(e)}")


def save_dataset(dataset: Dataset, filepath: str) -> None:
    """Save DICOM dataset to file."""
    try:
        dataset.ensure_file_meta()
        dataset.is_implicit_VR = False
        dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
        pydicom.dcmwrite(filepath, dataset, write_like_original=False)
        set_state("modified", "", False)
        st.success(f"Successfully saved to {filepath}")
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")


def main():
    st.title("DICOM Viewer")

    # Load private dictionaries
    load_private_dictionaries()

    # File upload handling
    uploaded_files = st.file_uploader("Choose DICOM file(s)", accept_multiple_files=True, type=["dcm"])

    # Track loaded files
    if "loaded_files" not in st.session_state:
        st.session_state["loaded_files"] = []

    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state["loaded_files"]:
                st.session_state["loaded_files"].append(uploaded_file.name)
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())

    # File selection and display
    if st.session_state["loaded_files"]:
        selected_file = st.selectbox("Select file to view", st.session_state["loaded_files"])

        if selected_file:
            if get_state("modified", "", False) and not st.warning("You have unsaved changes. Do you want to continue?"):
                return


            try:
                dataset = pydicom.dcmread(selected_file, force=True)
                st.session_state["current_dataset"] = dataset

                st.subheader("DICOM Elements")
                display_dataset(dataset)

                # Save options
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save"):
                        save_dataset(dataset, selected_file)
                with col2:
                    save_as = st.text_input("Save as:", selected_file + "_new")
                    if st.button("Save As"):
                        save_dataset(dataset, save_as)

                # Add element section
                add_element_ui()

            except Exception as e:
                st.error(f"Error reading file: {str(e)}")


if __name__ == "__main__":
    main()
