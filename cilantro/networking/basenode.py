from multiprocessing import Process, Pipe, Queue

import zmq


class ZMQScaffolding:
    def __init__(self, base_url='127.0.0.1', subscriber_port='1111', publisher_port='9998', filters=(b'', )):
        self.base_url = base_url
        self.subscriber_port = subscriber_port
        self.publisher_port = publisher_port
        self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)
        self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

        self.filters = filters

    def connect(self):
        self.context = zmq.Context()

        self.sub_socket = self.context.socket(socket_type=zmq.SUB)
        self.pub_socket = self.context.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.publisher_url)

        print("binding to url: ", self.subscriber_url)
        self.sub_socket.bind(self.subscriber_url)

        for filter in self.filters:
            self.sub_socket.subscribe(filter)

class BaseNode:
    def __init__(self, serializer, start=True, **kwargs):
        self.queue = Queue()
        self.serializer = serializer
        self.process = Process(target=self.loop)

        self.message_queue = ZMQScaffolding(**kwargs)

        if start:
            self.process.start()

    def loop(self):
        self.message_queue.connect()
        while True:
            print("one inter of the while loop (basenode)")
            self.process_local_queue(self.queue.get())
            try:
                msg = self.message_queue.sub_socket.recv(flags=zmq.NOBLOCK)
                self.process_message_queue(msg)
            except zmq.Again:
                pass

    def process_message_queue(self, msg):
        raise NotImplementedError

    def process_local_queue(self, msg):
        raise NotImplementedError

    def handle_request(self, request):
        # serialize
        # put on queue
        self.queue.put(request)

    def terminate(self):
        self.process.terminate()