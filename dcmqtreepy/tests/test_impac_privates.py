"""Unit tests for impac_privates.py"""

# import os
# import subprocess
# import sys
# import time

# import pytest

from dcmqtreepy import impac_privates


def test_impac_privates():
    impac_dict = impac_privates.impac_private_dict
    assert 0x300B1001 in impac_dict
