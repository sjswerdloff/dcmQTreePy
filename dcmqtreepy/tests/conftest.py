"""Common fixtures and utilities for DICOM-related tests."""

import json
import os
import re
import tempfile

import pytest


@pytest.fixture
def valid_vrs():
    """Return a set of valid DICOM Value Representations."""
    return {
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
    }


@pytest.fixture
def valid_vm_patterns():
    """Return a list of valid VM (Value Multiplicity) regex patterns."""
    return [
        r"^\d+$",  # Single number like "1"
        r"^\d+-\d+$",  # Range like "1-3"
        r"^\d+-n$",  # Range to infinity like "1-n"
        r"^\d+-\d+n$",  # Range to multiple of infinity like "2-2n"
    ]


@pytest.fixture
def sample_private_dict_data():
    """Return sample private dictionary data for testing."""
    return [
        {
            "Test Creator": {
                "0x300B0001": ["CS", "1", "Test Element", ""],
                "0x300B0002": ["DS", "2", "Test Element 2", ""],
            }
        },
        {
            "Invalid Creator": {
                "0x30000001": ["CS", "1", "Invalid Element", ""],
            }
        },
        {"Empty Creator": {}},
    ]


@pytest.fixture
def sample_json_file(sample_private_dict_data):
    """Create a temporary JSON file with sample private dictionary data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
        json.dump(sample_private_dict_data, temp_file)
        temp_path = temp_file.name

    yield temp_path

    # Cleanup after tests
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def assert_valid_tag_format():
    """Return a function to check if a tag has valid format."""

    def _assert_valid_tag_format(tag, vendor=None):
        # Tags should be in the format 0xGGGGEEEE where GGGG is the group and EEEE is the element
        group = tag >> 16
        element = tag & 0xFFFF

        # Private tags should have odd-numbered groups
        assert group % 2 == 1, f"Tag {hex(tag)} in {vendor or 'dictionary'} does not have an odd group number"

        # Element should be in a valid private element range
        private_creator_block = (element & 0xFF00) >> 8
        private_element = element & 0x00FF

        # Most private elements should have creator blocks between 0x10 and 0xFF
        assert (
            0x10 <= private_creator_block <= 0xFF or private_creator_block == 0x00
        ), f"Tag {hex(tag)} in {vendor or 'dictionary'} has unusual private creator block {private_creator_block:02X}"

        # Private elements should be between 0x00 and 0xFF
        assert (
            0x00 <= private_element <= 0xFF
        ), f"Tag {hex(tag)} in {vendor or 'dictionary'} has unusual private element {private_element:02X}"

    return _assert_valid_tag_format


@pytest.fixture
def assert_valid_dict_attributes():
    """Return a function to check if dictionary attributes have valid structure."""

    def _assert_valid_dict_attributes(tag, attributes, vendor=None, valid_vrs=None):
        # Attributes should be a tuple of 4 strings: VR, VM, name, retired flag
        assert isinstance(attributes, tuple), f"Attributes for tag {tag} in {vendor or 'dictionary'} is not a tuple"
        assert len(attributes) == 4, f"Attributes for tag {tag} in {vendor or 'dictionary'} doesn't have 4 elements"

        vr, vm, name, retired = attributes
        assert isinstance(vr, str), f"VR for tag {tag} in {vendor or 'dictionary'} is not a string"
        assert isinstance(vm, str), f"VM for tag {tag} in {vendor or 'dictionary'} is not a string"
        assert isinstance(name, str), f"Name for tag {tag} in {vendor or 'dictionary'} is not a string"
        assert isinstance(retired, str), f"Retired flag for tag {tag} in {vendor or 'dictionary'} is not a string"

        # Check VR is valid if valid_vrs is provided
        if valid_vrs:
            assert vr in valid_vrs, f"VR '{vr}' for tag {hex(tag)} is not a valid DICOM VR"

    return _assert_valid_dict_attributes


@pytest.fixture
def assert_valid_vm_format():
    """Return a function to check if VM has valid format."""

    def _assert_valid_vm_format(tag, vm, vendor=None, patterns=None):
        if not patterns:
            patterns = [
                r"^\d+$",  # Single number like "1"
                r"^\d+-\d+$",  # Range like "1-3"
                r"^\d+-n$",  # Range to infinity like "1-n"
                r"^\d+-\d+n$",  # Range to multiple of infinity like "2-2n"
            ]

        # Check if VM matches any of the valid patterns
        valid_format = any(re.match(pattern, vm) for pattern in patterns)
        assert valid_format, f"VM '{vm}' for tag {hex(tag)} in {vendor or 'dictionary'} has invalid format"

    return _assert_valid_vm_format
