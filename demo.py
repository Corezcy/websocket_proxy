# System imports.
from datetime import datetime
from gzip import GzipFile
from io import BytesIO
from threading import Thread
from time import sleep
from json import loads
from json import dumps
from os import makedirs

# Third-party imports.
from flask import Flask
from flask_sockets import Sockets
from geventwebsocket.handler import WebSocketHandler
from gevent.pywsgi import WSGIServer
from websocket import WebSocketException
from websocket import WebSocketApp

# Configuration.
# This is the intended server's URI.
REAL_SERVER_URI = 'ws://10.78.4.163:8181'

def get_timestamp():
    return datetime.now().strftime('%I.%M.%S.%f %p')

def parse_message(message):
    if type(message) is bytes:
        if message[0:3] == b'\x1f\x8b\x08':
            gzip_buffer = BytesIO(message)
            gzip_file = GzipFile(fileobj=gzip_buffer)
            message = gzip_file.read()
        else:
            raise BufferError('Got unexpected binary data!')

    return dumps(loads(message), indent='\t')

class ServerEventHandler:
    def  __init__(self, client_web_socket):
        self.client_web_socket = client_web_socket

    def on_message(self, web_socket, message):
        self.client_web_socket.send(message)
        message = parse_message(message)
        timestamp = get_timestamp()

        makedirs('packets', exist_ok=True)

        with open('packets/{} - Server Packet.json'.format(timestamp), 'w') as file:
            file.write(message)
            file.write('\n')

        print('{} - Server Packet:'.format(timestamp))
        print(message)

    def on_open(self, web_socket):
        print('{} - WebSocket Proxy: Connected to server!'.format(get_timestamp()))


    def on_close(self, web_socket):
        print('{} - WebSocket Proxy: Disconnected from server!'.format(get_timestamp()))

        if not self.client_web_socket.closed:
            print('{} - WebSocket Proxy: Disconnecting client...'.format(get_timestamp()))
            self.client_web_socket.close()
            print('{} - WebSocket Proxy: Disconnected from client!'.format(get_timestamp()))

application = Flask(__name__)
sockets = Sockets(application)

@sockets.route('/')
def proxy(client_web_socket):
    print('{} - WebSocket Proxy: Connected to client!'.format(get_timestamp()))

    # We need to establish a connection with the real server.
    server_event_handler = ServerEventHandler(client_web_socket)
    server_web_socket_app = WebSocketApp(
        REAL_SERVER_URI,
        on_open=server_event_handler.on_open,
        on_message=server_event_handler.on_message,
        on_close=server_event_handler.on_close)
    server_web_socket_thread = Thread(target=server_web_socket_app.run_forever)
    server_web_socket_thread.start()
    server_web_socket = server_web_socket_app.sock

    while not server_web_socket.connected:
        print('{} - WebSocket Proxy: Connecting to server...'.format(get_timestamp()))
        sleep(1)

    # The server is connected, let's start listening to the client.
    while not client_web_socket.closed:
        message = client_web_socket.receive()

        if message:
            server_web_socket.send(message)

            message = parse_message(message)
            timestamp = get_timestamp()

            makedirs('packets', exist_ok=True)

            with open('packets/{} - Client Packet.json'.format(timestamp), 'w') as file:
                file.write(message)
                file.write('\n')

            print('{} - Client Packet:'.format(timestamp))
            print(message)
        else:
            print('{} - WebSocket Proxy: Disconnected from client!'.format(get_timestamp()))
            print('{} - WebSocket Proxy: Disconnecting server...'.format(get_timestamp()))
            server_web_socket.close()

if __name__ == '__main__':
    server = WSGIServer(('0.0.0.0', 1111), application, handler_class=WebSocketHandler)
    print('{} - WebSocket Proxy: Waiting for client...'.format(get_timestamp()))
    server.serve_forever()