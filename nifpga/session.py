"""
Session, a convenient wrapper around the low-level _NiFpga class.

Copyright (c) 2017 National Instruments
"""

from .nifpga import (_SessionType, _IrqContextType, _NiFpga, DataType,
                     OPEN_ATTRIBUTE_NO_RUN, RUN_ATTRIBUTE_WAIT_UNTIL_DONE,
                     CLOSE_ATTRIBUTE_NO_RESET_IF_LAST_SESSION, FifoProperty,
                     _fifo_properties_to_types, FlowControl, DmaBufferType,
                     FpgaViState)
from .bitfile import Bitfile, Fxp_Register
from .status import InvalidSessionError
from collections import namedtuple
import ctypes
from builtins import bytes
from decimal import Decimal
from future.utils import iteritems
from warnings import warn


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
                            or an already open session
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

        if isinstance(resource, _SessionType):
            self._session = resource
        else:
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
            register = self._create_register(bitfile_register,
                                             base_address_on_device)
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

    @property
    def fpga_vi_state(self):
        """ Returns the current state of the FPGA VI. """
        state = ctypes.c_uint32()
        self._nifpga.GetFpgaViState(self._session, state)
        return FpgaViState(state.value)

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
        """ This property contains internal registers"""
        return self._internal_registers_dict

    @property
    def fifos(self):
        """ This property returns a dictionary containing all FIFOs that are
        associated with the bitfile opened with the session. A FIFO can be
        accessed by its unique name.
        """
        return self._fifos

    def _create_register(self, bitfile_register, base_address_on_device):

        if bitfile_register.is_array():
            return _ArrayRegister(self._session,
                                  self._nifpga,
                                  bitfile_register,
                                  base_address_on_device)
        elif isinstance(bitfile_register, Fxp_Register):
            return _FxpRegister(self._session,
                                self._nifpga,
                                bitfile_register,
                                base_address_on_device)
        else:  # default register
            return _Register(self._session,
                             self._nifpga,
                             bitfile_register,
                             base_address_on_device)


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
        self._nifpga = nifpga
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
        write_func = self.get_write_function()
        write_func(self._session, self._resource, data)

    def read(self):
        """ Reads a single element from the control or indicator

        Returns:
            data (DataType.value): The data inside the register.
        """
        data = self._ctype_type()
        read_func = self._get_read_function()
        read_func(self._session, self._resource, data)
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

    def _get_read_function(self):
        """ Sets this registers read function based on the data type from the
        bitfile."""
        return self.nifpga["Read%s" % self.datatype]

    def _get_write_function(self):
        """ Sets this registers read function based on the data type from the
        bitfile."""
        return self.nifpga["Write%s" % self.datatype]


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
        write_func = self._get_write_function()
        write_func(self._session, self._resource, buf, len(self))

    def read(self):
        """ Reads the entire array from the control or indicator.

        Returns:
            (list): The data in the register in a python list.
        """
        buf = self._ctype_type()
        read_func = self._get_read_function()
        read_func(self._session, self._resource, buf, len(self))
        val = [bool(elem) if self._datatype is DataType.Bool else elem for elem in buf]
        return val

    def _get_read_function(self):
        """ Sets this registers read function based on the data type from the
        bitfile."""
        return self._nifpga["ReadArray%s" % self.datatype]

    def _get_write_function(self):
        """ Sets this registers read function based on the data type from the
        bitfile."""
        return self._nifpga["WriteArray%s" % self.datatype]


