from decimal import Decimal, getcontext
from nifpga import DataType
from nifpga.bitfile import _FXP
from nifpga.tests.test_nifpga import assert_warns
import unittest

getcontext().prec = 100


class MockFxp(_FXP):
    def __init__(self,
                 signed,
                 enableOverflowStatus,
                 word_length,
                 integer_word_length):
        self._signed = signed
        self._word_length = word_length
        self._integer_word_length = integer_word_length
        self._delta = self._calculate_delta()
        self._minimum = self._calculate_minimum()
        self._maximum = self._calculate_maximum()
        self._overflow_enabled = enableOverflowStatus
        self._size_in_bits = self._calculate_size_in_bits()
        self._data_mask = (1 << self._size_in_bits) - 1
        self._word_length_mask = (1 << self._word_length) - 1
        self._signed_bit_mask = 1 << (self._word_length - 1)
        self.set_register_attributes()

    def set_register_attributes(self):
        self._name = "MockFxp"
        self._offset = 0  # Not needed for mock
        self._datatype = DataType.Fxp  # FXP is always DataType.Fxp
        self._ctype_type = self._datatype._return_ctype()
        self._access_may_timeout = False  # Does not affect FXP any different
        self._internal = False  # Cant be internal
        self._is_array = False  # This mock is always a single FXP


class FXPRegisterAsserts(object):
    def __init__(self, test):
        self._test = test

    def assert_fxp_value_converted_to_decimal(self,
                                              register,
                                              read_value,
                                              expected_value):
        actual = register.unpack_data(read_value)
        self._test.assertEqual(actual, expected_value)

    def assert_user_input_converted_to_fxp(self,
                                           register,
                                           user_input,
                                           expected_value):
        actual = register.pack_data(user_input, 0)
        self._test.assertEqual(actual, expected_value)


def _calculate_minimum_fxp_value(register):
    if register._signed:
        return 2**(register._word_length - 1)
    else:
        return 0


def _calculate_maximum_fxp_value(register):
    if register._signed:
        magnitude_bits = register._word_length - 1
    else:
        magnitude_bits = register._word_length
    return (2**(magnitude_bits) - 1)


""" These are a couple of arbitrary binary strings that the following unit
to test a non random value.
"""
binary_string_16bit = '1110010010010110'  # 2's comp = 0001101101101010
binary_string_32bit = '01000101100100100011000100001100'

positive_integer = 42  # Arbitrary constant used in some tests


class FXPRegisterSharedTests(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=False,
                                    word_length=1,
                                    integer_word_length=1)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int('1', 2)
        self.user_value = Decimal(1)

    def test_converting_fxp_to_decimal_value(self):
        self.FxpAssert.assert_fxp_value_converted_to_decimal(self.testRegister,
                                                             self.fxp_value,
                                                             self.user_value)

    def test_converting_user_data_into_binary(self):
        self.FxpAssert.assert_user_input_converted_to_fxp(self.testRegister,
                                                          self.user_value,
                                                          self.fxp_value)

    def test_user_input_less_than_minimum(self):
        less_than_minimum = self.testRegister._minimum - positive_integer
        expected_value = _calculate_minimum_fxp_value(self.testRegister)
        with assert_warns(UserWarning):
            if self.testRegister._overflow_enabled:
                overflow = False
                self.FxpAssert.assert_user_input_converted_to_fxp(self.testRegister,
                                                                  (overflow, less_than_minimum),
                                                                  expected_value)
            else:
                self.FxpAssert.assert_user_input_converted_to_fxp(self.testRegister,
                                                                  less_than_minimum,
                                                                  expected_value)

    def test_user_input_greater_than_maximum(self):
        greater_than_max = self.testRegister._maximum + positive_integer
        expected_value = _calculate_maximum_fxp_value(self.testRegister)
        with assert_warns(UserWarning):
            if self.testRegister._overflow_enabled:
                overflow = False
                self.FxpAssert.assert_user_input_converted_to_fxp(self.testRegister,
                                                                  (overflow, greater_than_max),
                                                                  expected_value)
            else:
                self.FxpAssert.assert_user_input_converted_to_fxp(self.testRegister,
                                                                  greater_than_max,
                                                                  expected_value)


class FXPRegister16bitWord16bitInteger(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=False,
                                    word_length=16,
                                    integer_word_length=16)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = Decimal(2**(15) + 2**(14) + 2**(13) + 2**(10)
                                  + 2**(7) + 2**(4) + 2**(2) + 2**(1))


class FXPRegister16bitWord16bitIntegerSigned(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=True,
                                    enableOverflowStatus=False,
                                    word_length=16,
                                    integer_word_length=16)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = Decimal((-1) * (2**(12) + 2**(11) + 2**(9) + 2**(8)
                                          + 2**(6) + 2**(5) + 2**(3) + 2**(1)))


