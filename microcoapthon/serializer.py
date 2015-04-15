from microcoapthon.utils import BitManipulationReader, BitManipulationWriter

__author__ = 'Giacomo Tanganelli'
__version__ = "1.0"

import logging


from microcoapthon import defines
from microcoapthon.messages.message import Message
from microcoapthon.messages.option import Option
from microcoapthon.messages.request import Request
from microcoapthon.messages.response import Response


class Serializer:
    """
    Class for serialize and de-serialize messages.
    """

    def __init__(self):
        """
        Initialize a Serializer.

        """
        self._reader = None
        self._writer = None

    def deserialize(self, raw, host, port):
        """
        De-serialize a stream of byte to a message.

        :param raw: received bytes
        :param host: source host
        :param port: source port
        :return: the message
        """
        stream = bytearray(raw)
        self._reader = BitManipulationReader(stream)
        # self._reader = BitStream(bytes=raw, length=(len(raw) * 8))
        # version = self._reader.read(defines.VERSION_BITS).uint
        version = self._reader.read_bits(defines.VERSION_BITS, "uint")
        # message_type = self._reader.read(defines.TYPE_BITS).uint
        message_type = self._reader.read_bits(defines.TYPE_BITS, "uint")
        # token_length = self._reader.read(defines.TOKEN_LENGTH_BITS).uint
        token_length = self._reader.read_bits(defines.TOKEN_LENGTH_BITS, "uint")
        # code = self._reader.read(defines.CODE_BITS).uint
        code = self._reader.read_bits(defines.CODE_BITS, "uint")
        # mid = self._reader.read(defines.MESSAGE_ID_BITS).uint
        mid = self._reader.read_bits(defines.MESSAGE_ID_BITS, "uint")
        if self.is_response(code):
            message = Response()
            message.code = code
        elif self.is_request(code):
            message = Request()
            message.code = code
        else:
            message = Message()
        message.source = (host, port)
        message.destination = None
        message.version = version
        message.type = message_type
        message._mid = mid

        if token_length > 0:
            message.token = self._reader.read_bits(token_length * 8, "str")
        else:
            message.token = None

        current_option = 0
        while self._reader.pos < self._reader.len:
            next_byte = self._reader.peek_bits(8)
            if next_byte != int(defines.PAYLOAD_MARKER):
                # the first 4 bits of the byte represent the option delta
                delta = self._reader.read_bits(4)
                # the second 4 bits represent the option length
                length = self._reader.read_bits(4)
                current_option += self.read_option_value_from_nibble(delta)
                option_length = self.read_option_value_from_nibble(length)

                # read option
                try:
                    option_name, option_type, option_repeatable, default = defines.options[current_option]
                except KeyError:
                    logging.error("unrecognized option")
                    return message, "BAD_OPTION"
                if option_length == 0:
                    value = None
                elif option_type == defines.INTEGER:
                    value = self._reader.read_bits(option_length * 8)
                else:
                    value = self._reader.read_bits(option_length * 8, kind='str')

                option = Option()
                option.number = current_option
                # option.value = self.convert_to_raw(current_option, value, option_length)
                option.value = value

                message.add_option(option)
            else:
                self._reader.pos_byte += 1  # skip payload marker
                if self._reader.len <= self._reader.pos:
                    logging.error("Payload Marker with no payload")
                    return message, "BAD_REQUEST"
                to_end = self._reader.len - self._reader.pos
                message.payload = self._reader.read_bits(to_end, "opaque")
        return message

    @staticmethod
    def is_request(code):
        """
        Checks if is request.

        :return: True, if is request
        """
        return defines.REQUEST_CODE_LOWER_BOUND <= code <= defines.REQUEST_CODE_UPPER_BOUND

    @staticmethod
    def is_response(code):
        """
        Checks if is response.

        :return: True, if is response
        """
        return defines.RESPONSE_CODE_LOWER_BOUND <= code <= defines.RESPONSE_CODE_UPPER_BOUND

    def read_option_value_from_nibble(self, nibble):
        """
        Calculates the value used in the extended option fields.

        :param nibble: the 4-bit option header value.
        :return: the value calculated from the nibble and the extended option value.
        """
        if nibble <= 12:
            return nibble
        elif nibble == 13:
            tmp = self._reader.read_bits(8) + 13
            return tmp
        elif nibble == 14:
            return self._reader.read_bits(16) + 269
        else:
            raise ValueError("Unsupported option nibble " + nibble)

    def serialize(self, message):
        """
        Serialize message to a stream of byte.

        :param message: the message
        :return: the stream of bytes
        """

        if message.token is None or message.token == "":
            tkl = 0
        else:
            tkl = len(message.token)

        self._writer = BitManipulationWriter()
        self._writer.write_bits(defines.VERSION_BITS, defines.VERSION)
        self._writer.write_bits(defines.TYPE_BITS, message.type)
        self._writer.write_bits(defines.TOKEN_LENGTH_BITS, tkl)
        self._writer.write_bits(defines.CODE_BITS, message.code)
        self._writer.write_bits(defines.MESSAGE_ID_BITS, message.mid)

        if message.token is not None and len(message.token) > 0:
            self._writer.write_bits(len(message.token) * 8, message.token)

        options = self.as_sorted_list(message.options)  # already sorted
        lastoptionnumber = 0
        for option in options:

            # write 4-bit option delta
            optiondelta = option.number - lastoptionnumber
            optiondeltanibble = self.get_option_nibble(optiondelta)
            self._writer.write_bits(defines.OPTION_DELTA_BITS, optiondeltanibble)

            # write 4-bit option length
            optionlength = option.length
            optionlengthnibble = self.get_option_nibble(optionlength)
            self._writer.write_bits(defines.OPTION_LENGTH_BITS, optionlengthnibble)

            # write extended option delta field (0 - 2 bytes)
            if optiondeltanibble == 13:
                self._writer.write_bits(8, optiondelta - 13)
            elif optiondeltanibble == 14:
                self._writer.write_bits(16, optiondelta - 296)

            # write extended option length field (0 - 2 bytes)
            if optionlengthnibble == 13:
                self._writer.write_bits(8, optionlength - 13)
            elif optionlengthnibble == 14:
                self._writer.write_bits(16, optionlength - 269)

            # write option value
            self._writer.write_bits(optionlength * 8, option.value)

            # update last option number
            lastoptionnumber = option.number

        payload = message.payload
        if isinstance(payload, dict):
            payload = payload.get("Payload")
        if payload is not None and len(payload) > 0:
            # if payload is present and of non-zero length, it is prefixed by
            # an one-byte Payload Marker (0xFF) which indicates the end of
            # options and the start of the payload
            self._writer.write_bits(8, defines.PAYLOAD_MARKER)
            self._writer.write_bits(len(payload) * 8, payload)

        return self._writer.stream

    @staticmethod
    def get_option_nibble(optionvalue):
        """
        Returns the 4-bit option header value.

        :param optionvalue: the option value (delta or length) to be encoded.
        :return: the 4-bit option header value.
         """
        if optionvalue <= 12:
            return optionvalue
        elif optionvalue <= 255 + 13:
            return 13
        elif optionvalue <= 65535 + 269:
            return 14
        else:
            raise ValueError("Unsupported option delta " + optionvalue)

    @staticmethod
    def as_sorted_list(options):
        """
        Returns all options in a list sorted according to their option numbers.

        :return: the sorted list
        """
        if len(options) > 0:
            options.sort(key=lambda o: o.number)
        return options

    @staticmethod
    def convert_to_raw(number, value, length):
        """
        Get the value of an option as a BitArray.

        :param number: the option number
        :param value: the option value
        :param length: the option length
        :return: the value of an option as a BitArray
        """
        if length == 0:
            return bytearray()
        return bytearray(value, "utf-8")