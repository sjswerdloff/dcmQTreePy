"""Unit tests for new_privates.py"""


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


def test_vendor_dictionaries_format(assert_valid_dict_attributes):
    """Test that each vendor dictionary has the correct format."""
    for vendor, vendor_dict in new_private_dictionaries.items():
        # Each vendor dictionary should be a dictionary of tag -> attributes
        assert isinstance(vendor_dict, dict), f"Vendor {vendor} dictionary is not a dict"

        # Check each tag entry
        for tag, attributes in vendor_dict.items():
            # Tag should be an integer
            assert isinstance(tag, int), f"Tag {tag} in {vendor} is not an integer"

            # Use the fixture to validate dict attributes
            assert_valid_dict_attributes(tag, attributes, vendor=vendor)


def test_tag_format(assert_valid_tag_format):
    """Test that all tags in the private dictionaries have the correct format."""
    for vendor, vendor_dict in new_private_dictionaries.items():
        for tag in vendor_dict.keys():
            assert_valid_tag_format(tag, vendor=vendor)


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


def test_value_multiplicity_format(valid_vm_patterns, assert_valid_vm_format):
    """Test that VM (Value Multiplicity) entries are correctly formatted."""
    for vendor, vendor_dict in new_private_dictionaries.items():
        for tag, attributes in vendor_dict.items():
            vm = attributes[1]
            assert_valid_vm_format(tag, vm, vendor=vendor, patterns=valid_vm_patterns)