class _FxpRegister(_ArrayRegister):
    """
    _FxpRegister is a private class that does all the work of converting the
    LabVIEW fixed point data type into something more native to python. This
    implementation will return the Decimal type when calling read(), but should
    be able to handle any native python data types when writing.

    Just like the other Registers we do not support users creating their
    instances of _FxpRegister, but all of the fixed point registers from a
    given bitfile will exist under the sessions.register property.

    Fixed point registers should be easily used from python with a few caveats:
        1. Trying to write data that does not conform to boundaries of the
        defined register, will be coerced and the user will be warned. This is
        either data outside the maximum and minimum values, or data that is not
        a multiple of the delta.
        2. Using Read() and Write() will only return the numerically values of
        a fixed point register. In order to access the overflow status bit,
        users must call the overflow attribute on the Register. The register
        will only have a set overflow status given, the Register has been
        enabled, and has at least been read from or written to before.
    """
    def __init__(self,
                 session,
                 nifpga,
                 bitfile_register,
                 base_address_on_device):
        super(_FxpRegister, self).__init__(session,
                                           nifpga,
                                           bitfile_register,
                                           base_address_on_device)

        self._word_length = bitfile_register.word_length
        self._integer_word_length = bitfile_register.integer_word_length
        self._overflow_enabled = bitfile_register.overflow
        self._signed = bitfile_register.signed
        self._delta = self._calculate_delta()
        self._minimum = self._calculate_minimum()
        self._maximum = self._calculate_maximum()

    @property
    def overflow(self):
        """ This property should only set be whenever this register has overflow
        enabled"""
        return self._overflow

    @overflow.setter
    def overflow(self, value):
        if self._overflow_enabled:
            self._overflow = value

    def _calculate_delta(self):
        """ The value represented in the bitfile for delta is not always
        correct, therefore we must calculate it ourselves.
        """
        return 2**(self._integer_word_length - self._word_length)

    def _calculate_maximum(self):
        """ The value represented in the bitfile for the maximum FXP value is
        not always correct, therefore we must calculate it ourselves.
        """
        if self._signed:
            magnitude_bits = self._word_length - 1
        else:
            magnitude_bits = self._word_length
        return (2**(magnitude_bits) - 1) * self._delta

    def _calculate_minimum(self):
        """ The value represented in the bitfile for the minimum FXP value is
        not always correct, therefore we must calculate it ourselves.
        """
        if self._signed:
            magnitude_bits = self._word_length - 1
            return -1 * ((2**(magnitude_bits)) * self._delta)
        else:
            return 0

    def read(self):
        """ Reads the entire FXP number as an array U32 bits then combining
        the array bits into a single datatype, then convert it into python
        Decimal. The largest expecting transfer would be a 64 bit fixed point
        with the overflow status enabled (making an array of length 3).

        Returns:
            data (DataType.value): The data in the register in a python list.
        """
        data = super(_FxpRegister, self).read()
        data = self._combine_array_of_u32_into_one_value(data)
        return self._convert_from_read_value_to_decimal(data)

    def _combine_array_of_u32_into_one_value(self, data):
        combinedData = 0
        for index in range(0, len(self)):
            combinedData = (combinedData << 32 * index) + data[index]
        if len(self) > 1:
            overflow_bit = 1 if self._overflow_enabled else 0
            total_num_bits = self._word_length + overflow_bit
            combinedData = combinedData >> (32 * len(self) - total_num_bits)
        return combinedData

    def _convert_from_read_value_to_decimal(self, data):
        """ This function converts read value from a RIO device and sets
        the overflow bit if enabled and returns a Decimal representation of
        the fixed point. """
        if self._overflow_enabled:
            self.overflow = self._get_overflow_value(data)
            data = self._remove_overflow_bit(data)
        if self._signed:
            data = self._integer_twos_comp(data)
        return Decimal(data * self._delta)

    def _get_overflow_value(self, data):
        """ Mask out all the data within the word length, leaving the overflow
        bit. If the result after masking the the word portion of the fixed
        point is none zero that indicates the data read has overflown."""
        mask = 2**(self._word_length)
        if data & mask > 0:
            return True
        return False

    def _remove_overflow_bit(self, data):
        """ This helper function masks out all bits not inside the word length,
        ultimately returning a value of data missing the overflow bit. """
        return data & (2**(self._word_length) - 1)

    def _integer_twos_comp(self, data):
        if (data & (1 << (self._word_length - 1))) != 0:
            data = data ^ (2 ** (self._word_length) - 1)
            data += 1
            data *= -1
        return data

    def write(self, data):
        """ Converts the passed in argument into fixed point representation
        and then writes it into the register.

            Args:
                data (any python datatype): The data to be written into the
                register. This method will coerce the value to the nearest
                possible fixed point representation.

                self.overflow: Registers with overflow enabled will write the
                value of the attribute into the register. Users should set this
                attribute on the the register before calling write.
        """

        #binary = self._convert_data_to_binary_fxp(data)
        fxp_representation = self._convert_written_value_to_fxp_representation(data)
        arrayData = self._extract_array_of_u32_from_one_intger(fxp_representation)
        super(_FxpRegister, self).write(arrayData)

    def _convert_written_value_to_fxp_representation(self, data):
        """ """
        fxp_representation = 0
        if data < self._minimum:
            fxp_representation = self._convert_value_to_fxp(self._minimum)
            self.warn_coerced_data()
        elif data > self._maximum:
            fxp_representation = self._convert_value_to_fxp(self._maximum)
            self.warn_coerced_data()
        else:
            fxp_representation = self._convert_value_to_fxp(data)

        if self._signed and data < 0:
            fxp_representation = self._integer_twos_comp(fxp_representation)

        if self._overflow_enabled:
            self._check_overflow_attribute_is_set()
            if self.overflow:
                fxp_representation += 2**(self._word_length)
        return fxp_representation

    def _convert_value_to_fxp(self, data):
        calculated_fxp = Decimal(data) / Decimal(self._delta)
        fxp_representation = int(calculated_fxp)
        """ If the result of the division is not an integer we lost some of
        the input data warn the user that we had to coerce the value to the
        nearest fixed point representation. """
        if fxp_representation != calculated_fxp:
            self.warn_coerced_data()
        return fxp_representation

    def _extract_array_of_u32_from_one_intger(self, data):
        mask_32bit = (2**32) - 1
        extracted_array = []
        for index in range(0, len(self)):
            extracted_array.append(data & mask_32bit)
            data = data >> 32
        extracted_array.reverse()
        return extracted_array

    def _check_overflow_attribute_is_set(self):
        if not hasattr(self, "overflow"):
            warn("Attempting to write without the overflow bit set, defaulting to False")
            self.overflow = False

    def warn_coerced_data(self):
        warn("The inputed value was not able to be converted to FXP, without coercion. ")

    def _get_read_function(self):
        return self._nifpga["ReadArray%s" % DataType.U32]

    def _get_write_function(self):
        return self._nifpga["WriteArray%s" % DataType.U32]


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

    def commit_configuration(self):
        """ Resolves and Commits property changes made to the FIFO. """
        self._nifpga.CommitFifoConfiguration(self._session, self._number)

    @property
    def name(self):
        """ Property of a Fifo that contains its name. """
        return self._name

    @property
    def datatype(self):
        """ Property of a Fifo that contains its datatype. """
        return self._datatype

    def _get_fifo_property(self, prop):
        prop_type = _fifo_properties_to_types[prop]
        value = (prop_type._return_ctype())(0)
        value_pointer = ctypes.pointer(value)
        self._nifpga['GetFifoProperty%s' % prop_type](self._session, self._number, prop.value, value_pointer)
        return value.value

    def _set_fifo_property(self, prop, value):
        prop_type = _fifo_properties_to_types[prop]
        self._nifpga['SetFifoProperty%s' % prop_type](self._session, self._number, prop.value, value)

    @property
    def buffer_allocation_granularity(self):
        """ The allocation granularity of the host memory part of a DMA FIFO.

        By default this will usually be a page size, which is optimal for most
        devices.  This property can be used to customize it.
        """
        return self._get_fifo_property(FifoProperty.BufferAllocationGranularityElements)

    @buffer_allocation_granularity.setter
    def buffer_allocation_granularity(self, value):
        self._set_fifo_property(FifoProperty.BufferAllocationGranularityElements, value)

    @property
    def buffer_size(self):
        """ The size in elements of the Host Memory part of a DMA FIFO. """
        return self._get_fifo_property(FifoProperty.BufferSizeElements)

    @buffer_size.setter
    def buffer_size(self, value):
        self._set_fifo_property(FifoProperty.BufferSizeElements, value)

    @property
    def _mirror_size(self):
        """ The amount of elements in the Host Memory part of the DMA FIFO that
        mirror elements at the beginning.

        The Host Memory part of a DMA FIFO is a circular buffer.  This means that
        when we hit the end of the buffer we have to deal with the logic of wrapping
        around the buffer.  Mirrored elements are elements at the beginning of
        the buffer that are mapped twice in memory to the end of the buffer.
        Settings this value can allow us to avoid wrap arounds.

        This is mostly useful when using our Zero Copy API.  Its not yet
        supported in Python though, so this property is private.
        """
        return self._get_fifo_property(FifoProperty.MirroredElements)

    @_mirror_size.setter
    def _mirror_size(self, value):
        self._set_fifo_property(FifoProperty.MirroredElements, value)

    @property
    def _dma_buffer_type(self):
        return self._get_fifo_property(FifoProperty.DmaBufferType)

    @_dma_buffer_type.setter
    def _dma_buffer_type(self, value):
        if not isinstance(value, DmaBufferType):
            raise TypeError("_dma_buffer_type must be set to a nifpga.DmaBufferType")
        self._set_fifo_property(FifoProperty.DmaBufferType, value.value)

    @property
    def _dma_buffer(self):
        return self._get_fifo_property(FifoProperty.DmaBuffer)

    @_dma_buffer.setter
    def _dma_buffer(self, value):
        self._set_fifo_property(FifoProperty.DmaBuffer, value)

    @property
    def flow_control(self):
        """ Controls whether the FPGA will wait for the host when using FIFOs.

        If flow control is disabled, the FPGA will have free reign to read or
        write elements before the host is ready.  This means the FIFO no longer
        acts in a First In First Out manner.

        For Host To Target FIFOs, this feature is useful when you want to put
        something like a waveform in a FIFO and let the FPGA continue reading
        that waveform over and over without any involvement from the host.

        For Target To Host FIFOs, this feature is useful when you only care
        about the latest data and don't care about old data.
        """
        return self._get_fifo_property(FifoProperty.FlowControl)

    @flow_control.setter
    def flow_control(self, value):
        if not isinstance(value, FlowControl):
            raise TypeError("flow_control must be set to an nifpga.FlowControl")
        self._set_fifo_property(FifoProperty.FlowControl, value.value)
