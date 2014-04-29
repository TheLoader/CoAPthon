import socket
import SocketServer
import sys
from bitstring import BitStream, ReadError
from coapthon2 import defines
from coapthon2.messages.message import Message
from coapthon2.messages.option import Option
from coapthon2.messages.optionregistry import OptionRegistry
from coapthon2.messages.request import Request

__author__ = 'Giacomo Tanganelli'
__version__ = "2.0"
__all__ = ["CoAPServer", "BaseCoAPRequestHandler"]


class CoAPServer(SocketServer.UDPServer):

    def __init__(self, server_address, request_handler_class):
        SocketServer.UDPServer.__init__(self, server_address, request_handler_class)
        self._server_name = None
        self._server_port = None

    def server_bind(self):
        """Override server_bind to store the server name."""
        SocketServer.UDPServer.server_bind(self)
        host, port = self.socket.getsockname()[:2]
        self._server_name = socket.getfqdn(host)
        self._server_port = port


class BaseCoAPRequestHandler(SocketServer.DatagramRequestHandler):
    # The Python system version, truncated to its first component.
    sys_version = "Python/" + sys.version.split()[0]

    # The server software version.  You may want to override this.
    # The format is multiple whitespace-separated strings,
    # where each string is of the form name[/version].
    server_version = "BaseCoAP/" + __version__

    def __init__(self, request, client_address, server):
        SocketServer.DatagramRequestHandler.__init__(self, request, client_address, server)
        ## The reader.
        self._reader = None

    def handle(self):
        try:
            buff = self.rfile.getvalue()
            self._reader = BitStream(bytes=buff, length=self.rfile.len)
            version = self._reader.read(defines.VERSION_BITS).uint
            mtype = self._reader.read(defines.TYPE_BITS).uint
            token_length = self._reader.read(defines.TOKEN_LENGTH_BITS).uint
            code = self._reader.read(defines.CODE_BITS).uint
            mid = self._reader.read(defines.MESSAGE_ID_BITS).uint
            if not self.is_response(code):
                self.send_error(406)
                return
            elif self.is_request(code):
                message = Request()
                message.code = code
            else:
                message = Message()
            message.version = version
            message.type = mtype
            message.mid = mid

            if token_length > 0:
                message.token = self._reader.read(token_length * 8).bytes
            else:
                message.token = None

            current_option = 0
            try:
                while True:
                    next_byte = self._reader.peek(8).uint
                    if next_byte != int(defines.PAYLOAD_MARKER):
                        # the first 4 bits of the byte represent the option delta
                        delta = self._reader.read(4).uint
                        current_option += self.read_option_value_from_nibble(delta)
                        # the second 4 bits represent the option length
                        length = self._reader.read(4).uint
                        option_length = self.read_option_value_from_nibble(length)

                        # read option
                        option_name, option_type = OptionRegistry.dict[current_option]
                        if option_length == 0:
                            value = None
                        elif option_type == defines.INTEGER:
                            value = self._reader.read(option_length * 8).uint
                        else:
                            value = self._reader.read(option_length * 8).bytes
            except ReadError:
                pass


        except socket.timeout, e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            return

    @staticmethod
    def is_request(code):
        """
        Checks if is request.

        @return: true, if is request
        """
        return defines.REQUEST_CODE_LOWER_BOUND <= code <= defines.REQUEST_CODE_UPPER_BOUNT

    @staticmethod
    def is_response(self, code):
        """
        Checks if is response.

        @return: true, if is response
        """
        return defines.RESPONSE_CODE_LOWER_BOUND <= code <= defines.RESPONSE_CODE_UPPER_BOUND

    @staticmethod
    def is_empty(self, code):
        """
        Checks if is empty.

        @return: true, if is empty
        """
        return code == defines.EMPTY_CODE

    def log_error(self, fmt, *args):
        raise NotImplemented

    def send_error(self, code, message=None):
        raise NotImplemented

    def read_option_value_from_nibble(self, nibble):
        """
        Calculates the value used in the extended option fields as specified in
        draft-ietf-core-coap-14, section 3.1

        @param nibble: the 4-bit option header value.
        @return: the value calculated from the nibble and the extended option value.
        """
        if nibble <= 12:
            return nibble
        elif nibble == 13:
            #self._reader.pos += 4
            tmp = self._reader.read(8).uint + 13
            #self._reader.pos -= 12
            return tmp
        elif nibble == 14:
            return self._reader.read(16).uint + 269
        else:
            raise ValueError("Unsupported option delta " + nibble)