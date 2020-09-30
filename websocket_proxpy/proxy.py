from websocket_proxpy.util import base
try:
    import websockets
except ImportError:
    base.fatal_fail("'websockets' library required (pip install websockets). Exiting.")
from websocket_proxpy.util.jsonutils import get_json_status_response
import asyncio
import json


class WebSocketProxpy:
    logger = None
    host = "localhost"
    port = 1111
    serverType = "OPEN_URL"
    proxied_url = "10.78.4.163:8181"
    password = ""
    send_suffix = ""
    send_prefix = ""
    requests_per_connection = 10000

    def __init__(self, logger):
        self.logger = logger

    def is_open_url_server(self):
        return self.serverType == "OPEN_URL"

    def is_forced_url_server(self):
        return self.serverType == "FORCED_URL"

    def is_forced_url_no_password_server(self):
        return self.serverType == "FORCED_URL_NO_PASSWORD"

    def authenticate(self, connection):
        # expects {"password": "12345"}
        try:
            parsed_json = json.loads(connection.credentials)
        except ValueError:
            return False

        if 'password' not in parsed_json:
            return False
        elif parsed_json['password'] != self.password:
            return False
        else:
            self.logger.log("User authenticated.")
            return True

    @staticmethod
    def parse_destination_url(json_content):
        # expects {"url": "ws://localhost:8081/test"}
        try:
            parsed_json = json.loads(json_content)
        except ValueError:
            return None

        if 'url' not in parsed_json:
            return None
        return parsed_json['url']

    @staticmethod
    def is_close(json_content):
        # expects {"action": "close"}
        try:
            parsed_json = json.loads(json_content)
        except ValueError:
            return None

        if 'action' not in parsed_json:
            return False

        if parsed_json['action'] != "close":
            return False

        return True

    def load_authentication_config_from_yaml(self, config_yaml):
        authentication_configuration = config_yaml['configuration']['authenticationConfiguration']
        self.password = authentication_configuration['password']

    def load_transport_config_from_yaml(self, config_yaml):
        transport_configuration = config_yaml['configuration']['transportConfiguration']
        self.send_prefix = transport_configuration['sendPrefix']
        self.send_suffix = transport_configuration['sendSuffix']

    def load_server_config_from_yaml(self, config_yaml):
        server_config = config_yaml['configuration']['serverConfiguration']

        self.host = server_config['listenHost']
        self.port = int(server_config['port'])
        self.serverType = server_config['type']
        self.requests_per_connection = int(server_config['requestsPerConnection'])
        if not self.has_valid_server_type():
            self.logger.log("Server type value [" + self.serverType + "] in config is invalid. Can't start server")
            base.fatal_fail(None)

        if self.is_forced_url_server() or self.is_forced_url_no_password_server():
            self.proxied_url = server_config['proxiedUrl']

            if self.proxied_url is None or self.proxied_url == "":
                error_message = "Proxied url in config missing--required when running in FORCED_URL mode."
                self.logger.log(error_message)
                base.fatal_fail(None)

    def load_config_from_yaml(self, config_yaml):
        try:
            self.load_server_config_from_yaml(config_yaml)
            self.load_authentication_config_from_yaml(config_yaml)
            self.load_transport_config_from_yaml(config_yaml)
            return True
        except TypeError:
            return False

    @asyncio.coroutine
    def proxy_dispatcher(self, proxy_web_socket, path):
        self.logger.log("Connection established with CLIENT")

        connection = WebSocketConnection()

        if not self.is_forced_url_no_password_server():

            #proxy已经接受到client发送的东西
            connection.credentials = yield from self.get_credentials(proxy_web_socket)

            if self.authenticate(connection):
                authenticated_message = "Authenticated " + self.get_post_authentication_directions()
                #yield from proxy_web_socket.send(get_json_status_response("ok", authenticated_message + "'}"))
                if self.is_open_url_server():
                    proxied_url_value = yield from self.get_proxy_url_from_client(proxy_web_socket)

                    if proxied_url_value is None:
                        return
                else:
                    proxied_url_value = self.proxied_url

                proxied_web_socket = yield from self.connect_to_proxy_server(proxied_url_value, proxy_web_socket)
                yield from self.process_arbitrary_requests(proxy_web_socket, proxied_web_socket, connection,proxied_url_value)
            else:
                auth_failed_message = "Authentication failed. Password invalid [" + connection.credentials + "]"
                yield from proxy_web_socket.send(get_json_status_response("error", auth_failed_message + "'}"))
                self.logger.log("CLIENT authentication credentials [" + connection.credentials + "] rejected.")
        else:
            proxied_url_value = self.proxied_url
            proxied_web_socket = yield from self.connect_to_proxy_server(proxied_url_value, proxy_web_socket)
            yield from self.process_arbitrary_requests(proxy_web_socket, proxied_web_socket, connection,proxied_url_value)



    def respond_with_proxy_connect_error(self, proxied_url_value, proxy_web_socket):
            error_message = "Unable to connect with proxied url [" + proxied_url_value + "]. Connection closed."
            #yield from proxy_web_socket.send(get_json_status_response("error", error_message + "'}"))
            self.logger.log(error_message)

    def get_credentials(self, web_socket):
        credentials = yield from web_socket.recv()
        self.logger.log("Credentials received from CLIENT [" + credentials + "]")

        return credentials

    def run(self, config_yaml):
        is_config_loaded = self.load_config_from_yaml(config_yaml)

        if not is_config_loaded:
            base.fatal_fail("Unable to load config file, can't parse the YAML!")

        server = websockets.serve(self.proxy_dispatcher, self.host, self.port)
        self.logger.log("Initializing PROXY SERVER")
        asyncio.get_event_loop().run_until_complete(server)
        asyncio.get_event_loop().run_forever()

    def process_arbitrary_requests(self, proxy_web_socket, proxied_web_socket, connection,proxied_url_value):

        while not proxied_web_socket.closed:
            # request_for_proxy = yield from proxy_web_socket.recv()

            try:
                request_for_proxy = yield from proxy_web_socket.recv()
                # request_for_proxy = yield from asyncio.wait_for(proxy_web_socket.recv(), timeout=10)
            except websockets.exceptions.ConnectionClosed:
                 self.logger.log("websockets.exceptions.ConnectionClosed")
                 if proxied_web_socket.closed:
                     self.logger.log("proxied_web_socket is closed")
                 self.logger.log("proxied_web_socket is open")

                 yield from proxied_web_socket.wait_closed()

                 if proxied_web_socket.closed:
                     self.logger.log("proxied_web_socket is closed")
                 self.logger.log("proxied_web_socket is open")
                 break

            if self.is_close(request_for_proxy):
                self.logger.log("Received CLOSE from CLIENT [" + request_for_proxy + "]")
                yield from proxy_web_socket.send('{"action": "closed"}')
                yield from proxied_web_socket.close()
                yield from proxy_web_socket.wait_closed()
                return

            self.logger.log("Received request from CLIENT [" + request_for_proxy + "]")


            if self.send_prefix is not None and self.send_suffix is not None:
                request_for_proxy = self.send_prefix + request_for_proxy + self.send_suffix
            yield from self.send_to_web_socket_connection_aware(proxy_web_socket, proxied_web_socket, request_for_proxy)

            connection.request_count += 1

            if connection.request_count > self.requests_per_connection:
                connection_limit_error = "Unable to proxy request, connection exceeds config limit of [" + str(
                    self.requests_per_connection) + "] requests per connection."
                self.logger.log(connection_limit_error)
                #yield from proxy_web_socket.send(get_json_status_response("error", connection_limit_error))
                return

            self.logger.log(
                "Sending request [" + str(connection.request_count) + "] to PROXIED SERVER [" + request_for_proxy + "]")

            try:
                response_from_proxy = yield from proxied_web_socket.recv()
            except websockets.exceptions.ConnectionClosed:
                self.logger.log("ConnectionClosedError1")
                yield from proxied_web_socket.close()
                proxied_web_socket = yield from websockets.connect(proxied_url_value,ping_interval=60)
                yield from self.send_to_web_socket_connection_aware(proxy_web_socket, proxied_web_socket,
                                                                    request_for_proxy)
                response_from_proxy = yield from proxied_web_socket.recv()
            self.logger.log("Received response from PROXIED SERVER [" + response_from_proxy + "]")

            # if proxy_web_socket.closed:
            #     self.logger.log("proxy_web_socket is closed")
            # self.logger.log("proxy_web_socket is open")
            # if proxied_web_socket.closed:
            #     self.logger.log("proxied_web_socket is closed")
            # self.logger.log("proxied_web_socket is open")

            try:
                yield from proxy_web_socket.send(response_from_proxy)
            except websockets.exceptions.ConnectionClosed:
                self.logger.log("ConnectionClosedError2")
                break

            self.logger.log("Sending response to CLIENT [" + response_from_proxy + "]")

        if proxied_web_socket.closed:
            self.logger.log("proxied_web_socket is closed")
        self.logger.log("proxied_web_socket is open")

    def get_post_authentication_directions(self):
        authentication_message = "Authenticated. "

        if self.is_forced_url_server():
            authentication_message += "Socket open for arbitrary proxy requests."
        else:
            authentication_message += "Supply URL."

        return authentication_message

    def has_valid_server_type(self):
        return self.is_open_url_server() or self.is_forced_url_server() or self.is_forced_url_no_password_server()

    def get_proxy_url_from_client(self, proxy_web_socket, ):
        proxied_url_json = yield from proxy_web_socket.recv()
        proxied_url_value = self.parse_destination_url(proxied_url_json)
        self.logger.log("PROXIED SERVER url received [" + proxied_url_value + "]")

        if proxied_url_value is None:
            url_missing_message = "Couldn't establish proxy. Url not provided in [" + proxied_url_json + "]"

            # yield from proxy_web_socket.send(get_json_status_response("error", url_missing_message + "'}"))

        return proxied_url_value

    def connect_to_proxy_server(self, proxied_url_value, proxy_web_socket):
        try:
            proxied_web_socket = yield from websockets.connect(proxied_url_value,ping_interval=60)
        except ConnectionRefusedError:
            yield from self.respond_with_proxy_connect_error(proxied_url_value, proxy_web_socket)
            return
        self.logger.log("Established proxied connection with PROXIED SERVER [" + proxied_url_value + "]")

        connection_open_message = "Proxied connection [" + proxied_url_value + "] open for arbitrary requests.'"
        #yield from proxy_web_socket.send(get_json_status_response("ok", connection_open_message))

        return proxied_web_socket

    def send_to_web_socket_connection_aware(self, proxy_web_socket, proxied_web_socket, request_for_proxy):
        try:
            yield from proxied_web_socket.send(request_for_proxy)
        except websockets.exceptions.InvalidState:
            self.logger.log("Send the Request to PROXIED SERVER error" )
            # proxy_web_socket.send(get_json_status_response("ok", "Proxied connection closed."))


class WebSocketConnection:
    request_count = 0
    credentials = ""