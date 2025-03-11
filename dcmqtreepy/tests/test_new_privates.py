"""Unit tests for new_privates.py"""


import re

from dcmqtreepy.new_privates import new_private_dictionaries


def test_new_private_dictionaries_structure():
    """Test the structure of the new_private_dictionaries dictionary."""
    # Check that the dictionary is properly formed
    assert isinstance(new_private_dictionaries, dict)

    # Check that it contains the expected vendor entries
    expected_vendors = [
        "Accuray Robotic Control",
        "SagiPlan",
        "Brainlab - ONC - Beam Parameters",
        "Brainlab - ONC - Multi-axial treatment machine",
        "GEMS_PETD_01",
        "IBA",
        "IMPAC",
        "medPhoton 1.0",
        "Philips PET Private Group",
        "RAYSEARCHLABS 2.0",
        "SIEMENS MED SYNGO RT",
        "TOMO_DD_01",
        "TOMO_HA_01",
    ]
    for vendor in expected_vendors:
        assert vendor in new_private_dictionaries, f"Vendor {vendor} not found in new_private_dictionaries"


def test_vendor_dictionaries_format():
    """Test that each vendor dictionary has the correct format."""
    for vendor, vendor_dict in new_private_dictionaries.items():
        # Each vendor dictionary should be a dictionary of tag -> attributes
        assert isinstance(vendor_dict, dict), f"Vendor {vendor} dictionary is not a dict"

        # Check each tag entry
        for tag, attributes in vendor_dict.items():
            # Tag should be an integer
            assert isinstance(tag, int), f"Tag {tag} in {vendor} is not an integer"

            # Attributes should be a tuple of 4 strings: VR, VM, name, retired flag
            assert isinstance(attributes, tuple), f"Attributes for tag {tag} in {vendor} is not a tuple"
            assert len(attributes) == 4, f"Attributes for tag {tag} in {vendor} doesn't have 4 elements"

            vr, vm, name, retired = attributes
            assert isinstance(vr, str), f"VR for tag {tag} in {vendor} is not a string"
            assert isinstance(vm, str), f"VM for tag {tag} in {vendor} is not a string"
            assert isinstance(name, str), f"Name for tag {tag} in {vendor} is not a string"
            assert isinstance(retired, str), f"Retired flag for tag {tag} in {vendor} is not a string"


def test_tag_format():
    """Test that all tags in the private dictionaries have the correct format."""
    for vendor, vendor_dict in new_private_dictionaries.items():
        for tag in vendor_dict.keys():
            # Tags should be in the format 0xGGGGEEEE where GGGG is the group and EEEE is the element
            group = tag >> 16
            element = tag & 0xFFFF

            # Private tags should have odd-numbered groups
            assert group % 2 == 1, f"Tag {hex(tag)} in {vendor} does not have an odd group number"

            # Element should be in a valid private element range (0x0010-0x00FF)
            private_creator_block = (element & 0xFF00) >> 8
            private_element = element & 0x00FF

            # Most private elements should have creator blocks between 0x10 and 0xFF
            # The private creator itself would be (bb,00) where bb is the block
            assert (
                0x10 <= private_creator_block <= 0xFF or private_creator_block == 0x00
            ), f"Tag {hex(tag)} in {vendor} has unusual private creator block {private_creator_block:02X}"

            # Private elements should be between 0x00 and 0xFF
            # Note: 0x00 is allowed for creator elements (e.g. (gggg,10,00) is a valid private creator element)
            assert (
                0x00 <= private_element <= 0xFF
            ), f"Tag {hex(tag)} in {vendor} has unusual private element {private_element:02X}"


def test_specific_vendor_entries():
    """Test specific entries for each vendor to ensure data integrity."""
    # Test Accuray
    assert 0x300F1001 in new_private_dictionaries["Accuray Robotic Control"]
    assert new_private_dictionaries["Accuray Robotic Control"][0x300F1001][0] == "CS"  # VR
    assert new_private_dictionaries["Accuray Robotic Control"][0x300F1001][2] == "Use Increased Pitch Correction"  # Name

    # Test IMPAC
    assert 0x300B1001 in new_private_dictionaries["IMPAC"]
    assert new_private_dictionaries["IMPAC"][0x300B1001][0] == "FL"  # VR
    assert new_private_dictionaries["IMPAC"][0x300B1001][2] == "Distal Target Distance Tolerance"  # Name

    # Test Philips
    assert 0x70531000 in new_private_dictionaries["Philips PET Private Group"]
    assert new_private_dictionaries["Philips PET Private Group"][0x70531000][0] == "DS"  # VR
    assert new_private_dictionaries["Philips PET Private Group"][0x70531000][2] == "Philips SUV Scale Factor"  # Name

    # Test RAYSEARCHLABS
    assert 0x40011001 in new_private_dictionaries["RAYSEARCHLABS 2.0"]
    assert new_private_dictionaries["RAYSEARCHLABS 2.0"][0x40011001][0] == "DT"  # VR
    assert new_private_dictionaries["RAYSEARCHLABS 2.0"][0x40011001][2] == "Treatment Machine CommissionTime"  # Name


def test_value_multiplicity_format():
    """Test that VM (Value Multiplicity) entries are correctly formatted."""
    valid_vm_patterns = [
        r"^\d+$",  # Single number like "1"
        r"^\d+-\d+$",  # Range like "1-3"
        r"^\d+-n$",  # Range to infinity like "1-n"
        r"^\d+-\d+n$",  # Range to multiple of infinity like "2-2n"
    ]

    for vendor, vendor_dict in new_private_dictionaries.items():
        for tag, attributes in vendor_dict.items():
            vm = attributes[1]

            # Check if VM matches any of the valid patterns
            valid_format = any(re.match(pattern, vm) for pattern in valid_vm_patterns)

            assert valid_format, f"VM '{vm}' for tag {hex(tag)} in {vendor} has invalid format"
