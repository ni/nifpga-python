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

    def test_build_spec_version(self):
        bitfile = nifpga.Bitfile(BITFILE_ALL_REGISTERS)
        self.assertEqual(bitfile.build_spec_version, "1.0.0")

    def test_build_spec_description(self):
        bitfile = nifpga.Bitfile(BITFILE_ALL_REGISTERS)
        self.assertEqual(bitfile.build_spec_description, "Test Bitfile Description")

    def test_build_spec_version_none_when_empty(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Bitfile>
  <BitfileVersion>4.0</BitfileVersion>
  <Documentation>
    <BuildSpecVersion/>
    <BuildSpecDescription/>
  </Documentation>
  <SignatureRegister>AABBCCDD00112233AABBCCDD00112233</SignatureRegister>
  <Project>
    <CompilationResultsTree>
      <CompilationResults>
        <NiFpga>
          <BaseAddressOnDevice>0</BaseAddressOnDevice>
          <DmaChannelAllocationList/>
        </NiFpga>
      </CompilationResults>
    </CompilationResultsTree>
  </Project>
  <VI>
    <RegisterList/>
  </VI>
</Bitfile>"""
        bitfile = nifpga.Bitfile(xml, parse_contents=True)
        self.assertIsNone(bitfile.build_spec_version)
        self.assertIsNone(bitfile.build_spec_description)