class FXPRegister15bitWord15bitIntegerOverflow(FXPRegisterSharedTests):

    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=True,
                                    word_length=15,
                                    integer_word_length=15)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = (True, Decimal(2**(14) + 2**(13) + 2**(10) + 2**(7)
                                         + 2**(4) + 2**(2) + 2**(1)))

    def test_converting_user_data_without_overflow_use_false(self):
        fxp_with_false_overflow = self.fxp_value - 2**self.testRegister._word_length
        self.FxpAssert.assert_user_input_converted_to_fxp(self.testRegister,
                                                          self.user_value[1],
                                                          fxp_with_false_overflow)


class FXPRegister15bitWord15bitIntegerSignedOverflow(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=True,
                                    enableOverflowStatus=True,
                                    word_length=15,
                                    integer_word_length=15)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = (True, Decimal((-1) * (2**(12) + 2**(11) + 2**(9)
                                                 + 2**(8) + 2**(6) + 2**(5)
                                                 + 2**(3) + 2**(1))))

    def test_overflow_bit_is_not_calculated_in_twos_compliment(self):
        # Create a 15 bit word that is all 1's
        value = int('1' * (self.testRegister._word_length + 1), 2)
        result = self.testRegister.unpack_data(value)
        """ The expected value of overflow(1) 111 1111 1111 1111, would
        expect -1 and an overflow. as the twos complement of the non-overflow
        bits would be 000 0000 0000 0001"""
        self.assertTrue(result[0])
        self.assertEqual(-1, result[1])


class FXPRegister16bitWord0bitInteger(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=False,
                                    word_length=16,
                                    integer_word_length=0)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = Decimal(2**(-1) + 2**(-2) + 2**(-3) + 2**(-6)
                                  + 2**(-9) + 2**(-12) + 2**(-14) + 2**(-15))


class FXPRegister15bitWord0bitIntegerOverflow(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=True,
                                    word_length=15,
                                    integer_word_length=0)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = (True, Decimal(2**(-1) + 2**(-2) + 2**(-5) + 2**(-8)
                                         + 2**(-11) + 2**(-13) + 2**(-14)))


class FXPRegister15bitWord0bitIntegerSignedOverflow(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=True,
                                    enableOverflowStatus=True,
                                    word_length=15,
                                    integer_word_length=0)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = (True, Decimal((-1) * (2**(-3) + 2**(-4) + 2**(-6)
                                                 + 2**(-7) + 2**(-9) + 2**(-10)
                                                 + 2**(-12) + 2**(-14))))


class FXPRegister32bitWord16bitIntegerOverflow(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=True,
                                    word_length=32,
                                    integer_word_length=16)
        self.FxpAssert = FXPRegisterAsserts(self)
        """ binary String '(0) 0100010110010010.0011000100001100' """
        self.fxp_value = int('0' + binary_string_32bit, 2)
        self.user_value = (False, Decimal(2**(1) + 2**(4) + 2**(7) + 2**(8)
                                          + 2**(10) + 2**(14) + 2**(-3)
                                          + 2**(-4) + 2**(-8) + 2**(-13)
                                          + 2**(-14)))


class FXPRegister16bitWord100bitInteger(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=False,
                                    word_length=16,
                                    integer_word_length=100)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = Decimal(2**(99) + 2**(98) + 2**(97) + 2**(94)
                                  + 2**(91) + 2**(88) + 2**(86) + 2**(85))


class FXPRegister16bitWordNegative100bitInteger(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=False,
                                    word_length=16,
                                    integer_word_length=-100)
        self.FxpAssert = FXPRegisterAsserts(self)
        self.fxp_value = int(binary_string_16bit, 2)
        self.user_value = Decimal(2**(-101) + 2**(-102) + 2**(-103) + 2**(-106)
                                  + 2**(-109) + 2**(-112) + 2**(-114)
                                  + 2**(-115))


class FXPRegister64bitWord64bitIntegerOverflow(FXPRegisterSharedTests):
    def setUp(self):
        self.testRegister = MockFxp(signed=False,
                                    enableOverflowStatus=True,
                                    word_length=64,
                                    integer_word_length=64)
        self.FxpAssert = FXPRegisterAsserts(self)
        """(1) 0100 0101 1001 0010 0011 0001 0000 1100 0100 0101 1001 0010 0011 0001 0000 1100 """
        self.fxp_value = int('1' + binary_string_32bit + binary_string_32bit, 2)
        self.user_value = (True, Decimal(5013123263993360652))
