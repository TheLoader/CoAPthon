from coapthon.resources.resource import Resource
from twisted.internet import reactor
from coapthon.server.coap_protocol import CoAP

import RPi.GPIO as GPIO


class RPiResource(Resource):
    channel = 0
    state = GPIO.low

    def __init__(self, name="RPiResource"):
        super(RPiResource, self).__init__(name, visible=True,
                                          observable=True, allow_children=True)
        self.payload = "Basic Resource"

    def render_PUT(self, request):
        GPIO.output(self.channel, self.state)
        self.payload = self.state
        return self


class CoAPServer(CoAP):
    def __init__(self, host, port, multicast=False):
        CoAP.__init__(self, multicast)
        self.add_resource('temp/', RPiResource())
        print "CoAP Server start on " + host + ":" + str(port)
        print(self.root.dump())


def main():
    server = CoAPServer("127.0.0.1", 5683)
    #reactor.listenMulticast(5683, server, listenMultiple=True)
    reactor.listenUDP(5683, server, "127.0.0.1")
    reactor.run()


if __name__ == '__main__':
    main()
