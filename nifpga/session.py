"""
Session, a convenient wrapper around the low-level _NiFpga class.

Copyright (c) 2017 National Instruments
"""

from .nifpga import (_SessionType, _IrqContextType, _NiFpga, DataType,
                     OPEN_ATTRIBUTE_NO_RUN, RUN_ATTRIBUTE_WAIT_UNTIL_DONE,
                     CLOSE_ATTRIBUTE_NO_RESET_IF_LAST_SESSION)
from .bitfile import Bitfile
from .status import IrqTimeoutWarning, InvalidSessionError
from collections import namedtuple
import ctypes
from builtins import bytes
from future.utils import iteritems


class Session(object):
    """
    Session, a convenient wrapper around the low-level _NiFpga class.

    The Session class uses regular python types, provides convenient default
    arguments to C API functions, and makes controls, indicators, and FIFOs
    available by name. If any NiFpga function return status is non-zero, the
    appropriate exception derived from either WarningStatus or ErrorStatus is
    raised.
    Example usage of FPGA configuration functions::

        with Session(bitfile="myBitfilePath.lvbitx", resource="RIO0") as session:
            session.run()
            session.download()
            session.abort()
            session.reset()

    Note:
        It is always recommended that you use a Session with a context manager
        (with). Opening a Session without a context manager could cause you to
        leak the session if :meth:`Session.close` is not called.

    Controls and indicators are accessed directly via a _Register object
    obtained from the session::

        my_control = session.registers["MyControl"]
        my_control.write(data=4)
        data = my_control.read()

    FIFOs are accessed directly via a _FIFO object obtained from the session::

        myHostToFpgaFifo = session.fifos["MyHostToFpgaFifo"]
        myHostToFpgaFifo.stop()
        actual_depth = myHostToFpgaFifo.configure(requested_depth=4096)
        myHostToFpgaFifo.start()
        empty_elements_remaining = myHostToFpgaFifo.write(data=[1, 2, 3, 4],
                                                          timeout_ms=2)

        myFpgaToHostFifo = session.fifos["MyHostToFpgaFifo"]
        read_values = myFpgaToHostFifo.read(number_of_elements=4,
                                            timeout_ms=0)
        print(read_values.data)
    """

    def __init__(self,
                 bitfile,
                 resource,
                 no_run=False,
                 reset_if_last_session_on_exit=False,
                 **kwargs):
        """Creates a session to the specified resource with the specified
        bitfile.

        Args:
            bitfile (str)(Bitfile): A bitfile.Bitfile() instance or a string
                                    filepath to a bitfile.
            resource (str): e.g. "RIO0", "PXI1Slot2", or "rio://hostname/RIO0"
            no_run (bool): If true, don't run the bitfile, just open the
                session.
            reset_if_last_session_on_exit (bool): Passed into Close on
                exit. Unused if not using this session as a context guard.
            **kwargs: Additional arguments that edit the session.
        """
        if not isinstance(bitfile, Bitfile):
            """ The bitfile we were passed is a path to an lvbitx."""
            bitfile = Bitfile(bitfile)
        self._nifpga = _NiFpga()
        self._session = _SessionType()

        open_attribute = 0
        for key, value in kwargs.items():
            if key == '_open_attribute':
                open_attribute = value

        if no_run:
            open_attribute = open_attribute | OPEN_ATTRIBUTE_NO_RUN

        bitfile_path = bytes(bitfile.filepath, 'ascii')
        bitfile_signature = bytes(bitfile.signature, 'ascii')
        resource = bytes(resource, 'ascii')
        self._nifpga.Open(bitfile_path,
                          bitfile_signature,
                          resource,
                          open_attribute,
                          self._session)

        self._reset_if_last_session_on_exit = reset_if_last_session_on_exit
        self._registers = {}
        self._internal_registers_dict = {}
        base_address_on_device = bitfile.base_address_on_device()
        for name, bitfile_register in iteritems(bitfile.registers):
            assert name not in self._registers, \
                "One or more registers have the same name '%s', this is not supported" % name
            if bitfile_register.is_array():
                array_register = _ArrayRegister(self._session, self._nifpga,
                                                bitfile_register,
                                                base_address_on_device)
                if bitfile_register.is_internal():
                    self._internal_registers_dict[name] = array_register
                else:
                    self._registers[name] = array_register

            else:
                register = _Register(self._session, self._nifpga,
                                     bitfile_register, base_address_on_device)
                if bitfile_register.is_internal():
                    self._internal_registers_dict[name] = register
                else:
                    self._registers[name] = register

        self._fifos = {}
        for name, bitfile_fifo in iteritems(bitfile.fifos):
            assert name not in self._fifos, \
                "One or more FIFOs have the same name '%s', this is not supported" % name
            self._fifos[name] = _FIFO(self._session, self._nifpga, bitfile_fifo)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_val, trace):
        try:
            self.close(reset_if_last_session=self._reset_if_last_session_on_exit)
        except InvalidSessionError:
            pass

    def close(self, reset_if_last_session=False):
        """ Closes the FPGA Session.

        Args:
            reset_if_last_session (bool): If True, resets the FPGA on the
                last close. If true, does not reset the FPGA on the last
                session close.
        """
        close_attr = CLOSE_ATTRIBUTE_NO_RESET_IF_LAST_SESSION if reset_if_last_session is False else 0
        self._nifpga.Close(self._session, close_attr)

    def run(self, wait_until_done=False):
        """ Runs the FPGA VI on the target.

        Args:
            wait_until_done (bool): If true, this functions blocks until the
                                    FPGA VI stops running
        """
        run_attr = RUN_ATTRIBUTE_WAIT_UNTIL_DONE if wait_until_done else 0
        self._nifpga.Run(self._session, run_attr)

    def abort(self):
        """ Aborts the FPGA VI. """
        self._nifpga.Abort(self._session)

    def download(self):
        """ Re-downloads the FPGA bitstream to the target. """
        self._nifpga.Download(self._session)

    def reset(self):
        """ Resets the FPGA VI. """
        self._nifpga.Reset(self._session)

    def _irq_ordinals_to_bitmask(self, ordinals):
        bitmask = 0
        for ordinal in ordinals:
            assert 0 <= ordinal and ordinal <= 31, "Valid IRQs are 0-31: %d is invalid" % ordinal
            bitmask |= (1 << ordinal)
        return bitmask

    def wait_on_irqs(self, irqs, timeout_ms):
        """ Stops the calling thread until the FPGA asserts any IRQ in the irqs
        parameter or until the function call times out.

        Args:
            irqs: A list of irq ordinals 0-31, e.g. [0, 6, 31].
            timeout_ms: The timeout to wait in milliseconds.

        Returns:
            session_wait_on_irqs (namedtuple)::

                session_wait_on_irqs.irqs_asserted (list): is a list of the
                    asserted IRQs.
                session_wait_on_irqs.timed_out (bool): Outputs whether or not
                    the time out expired before all irqs were asserted.

        """
        if type(irqs) != list:
            irqs = [irqs]
        irqs_bitmask = self._irq_ordinals_to_bitmask(irqs)

        context = _IrqContextType()
        self._nifpga.ReserveIrqContext(self._session, context)

        irqs_asserted_bitmask = ctypes.c_uint32(0)
        timed_out = DataType.Bool._return_ctype()()
        try:
            self._nifpga.WaitOnIrqs(self._session,
                                    context,
                                    irqs_bitmask,
                                    timeout_ms,
                                    irqs_asserted_bitmask,
                                    timed_out)
        except IrqTimeoutWarning:
            # We pass timed_out to the C API, so we can ignore this warning
            # and just always return timed_out.
            pass
        finally:
            self._nifpga.UnreserveIrqContext(self._session, context)
        irqs_asserted = [i for i in range(32) if irqs_asserted_bitmask.value & (1 << i)]
        WaitOnIrqsReturnValues = namedtuple('WaitOnIrqsReturnValues',
                                            ["irqs_asserted", "timed_out"])
        return WaitOnIrqsReturnValues(irqs_asserted=irqs_asserted,
                                      timed_out=bool(timed_out.value))

    def acknowledge_irqs(self, irqs):
        """ Acknowledges an IRQ or set of IRQs.

        Args:
            irqs (list): A list of irq ordinals 0-31, e.g. [0, 6, 31].
        """
        self._nifpga.AcknowledgeIrqs(self._session,
                                     self._irq_ordinals_to_bitmask(irqs))

    def _get_unique_register_or_fifo(self, name):
        assert not (name in self._registers and name in self._fifos), \
            "Ambiguous: '%s' is both a register and a FIFO" % name
        assert name in self._registers or name in self._fifos, \
            "Unknown register or FIFO '%s'" % name
        try:
            return self._registers[name]
        except KeyError:
            return self._fifos[name]

    @property
    def registers(self):
        """ This property returns a dictionary containing all registers that
        are associated with the bitfile opened with the session. A register can
        be accessed by its unique name.
        """
        return self._registers

    @property
    def _internal_registers(self):
        """ This property contains interal regis"""
        return self._internal_registers_dict

    @property
    def fifos(self):
        """ This property returns a dictionary containing all FIFOs that are
        associated with the bitfile opened with the session. A FIFO can be
        accessed by its unique name.
        """
        return self._fifos


