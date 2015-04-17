#!/bin/python
import getopt
import sys
import threading
import datetime
from time import sleep
from threading import Thread
from coapthon.client.coap_synchronous import HelperClientSynchronous


res = {}
threads = {}


def usage():
    print "Command:\tcoap_get_test.py -r"
    print "Options:"
    print "\t-r, --rate=\trequest rate [req / sec]"
    print "\t-n, --num=\tnumber of requests"


def end_save(obj, name):
    with open('results/' + name + '.dat', 'a') as f:
        f.write(obj + "\n")


def save_obj(obj, name):
    with open('results/' + name + '.dat', 'w') as f:
        f.write("Name\tSeconds\tPayload\n")
        for k, v in obj.items():
            elapsed, payload = v
            f.write(k + "\t" + str(elapsed) + "\t" + payload + "\n")


def main():
    rate = None
    num = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hr:n:", ["help", "rate=", "num="])
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
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        else:
            usage()
            sys.exit(2)

    if rate is None or num is None:
        print "Rate and Number of request must be specified"
        usage()
        sys.exit(2)

    interval = 1 / rate

    start = datetime.datetime.now()
    for i in range(0, num):
        sleep(interval)
        threads[i] = Thread(target=work)
        threads[i].start()

    for i in range(0, num):
        threads[i].join()

    end = datetime.datetime.now()
    name = "rate_" + str(rate) + "_num_" + str(num)
    save_obj(res, name)
    diff = end - start
    end_save("Total time: " + str(diff.total_seconds()), name)


def work():
    client = HelperClientSynchronous()
    kwargs = {"path": "coap://127.0.0.1:5683/basic"}
    start = datetime.datetime.now()
    response = client.get(**kwargs)
    end = datetime.datetime.now()
    name = threading.current_thread().getName()
    print name + " finish"
    diff = end - start
    res[threading.current_thread().getName()] = (diff.total_seconds(), response.payload)


if __name__ == '__main__':
    main()



