import unittest
import os
import nifpga

BITFILE_ALL_REGISTERS = 'nifpga/tests/allregistertypes.lvbitx'


class BitfileTest(unittest.TestCase):
    def test_parse_from_path(self):
        bitfile = nifpga.Bitfile(BITFILE_ALL_REGISTERS)
        self.assertEqual(bitfile.filepath, os.path.abspath(BITFILE_ALL_REGISTERS))

    def test_parse_from_contents(self):
        with open(BITFILE_ALL_REGISTERS, 'r') as f:
            bitfile = nifpga.Bitfile(f.read(), parse_contents=True)
            self.assertTrue(bitfile.filepath is None)

    def test_parse_bitfile_with_fxp_fifo(self):
        with open(BITFILE_ALL_REGISTERS, 'r') as f:
            bitfile = nifpga.Bitfile(f.read(), parse_contents=True)
            bitfile.fifos["FXP FIFO"]

    def test_parse_bitfile_with_fxp_register_array(self):
        with open(BITFILE_ALL_REGISTERS, 'r') as f:
            bitfile = nifpga.Bitfile(f.read(), parse_contents=True)
            print(bitfile.registers)
            bitfile.registers["output fxp array"]