class _Register(object):
    """ _Register is a private class that is a wrapper of logic that is
    associated with controls and indicators.

    All Registers will exists in a sessions session.registers property. This
    means that all possible registers for a given session are created during
    session initialization; a user should never need to create a new instance
    of this class.

    """
    def __init__(self, session, nifpga, bitfile_register, base_address_on_device):
        self._datatype = bitfile_register.datatype
        self._name = bitfile_register.name
        self._session = session
        self._write_func = nifpga["WriteArray%s" % self._datatype] if bitfile_register.is_array() \
            else nifpga["Write%s" % self._datatype]
        self._read_func = nifpga["ReadArray%s" % self._datatype] if bitfile_register.is_array() \
            else nifpga["Read%s" % self._datatype]
        self._ctype_type = self._datatype._return_ctype()
        self._resource = bitfile_register.offset + base_address_on_device
        if bitfile_register.access_may_timeout():
            self._resource = self._resource | 0x80000000

    def __len__(self):
        """ A single register will always have one and only one element.

        Returns:
            (int): Always a constant 1.
        """
        return 1

    def write(self, data):
        """ Writes the specified data to the control or indicator

        Args:
            data (DataType.value): The data to be written into the register
        """
        self._write_func(self._session, self._resource, data)

    def read(self):
        """ Reads a single element from the control or indicator

        Returns:
            data (DataType.value): The data inside the register.
        """
        data = self._ctype_type()
        self._read_func(self._session, self._resource, data)
        if self._datatype is DataType.Bool:
            return bool(data.value)
        return data.value

    @property
    def name(self):
        """ Property of a register that returns the name of the control or
        indicator. """
        return self._name

    @property
    def datatype(self):
        """ Property of a register that returns the datatype of the control or
        indicator. """
        return self._datatype


