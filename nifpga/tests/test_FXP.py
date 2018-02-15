from nifpga import DataType
from nifpga.session import _FxpRegister
from decimal import Decimal
import unittest


class MockFxpRegister(_FxpRegister):
    def __init__(self,
                 signed,
                 enableOverflowStatus,
                 word_length,
                 integer_word_length):
        self._signed = signed
        self._word_length = word_length
        self._integer_word_length = integer_word_length
        self._overflow_enabled = enableOverflowStatus
        self.set_register_attributes()

    def set_register_attributes(self):
        self._name = "MockFxpRegister"
        self._radix_point = self._calculate_radix_point()
        self._offset = 0  # Not needed for mock
        self._datatype = DataType.FXP  # FXP is always DataType.FXP
        self._ctype_type = self._datatype._return_ctype()
        self._access_may_timeout = False  # Does not affect FXP any different
        self._internal = False  # Cant be internal
        self._is_array = False  # This mock is always a single FXP


binary_string_16bit = '1110010010010110'  # 2's comp = 0001101101101010
binary_string_32bit = '01000101100100100011000100001100'
binary_string_64bit = '0010101100101100100000010001000000001001100101001000100001010011'


class FxpRegisterConvertFromBinaryToDecimalValues(unittest.TestCase):
    """ This unit test will test how that we are correctly converting the
    binary values read from hardware into python useful Decimal. """
    # Arbitrary constants to be used for the unit tests

    def test_16bit_all_integer(self):
        FxpRegister = MockFxpRegister(signed=False,
                                      enableOverflowStatus=False,
                                      word_length=16,
                                      integer_word_length=16)
        print(FxpRegister._get_fraction(binary_string_16bit))
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_16bit)
        """ The expected value should be equal to
        2^(15) + 2^(14) + 2^(13) + 2^(10) + 2^(7) + 2^(4) + 2^(2) + 2^(1)
        """
        expected = Decimal(58518)
        self.assertEqual(expected, actual)

    def test_16bit_all_integer_signed(self):
        FxpRegister = MockFxpRegister(signed=True,
                                      enableOverflowStatus=False,
                                      word_length=16,
                                      integer_word_length=16)
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_16bit)
        """ The expected value should be equal to
        -1*(2^(12) + 2^(11) + 2^(9) + 2^(8) + 2^(6) + 2^(5) + 2^(3) + 2^(1))
        """
        expected = Decimal(-7018)
        self.assertEqual(expected, actual)

    def test_15bit_all_integer_overflow(self):
        FxpRegister = MockFxpRegister(signed=False,
                                      enableOverflowStatus=True,
                                      word_length=15,
                                      integer_word_length=15)
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_16bit)
        """ The expected value should be equal to
        2^(15) + 2^(14) + 2^(13) + 2^(10) + 2^(7) + 2^(4) + 2^(2) + 2^(1)
        """
        expected = Decimal(25750)
        self.assertEqual(expected, actual)
        self.assertTrue(FxpRegister.overflow)

    def test_15bit_all_integer_signed_overflow(self):
        FxpRegister = MockFxpRegister(signed=True,
                                      enableOverflowStatus=True,
                                      word_length=15,
                                      integer_word_length=15)
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_16bit)
        """ The expected value should be equal to
        -1*(2^(12) + 2^(11) + 2^(9) + 2^(8) + 2^(6) + 2^(5) + 2^(3) + 2^(1))
        """
        expected = Decimal(-7018)
        self.assertEqual(expected, actual)
        self.assertTrue(FxpRegister.overflow)

    def test_16bit_all_fractional(self):
        FxpRegister = MockFxpRegister(signed=False,
                                      enableOverflowStatus=False,
                                      word_length=16,
                                      integer_word_length=0)
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_16bit)
        """ The expected value should be equal to
        2^(-1) + 2^(-2) + 2^(-3) + 2^(-6) + 2^(-9) + 2^(-12) + 2^(-14) + 2^(-15)
        """
        expected = Decimal(0.892913818359375)
        self.assertEqual(expected, actual)

    def test_16bit_all_fractional_overflow(self):
        FxpRegister = MockFxpRegister(signed=False,
                                      enableOverflowStatus=True,
                                      word_length=15,
                                      integer_word_length=0)
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_16bit)
        """ The expected value should be equal to
        2^(-1) + 2^(-2) + 2^(-5) + 2^(-8) + 2^(-11) + 2^(-13) + 2^(-14)
        """
        expected = Decimal(0.78582763671875)
        self.assertEqual(expected, actual)
        self.assertTrue(FxpRegister.overflow)

    def test_16bit_all_fractional_signed_overflow(self):
        FxpRegister = MockFxpRegister(signed=True,
                                      enableOverflowStatus=True,
                                      word_length=15,
                                      integer_word_length=0)
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_16bit)
        """ The expected value should be equal to
        2^(-3) + 2^(-4) + 2^(-6) + 2^(-7) + 2^(-9) + 2^(-10) + 2^(-12) + 2^(-14)
        """
        expected = Decimal(-0.21417236328125)
        self.assertEqual(expected, actual)
        self.assertTrue(FxpRegister.overflow)

    def test_16bit_integer_16bit_fractional(self):
        FxpRegister = MockFxpRegister(signed=False,
                                      enableOverflowStatus=False,
                                      word_length=32,
                                      integer_word_length=16)
        #'0100010110010010.0011000100001100'
        """ The expected value should be equal to
        2^(1) + 2^(4) + 2^(7) + 2^(8) + 2^(10) + 2^(14) +
        2^(-3) + 2^(-4) + 2^(-8) + 2^(-13) + 2^(-14)
        """
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_32bit)
        expected = Decimal(17810.19158935546875)
        self.assertEqual(expected, actual)

    def test_16bit_integer_15bit_fractional_overflow_signed(self):
        FxpRegister = MockFxpRegister(signed=True,
                                      enableOverflowStatus=True,
                                      word_length=31,
                                      integer_word_length=16)
        """
        #'01000101100100100.011000100001100'
        Expect there to not be an overflow, the value to be negative and the
        twos compliment of the 31 bits of data is:
        0111010011011011.10011101111010
        The expected value should be equal to
        2^(0) + 2^(1) + 2^(3) + 2^(4) + 2^(6) + 2^(7) + 2^(10) + 2^(12) +
        2^(13) + 2^(14) +
        2^(-1) + 2^(-4) + 2^(-5) + 2^(-6) + 2^(-8) + 2^(-9) + 2^(-10) +
        2^(-11)+ 2^(-13)
        """
        actual = FxpRegister._convert_from_binary_to_decimal(binary_string_32bit)
        expected = Decimal(-29915.6168212890625)
        self.assertEqual(expected, actual)
        self.assertFalse(FxpRegister.overflow)


    # def test_500bit_integer_32bit_word(self):
    #     FxpRegister = MockFxpRegister(signed=False,
    #                                   enableOverflowStatus=False,
    #                                   word_length=32,
    #                                   integer_word_length=468)
    #     actual = FxpRegister._convert_from_binary_to_decimal(binary_string_32bit)
    #     # With really large numbers, python can still equate equality using
    #     # E-Notation with enough significant digits
    #     expected = Decimal('2.07122190948279619911823418E140')
    #     self.assertTrue(expected == actual, "Expected {} Actual {}".format(expected, actual))

    # def test_500bit_fractional_32bit_word(self):
    #     FxpRegister = MockFxpRegister(signed=False,
    #                                   enableOverflowStatus=False,
    #                                   word_length=32,
    #                                   integer_word_length=-468)
    #     actual = FxpRegister._convert_from_binary_to_decimal(binary_string_32bit)
    #     expected = Decimal(0)
    #     self.assertEqual(expected, actual)

    # def test_64bit_all_integer_overflow(self):
    #     FxpRegister = MockFxpRegister(signed=False,
    #                                   enableOverflowStatus=True,
    #                                   word_length=64,
    #                                   integer_word_length=64)
    #     binary_string_65bit = '1' + binary_string_64bit

    #     actual = FxpRegister._convert_from_binary_to_decimal(binary_string_65bit)
    #     expected = Decimal(0)
    #     self.assertEqual(expected, actual)
    #     self.assertTrue(FxpRegister.overflow)

    # def test_1056bit_integer_64bit_word(self):
    #     FxpRegister = MockFxpRegister(signed=False,
    #                                   enableOverflowStatus=False,
    #                                   word_length=64,
    #                                   integer_word_length=1024)
    #     actual = FxpRegister._convert_from_binary_to_decimal(binary_string_64bit)
    #     expected = Decimal(0)
    #     self.assertEqual(expected, actual)


# class FxpIntegerWordLengthZeroTest(unittest.TestCase):
#     def setUp(self):
#         self.FxpRegister = MockFxpRegister(signed=False,
#                                            enableOverflowStatus=False,
#                                            word_length=16,
#                                            integer_word_length=0)

#     def test_length_16_word_length_fxp_setup_correctly(self):
#         self.assertEqual(1, len(self.FxpRegister), "We expect the length to be")
#         self.assertEqual(0, self.FxpRegister._radix_point)

#     def test_convert_from_binary_to_decimal(self):
#         data = '0000000000110110'  # Arbitrary 54
#         self.assertEqual(Decimal(54),
#                          self.FxpRegister._convert_from_binary_to_decimal(data))

