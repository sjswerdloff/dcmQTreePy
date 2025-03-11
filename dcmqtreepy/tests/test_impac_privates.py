"""Unit tests for impac_privates.py"""


import re

from dcmqtreepy.impac_privates import impac_private_dict


def test_impac_private_dict_structure():
    """Test the structure of the impac_private_dict dictionary."""
    # Check that the dictionary is properly formed
    assert isinstance(impac_private_dict, dict)
    assert len(impac_private_dict) > 0, "IMPAC private dictionary should not be empty"


def test_impac_dict_keys():
    """Test the keys in the IMPAC dictionary."""
    # Check a few known keys exist
    assert 0x300B1001 in impac_private_dict
    assert 0x300B1002 in impac_private_dict
    assert 0x300B1003 in impac_private_dict

    # All keys should be integers
    for tag in impac_private_dict.keys():
        assert isinstance(tag, int), f"Tag {tag} is not an integer"


def test_impac_dict_values():
    """Test the values in the IMPAC dictionary."""
    # Each entry should be a tuple of (VR, VM, name, retired flag)
    for tag, attributes in impac_private_dict.items():
        assert isinstance(attributes, tuple), f"Attributes for tag {tag} is not a tuple"
        assert len(attributes) == 4, f"Attributes for tag {tag} doesn't have 4 elements"

        vr, vm, name, retired = attributes
        assert isinstance(vr, str), f"VR for tag {tag} is not a string"
        assert isinstance(vm, str), f"VM for tag {tag} is not a string"
        assert isinstance(name, str), f"Name for tag {tag} is not a string"
        assert isinstance(retired, str), f"Retired flag for tag {tag} is not a string"


def test_impac_tag_format():
    """Test that all tags in the IMPAC private dictionary have the correct format."""
    for tag in impac_private_dict.keys():
        # Tags should be in the format 0xGGGGEEEE where GGGG is the group and EEEE is the element
        group = tag >> 16
        element = tag & 0xFFFF

        # IMPAC tags should be in group 300B or 3009
        assert group in (0x300B, 0x3009), f"Tag {hex(tag)} is not in group 300B or 3009"

        # Element should be in a valid private element range
        private_creator_block = (element & 0xFF00) >> 8
        private_element = element & 0x00FF

        # Most IMPAC private elements use block 0x10
        assert (
            private_creator_block == 0x10 or private_creator_block == 0x00
        ), f"Tag {hex(tag)} has unusual private creator block {private_creator_block:02X}"

        # Private elements should be between 0x01 and 0xFF
        assert 0x01 <= private_element <= 0xFF, f"Tag {hex(tag)} has unusual private element {private_element:02X}"


def test_specific_impac_entries():
    """Test specific entries in the IMPAC dictionary to ensure data integrity."""
    # Test a few known entries
    assert impac_private_dict[0x300B1001] == ("FL", "1", "Distal Target Distance Tolerance", "")
    assert impac_private_dict[0x300B1002] == ("FL", "1", "Maximum Collimated Field Diameter", "")
    assert impac_private_dict[0x300B1003] == ("CS", "1", "Beam Check Flag", "")

    # Check that VRs are valid DICOM Value Representations
    valid_vrs = {
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

    for tag, attributes in impac_private_dict.items():
        vr = attributes[0]
        assert vr in valid_vrs, f"VR '{vr}' for tag {hex(tag)} is not a valid DICOM VR"


def test_value_multiplicity_format():
    """Test that VM (Value Multiplicity) entries are correctly formatted."""
    valid_vm_patterns = [
        r"^\d+$",  # Single number like "1"
        r"^\d+-\d+$",  # Range like "1-3"
        r"^\d+-n$",  # Range to infinity like "1-n"
        r"^\d+-\d+n$",  # Range to multiple of infinity like "2-2n"
    ]

    for tag, attributes in impac_private_dict.items():
        vm = attributes[1]

        # Check if VM matches any of the valid patterns
        valid_format = any(re.match(pattern, vm) for pattern in valid_vm_patterns)

        assert valid_format, f"VM '{vm}' for tag {hex(tag)} has invalid format"