class _ArrayRegister(_Register):
    """
    _ArryRegister is a private class that inherits from _Register with
    additional interfaces unique to the logic of array controls and indicators.
    """
    def __init__(self,
                 session,
                 nifpga,
                 bitfile_register,
                 base_address_on_device):
        super(_ArrayRegister, self).__init__(session,
                                             nifpga,
                                             bitfile_register,
                                             base_address_on_device)
        self._num_elements = len(bitfile_register)
        self._ctype_type = self._ctype_type * self._num_elements
        self._write_func = nifpga["WriteArray%s" % self._datatype]
        self._read_func = nifpga["ReadArray%s" % self._datatype]

    def __len__(self):
        """ Returns the length of the array.

        Returns:
            (int): The number of elements in the array.
        """
        return self._num_elements

    def write(self, data):
        """ Writes the specified array of data to the control or indicator

            Args:
                data (list): The data "array" to be written into the registers
                wrapped into a python list.
        """
        # if data is not iterable make it iterable
        try:
            iter(data)
        except TypeError:
            data = [data]
        assert len(data) == len(self), \
            "Bad data length %d for register '%s', expected %s" \
            % (len(data), self._name, len(self))
        buf = self._ctype_type(*data)
        self._write_func(self._session, self._resource, buf, len(self))

    def read(self):
        """ Reads the entire array from the control or indicator.

        Returns:
            (list): The data in the register in a python list.
        """
        buf = self._ctype_type()
        self._read_func(self._session, self._resource, buf, len(self))
        return [bool(elem) if self._datatype is DataType.Bool else elem for elem in buf]


