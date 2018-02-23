from warnings import warn


def bin_to_int(binary_string):
    if binary_string == '':
        return 0
    else:
        return int(binary_string, 2)


def to_bin(value):
    """
    This class uses the built in bin() function to do the conversion,
    but we remove the leading '0b' or '-0b' identifier to keep the logic
    simplified.
    """
    binary_representation = bin(value)
    if binary_representation[0] == '-':
        return binary_representation[3:]
    else:
        return binary_representation[2:]


def twos_compliment(binary_string):
    binary_string = _flip_bits(binary_string)
    binary_string = _add_one_to_binary(binary_string)
    return binary_string


def _flip_bits(binary_string):
    temp_string = ''
    for bit in binary_string:
        if bit == '0':
            temp_string += '1'
        elif bit == '1':
            temp_string += '0'
    return temp_string


def _add_one_to_binary(binary_string):
    temp_string = ''
    carry = True
    for bit in reversed(binary_string):
        if bit == '0':
            if carry:
                temp_string = '1' + temp_string
                carry = False
            else:
                temp_string = '0' + temp_string
        if bit == '1':
            if carry:
                temp_string = '0' + temp_string
            else:
                temp_string = '1' + temp_string
    return temp_string


def warn_coerced_data():
    warn("The inputed value was not able to be converted to FXP, without coercion. ")
