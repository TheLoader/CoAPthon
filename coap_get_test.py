#!/bin/python
import getopt
import random
import sys
import threading
import datetime
from time import sleep
from threading import Thread
from coapthon.client.coap_synchronous import HelperClientSynchronous
from coapthon.messages.request import Request


res = {}
threads = {}


def usage():
    print "Command:\tcoap_get_test.py -r"
    print "Options:"
    print "\t-r, --rate=\trequest rate [req / sec]"
    print "\t-n, --num=\tnumber of requests"
    print "\t-i, --iteration=\titeration number"


def end_save(obj, name):
    with open('results/' + name + '.dat', 'a') as f:
        f.write(obj + "\n")


def save_obj(obj, name):
    with open('results/' + name + '.dat', 'w') as f:
        f.write("Name\tSeconds\tPayload\n")
        for k, v in obj.items():
            elapsed, payload = v
            if payload is None:
                f.write(k + "\t" + str(elapsed) + "\tERROR\n")
            else:
                f.write(k + "\t" + str(elapsed) + "\t" + payload + "\n")


def main():
    rate = None
    num = None
    iteration = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hr:n:i:", ["help", "rate=", "num=", "iteration"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print str(err)  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    for o, a in opts:
        if o in ("-r", "--rate"):
            rate = float(a)
        elif o in ("-n", "--num"):
            num = int(a)
        elif o in ("-i", "--iteration"):
            iteration = int(a)
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        else:
            usage()
            sys.exit(2)

    if rate is None or num is None or iteration is None:
        print "Rate, Number of request and Iteration must be specified"
        usage()
        sys.exit(2)

    for i in range(0, num):
        threads[i] = Thread(target=work)
    print "thread created"

    interval = 1 / rate

    start = datetime.datetime.now()
    for i in range(0, num):
        sleep(interval)
        # threads[i] = Thread(target=work)
        threads[i].start()

    for i in range(0, num):
        threads[i].join()

    end = datetime.datetime.now()
    name = "rate_" + str(rate) + "_num_" + str(num) + "_iter_" + str(iteration)
    save_obj(res, name)
    diff = end - start
    end_save("Total time: " + str(diff.total_seconds()), name)


def work():
    client = HelperClientSynchronous()
    kwargs = {"path": "coap://192.168.2.3:5683/basic"}
    start = datetime.datetime.now()
    response = client.get(**kwargs)
    end = datetime.datetime.now()
    name = threading.current_thread().getName()
    print name + " " + response.payload
    diff = end - start
    if response is None:
        res[name] = (diff.total_seconds(), "ERROR")
    else:
        res[name] = (diff.total_seconds(), response.payload)


if __name__ == '__main__':
    main()