class _FIFO(object):
    """ _FIFO is a private class that is a wrapper for the logic that
    associated with a FIFO.

    All FIFOs will exists in a sessions session.fifos property. This means that
    all possible FIFOs for a given session are created during session
    initialization; a user should never need to create a new instance of this
    class.
    """
    def __init__(self, session, nifpga, bitfile_fifo):
        self._datatype = bitfile_fifo.datatype
        self._number = bitfile_fifo.number
        self._session = session
        self._write_func = nifpga["WriteFifo%s" % self._datatype]
        self._read_func = nifpga["ReadFifo%s" % self._datatype]
        self._acquire_read_func = nifpga["AcquireFifoReadElements%s" % self._datatype]
        self._acquire_write_func = nifpga["AcquireFifoWriteElements%s" % self._datatype]
        self._release_elements_func = nifpga["ReleaseFifoElements"]
        self._nifpga = nifpga
        self._ctype_type = self._datatype._return_ctype()
        self._name = bitfile_fifo.name

    def configure(self, requested_depth):
        """ Specifies the depth of the host memory part of the DMA FIFO.

        Args:
            requested_depth (int): The depth of the host memory part of the DMA
                                   FIFO in number of elements.

        Returns:
            actual_depth (int): The actual number of elements in the host
            memory part of the DMA FIFO, which may be more than the
            requested number.
        """
        actual_depth = ctypes.c_size_t()
        self._nifpga.ConfigureFifo2(self._session, self._number,
                                    requested_depth, actual_depth)
        return actual_depth.value

    def start(self):
        """ Starts the FIFO. """
        self._nifpga.StartFifo(self._session, self._number)

    def stop(self):
        """ Stops the FIFO. """
        self._nifpga.StopFifo(self._session, self._number)

    def write(self, data, timeout_ms=0):
        """ Writes the specified data to the FIFO.

        NOTE:
            If the FIFO has not been started before calling
            :meth:`_FIFO.write()`, then it will automatically start and
            continue to work as expected.

        Args:
            data (list): Data to be written to the FIFO.
            timeout_ms (int): The timeout to wait in milliseconds.

        Returns:
            elements_remaining (int): The number of elements remaining in the
            host memory part of the DMA FIFO.
        """
        # if data is not iterable make it iterable
        try:
            iter(data)
        except TypeError:
            data = [data]
        buf_type = self._ctype_type * len(data)
        buf = buf_type(*data)
        empty_elements_remaining = ctypes.c_size_t()
        self._write_func(self._session,
                         self._number,
                         buf,
                         len(data),
                         timeout_ms,
                         empty_elements_remaining)
        return empty_elements_remaining.value

    def read(self, number_of_elements, timeout_ms=0):
        """ Read the specified number of elements from the FIFO.

        NOTE:
            If the FIFO has not been started before calling
            :meth:`_FIFO.read()`, then it will automatically start and continue
            to work as expected.

        Args:
            number_of_elements (int): The number of elements to read from the
                                      FIFO.
            timeout_ms (int): The timeout to wait in milliseconds.

        Returns:
            ReadValues (namedtuple)::

                ReadValues.data (list): containing the data from
                    the FIFO.
                ReadValues.elements_remaining (int): The amount of elements
                    remaining in the FIFO.
        """
        buf_type = self._ctype_type * number_of_elements
        buf = buf_type()
        elements_remaining = ctypes.c_size_t()
        self._read_func(self._session,
                        self._number,
                        buf,
                        number_of_elements,
                        timeout_ms,
                        elements_remaining)
        data = [bool(elem) if self._datatype is DataType.Bool else elem for elem in buf]
        ReadValues = namedtuple("ReadValues", ["data", "elements_remaining"])
        return ReadValues(data=data,
                          elements_remaining=elements_remaining.value)

    def _acquire_write(self, number_of_elements, timeout_ms=0):
        """ Write the specified number of elements from the FIFO.

        Args:
            number_of_elements (int): The number of elements to read from the
                                      FIFO.
            timeout_ms (int): The timeout to wait in milliseconds.

        Returns:
            AcquireWriteValues(namedtuple)::

                AcquireWriteValues.data (ctypes.pointer): Contains the data
                    from the FIFO.
                AcquireWriteValues.elements_acquired (int): The number of
                    elements that were actually acquired.
                AcquireWriteValues.elements_remaining (int): The amount of
                    elements remaining in the FIFO.
        """
        block_out = ctypes.POINTER(self._ctype_type)()
        elements_acquired = ctypes.c_size_t()
        elements_remaining = ctypes.c_size_t()
        self._acquire_write_func(self._session,
                                 self._number,
                                 block_out,
                                 number_of_elements,
                                 timeout_ms,
                                 elements_acquired,
                                 elements_remaining)

        AcquireWriteValues = namedtuple("AcquireWriteValues",
                                        ["data", "elements_acquired",
                                         "elements_remaining"])
        return AcquireWriteValues(data=block_out,
                                  elements_acquired=elements_acquired.value,
                                  elements_remaining=elements_remaining.value)

    def _acquire_read(self, number_of_elements, timeout_ms=0):
        """ Read the specified number of elements from the FIFO.

        Args:
            number_of_elements (int): The number of elements to read from the
                                      FIFO.
            timeout_ms (int): The timeout to wait in milliseconds.

        Returns:
            AcquireWriteValues(namedtuple): has the following members::

                AcquireWriteValues.data (ctypes.pointer): Contains the data
                    from the FIFO.
                AcquireWriteValues.elements_acquired (int): The number of
                    elements that were actually acquired.
                AcquireWriteValues.elements_remaining (int): The amount of
                    elements remaining in the FIFO.
        """
        buf = self._ctype_type()
        buf_ptr = ctypes.pointer(buf)
        elements_acquired = ctypes.c_size_t()
        elements_remaining = ctypes.c_size_t()
        self._acquire_read_func(self._session,
                                self._number,
                                buf_ptr,
                                number_of_elements,
                                timeout_ms,
                                elements_acquired,
                                elements_remaining)
        AcquireReadValues = namedtuple("AcquireReadValues",
                                       ["data", "elements_acquired",
                                        "elements_remaining"])
        return AcquireReadValues(data=buf_ptr,
                                 elements_acquired=elements_acquired.value,
                                 elements_remaining=elements_remaining.value)

    def _release_elements(self, number_of_elements):
        """ Releases the FIFOs elements. """
        self._release_elements_func(self._session, self._number, number_of_elements)

    def get_peer_to_peer_endpoint(self):
        """ Gets an endpoint reference to a peer-to-peer FIFO. """
        endpoint = ctypes.c_uint32(0)
        self._nifpga.GetPeerToPeerFifoEndpoint(self._session, self._number, endpoint)
        return endpoint.value

    @property
    def name(self):
        """ Property of a Fifo that contains its name. """
        return self._name

    @property
    def datatype(self):
        """ Property of a Fifo that contains its datatype. """
        return self._datatype
