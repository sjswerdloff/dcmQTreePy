"""Unit tests for import_hex_legible_private_element_lists.py"""

import json

import pytest

from dcmqtreepy.import_hex_legible_private_element_lists import (
    _filter_creators,
    _pydicom_private_dicts_from_json,
    generate_python_code_from_private_dict_list,
    jsonify_pydicom_private_dict_list,
    pydicom_private_dicts_from_json,
    wrap_in_single_quotes,
)


def test_wrap_in_single_quotes():
    """Test the wrap_in_single_quotes function."""
    assert wrap_in_single_quotes("test") == "'test'"
    assert wrap_in_single_quotes("") == "''"
    assert wrap_in_single_quotes("string with spaces") == "'string with spaces'"


def test_pydicom_private_dicts_from_json(sample_json_file):
    """Test loading private dictionaries from JSON file."""
    result = pydicom_private_dicts_from_json(sample_json_file)

    # Only the valid creator should be present
    assert len(result) == 1
    assert "Test Creator" in result
    assert "Invalid Creator" not in result
    assert "Empty Creator" not in result

    # Check the structure of the loaded dictionary
    test_dict = result["Test Creator"]
    assert isinstance(test_dict, dict)
    assert 0x300B0001 in test_dict
    assert 0x300B0002 in test_dict

    # Check the values
    assert test_dict[0x300B0001] == ["CS", "1", "Test Element", ""]
    assert test_dict[0x300B0002] == ["DS", "2", "Test Element 2", ""]


def test_internal_pydicom_private_dicts_from_json(sample_json_file):
    """Test the internal _pydicom_private_dicts_from_json function."""
    result = _pydicom_private_dicts_from_json(sample_json_file)

    # All creators should be present in the unfiltered result
    assert len(result) == 3
    assert "Test Creator" in result
    assert "Invalid Creator" in result
    assert "Empty Creator" in result

    # Check that the keys are converted to integers
    test_dict = result["Test Creator"]
    assert 0x300B0001 in test_dict
    assert 0x300B0002 in test_dict


def test_filter_creators(sample_private_dict_data):
    """Test the _filter_creators function."""
    unfiltered_dict = {
        "Valid Creator": {
            0x300B0001: ["CS", "1", "Valid Element", ""],
        },
        "Invalid Creator": {
            0x30000001: ["CS", "1", "Invalid Element", ""],
        },
        "Empty Creator": {},
    }

    filtered_dict = _filter_creators(unfiltered_dict)

    # Only the valid creator should remain
    assert len(filtered_dict) == 1
    assert "Valid Creator" in filtered_dict
    assert "Invalid Creator" not in filtered_dict
    assert "Empty Creator" not in filtered_dict


def test_generate_python_code_from_private_dict_list():
    """Test generating Python code from private dictionaries."""
    private_dict_list = [
        {
            "Test Creator": {
                0x300B0001: ["CS", "1", "Test Element", ""],
                0x300B0002: ["DS", "2", "Test Element 2", ""],
            }
        }
    ]

    python_code = generate_python_code_from_private_dict_list(private_dict_list)

    # Check that the generated code contains the expected elements
    assert "from typing import Dict, Tuple" in python_code
    assert "new_private_dictionaries: Dict[str, Dict[str, Tuple[str, str, str, str]]] = {" in python_code
    assert "'Test Creator'" in python_code
    assert "0x300B0001" in python_code
    assert "0x300B0002" in python_code
    assert "'CS'" in python_code
    assert "'DS'" in python_code
    assert "'Test Element'" in python_code
    assert "'Test Element 2'" in python_code


def test_generate_python_code_for_pydicom_pr():
    """Test generating Python code for pydicom PR format."""
    private_dict_list = [
        {
            "Test Creator": {
                0x300B0001: ["CS", "1", "Test Element", ""],
            }
        }
    ]

    python_code = generate_python_code_from_private_dict_list(private_dict_list, for_pydicom_pr=True)

    # Check that the format is correct for pydicom PR (using xxxx format)
    assert "'300Bxx01'" in python_code


def test_jsonify_pydicom_private_dict_list(sample_private_dict_data):
    """Test converting Python dictionaries to JSON format."""
    private_dict_list = [
        {
            "Test Creator": {
                0x300B0001: ["CS", "1", "Test Element", ""],
                0x300B0002: ["DS", "2", "Test Element 2", ""],
            }
        }
    ]

    jsonified_list = jsonify_pydicom_private_dict_list(private_dict_list)

    # Check the structure of the returned list
    assert isinstance(jsonified_list, list)
    assert len(jsonified_list) == 1

    # Check that the tag keys are converted to hex strings
    assert "Test Creator" in jsonified_list[0]
    creator_dict = jsonified_list[0]["Test Creator"]
    assert "0x300B0001" in creator_dict
    assert "0x300B0002" in creator_dict

    # Check the values remain the same
    assert creator_dict["0x300B0001"] == ["CS", "1", "Test Element", ""]
    assert creator_dict["0x300B0002"] == ["DS", "2", "Test Element 2", ""]
