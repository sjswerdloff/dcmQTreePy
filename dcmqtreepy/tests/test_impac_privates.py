"""Unit tests for impac_privates.py"""


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


def test_impac_dict_values(assert_valid_dict_attributes):
    """Test the values in the IMPAC dictionary."""
    # Use the fixture to validate dict attributes
    for tag, attributes in impac_private_dict.items():
        assert_valid_dict_attributes(tag, attributes, vendor="IMPAC")


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
        assert private_creator_block in [
            0x10,
            0x00,
        ], f"Tag {hex(tag)} has unusual private creator block {private_creator_block:02X}"

        # Private elements should be between 0x01 and 0xFF
        assert 0x01 <= private_element <= 0xFF, f"Tag {hex(tag)} has unusual private element {private_element:02X}"


@pytest.mark.parametrize(
    "tag, expected_attributes",
    [
        (0x300B1001, ("FL", "1", "Distal Target Distance Tolerance", "")),
        (0x300B1002, ("FL", "1", "Maximum Collimated Field Diameter", "")),
        (0x300B1003, ("CS", "1", "Beam Check Flag", "")),
    ],
)
def test_specific_impac_entries_parameterized(tag, expected_attributes):
    """Test specific entries in the IMPAC dictionary to ensure data integrity."""
    assert impac_private_dict[tag] == expected_attributes


def test_impac_entries_vr_validity(valid_vrs):
    """Check that all VRs in the IMPAC dictionary are valid DICOM Value Representations."""
    for tag, attributes in impac_private_dict.items():
        vr = attributes[0]
        assert vr in valid_vrs, f"VR '{vr}' for tag {hex(tag)} is not a valid DICOM VR"


def test_value_multiplicity_format(valid_vm_patterns, assert_valid_vm_format):
    """Test that VM (Value Multiplicity) entries are correctly formatted."""
    for tag, attributes in impac_private_dict.items():
        vm = attributes[1]
        assert_valid_vm_format(tag, vm, vendor="IMPAC", patterns=valid_vm_patterns)
