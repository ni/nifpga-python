"""
Tests for Session.add_register and Session.add_fifo, which support
HDL-written registers and FIFOs not present in the lvbitx file.
"""
import ctypes
import unittest
import mock

import nifpga
from nifpga.nifpga import DataType, _SessionType
from nifpga.session import Session, _RegisterDescriptor, _FifoDescriptor
from nifpga.statuscheckedlibrary import StatusCheckedLibrary


MINIMAL_BITFILE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Bitfile>
  <BitfileVersion>4.0</BitfileVersion>
  <SignatureRegister>AABBCCDD00112233AABBCCDD00112233</SignatureRegister>
  <Project>
    <CompilationResultsTree>
      <CompilationResults>
        <NiFpga>
          <BaseAddressOnDevice>16384</BaseAddressOnDevice>
          <DmaChannelAllocationList/>
        </NiFpga>
      </CompilationResults>
    </CompilationResultsTree>
  </Project>
  <VI>
    <RegisterList/>
  </VI>
</Bitfile>"""


def _make_mock_session():
    """Return a Session with a mocked _nifpga and an open _session handle."""
    bitfile = nifpga.Bitfile(MINIMAL_BITFILE_XML, parse_contents=True)
    with mock.patch('nifpga.statuscheckedlibrary.ctypes.util.find_library'), \
         mock.patch('nifpga.statuscheckedlibrary.ctypes.cdll') as mock_cdll:
        mock_lib = mock.Mock()
        mock_cdll.LoadLibrary.return_value = mock_lib
        # All library calls return 0 (success)
        mock_lib.NiFpgaDll_Open.return_value = 0
        for attr in dir(mock_lib):
            try:
                getattr(mock_lib, attr).return_value = 0
            except Exception:
                pass

        session = Session.__new__(Session)
        session._nifpga = mock.Mock()
        session._nifpga.__getitem__ = mock.Mock(return_value=mock.Mock(return_value=0))
        session._session = _SessionType(42)
        session._reset_if_last_session_on_exit = False
        session._registers = {}
        session._internal_registers_dict = {}
        session._fifos = {}
        session._base_address_on_device = bitfile.base_address_on_device()
    return session


class RegisterDescriptorTest(unittest.TestCase):
    def test_name(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertEqual(d.name, "MyReg")

    def test_offset(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertEqual(d.offset, 100)

    def test_datatype_is_u32(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertIs(d.datatype, DataType.U32)

    def test_type_is_c_api_type(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertTrue(d.type.is_c_api_type)

    def test_type_datatype_is_u32(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertIs(d.type.datatype, DataType.U32)

    def test_access_may_timeout_false(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertFalse(d.access_may_timeout())

    def test_is_array_false(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertFalse(d.is_array())

    def test_is_internal_false(self):
        d = _RegisterDescriptor("MyReg", 100)
        self.assertFalse(d.is_internal())


class FifoDescriptorTest(unittest.TestCase):
    def test_name(self):
        d = _FifoDescriptor("MyFifo", 3)
        self.assertEqual(d.name, "MyFifo")

    def test_number(self):
        d = _FifoDescriptor("MyFifo", 3)
        self.assertEqual(d.number, 3)

    def test_datatype_is_u32(self):
        d = _FifoDescriptor("MyFifo", 3)
        self.assertIs(d.datatype, DataType.U32)

    def test_type_datatype_is_u32(self):
        d = _FifoDescriptor("MyFifo", 3)
        self.assertIs(d.type.datatype, DataType.U32)

    def test_transfer_size_bytes_is_4(self):
        d = _FifoDescriptor("MyFifo", 3)
        self.assertEqual(d.transfer_size_bytes, 4)

    def test_is_fxp_false(self):
        d = _FifoDescriptor("MyFifo", 3)
        self.assertFalse(d.is_fxp())

    def test_is_composite_false(self):
        d = _FifoDescriptor("MyFifo", 3)
        self.assertFalse(d.is_composite())


class AddRegisterTest(unittest.TestCase):
    def setUp(self):
        self._session = _make_mock_session()

    def test_add_register_returns_register(self):
        reg = self._session.add_register("HdlReg", 8)
        self.assertIsNotNone(reg)

    def test_register_appears_in_registers_dict(self):
        self._session.add_register("HdlReg", 8)
        self.assertIn("HdlReg", self._session.registers)

    def test_register_name(self):
        reg = self._session.add_register("HdlReg", 8)
        self.assertEqual(reg.name, "HdlReg")

    def test_register_datatype_is_u32(self):
        reg = self._session.add_register("HdlReg", 8)
        self.assertIs(reg.datatype, DataType.U32)

    def test_register_resource_includes_base_address(self):
        base = self._session._base_address_on_device  # 16384
        offset = 32
        reg = self._session.add_register("HdlReg", offset)
        self.assertEqual(reg._resource, base + offset)

    def test_duplicate_name_raises(self):
        self._session.add_register("HdlReg", 8)
        with self.assertRaises(AssertionError):
            self._session.add_register("HdlReg", 16)


class AddFifoTest(unittest.TestCase):
    def setUp(self):
        self._session = _make_mock_session()

    def test_add_fifo_calls_nifpga_AddFifo(self):
        self._session.add_fifo("HdlFifo", number=5, base_address=0x8000,
                               direction=0)
        self._session._nifpga.AddFifo.assert_called_once_with(
            self._session._session, 5, 0x8000, 0, 4)

    def test_add_fifo_returns_fifo(self):
        fifo = self._session.add_fifo("HdlFifo", number=5,
                                      base_address=0x8000, direction=0)
        self.assertIsNotNone(fifo)

    def test_fifo_appears_in_fifos_dict(self):
        self._session.add_fifo("HdlFifo", number=5, base_address=0x8000,
                               direction=0)
        self.assertIn("HdlFifo", self._session.fifos)

    def test_fifo_name(self):
        fifo = self._session.add_fifo("HdlFifo", number=5,
                                      base_address=0x8000, direction=0)
        self.assertEqual(fifo.name, "HdlFifo")

    def test_fifo_datatype_is_u32(self):
        fifo = self._session.add_fifo("HdlFifo", number=5,
                                      base_address=0x8000, direction=0)
        self.assertIs(fifo.datatype, DataType.U32)

    def test_fifo_number(self):
        fifo = self._session.add_fifo("HdlFifo", number=7,
                                      base_address=0x8000, direction=1)
        self.assertEqual(fifo._number, 7)

    def test_duplicate_name_raises(self):
        self._session.add_fifo("HdlFifo", number=5, base_address=0x8000,
                               direction=0)
        with self.assertRaises(AssertionError):
            self._session.add_fifo("HdlFifo", number=6, base_address=0x8000,
                                   direction=0)
