from websocket_proxy.util import base
try:
    import websockets
except ImportError:
    base.fatal_fail("'websockets' library required (pip install websockets). Exiting.")
from websocket_proxy.util.jsonutils import get_json_status_response
import asyncio
import json

#dict:端口是否被占用,{"port":bool}
is_port_used = {}

class WebSocketProxpy:

    logger = None
    host = ""
    port = 0
    serverType = "OPEN_URL"
    proxied_url = ""
    password = ""
    send_suffix = ""
    send_prefix = ""
    proxied_port_list = []

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
            self.logger.info("User authenticated.")
            return True

    @staticmethod
    def parse_destination_url(json_content):
        # expects {"url": "ws://0.0.0.0:8081/test"}
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
            self.logger.error("Server type value [" + self.serverType + "] in config is invalid. Can't start server")
            base.fatal_fail(None)

        if self.is_forced_url_server() or self.is_forced_url_no_password_server():
            self.proxied_url = server_config['proxiedUrl']
            self.proxied_port_list = server_config['proxiedPortList']

            if self.proxied_url is None or self.proxied_url == "":
                error_message = "Proxied url in config missing--required when running in FORCED_URL mode."
                self.logger.error(error_message)
                base.fatal_fail(None)
            if self.proxied_port_list is None :
                error_message = "Proxied url in config missing--required when running in FORCED_URL mode."
                self.logger.error(error_message)
                base.fatal_fail(None)

            for i in range(len(self.proxied_port_list)):
                is_port_used[self.proxied_port_list[i]] = False


    def load_config_from_yaml(self, config_yaml):
        try:
            self.load_server_config_from_yaml(config_yaml)
            self.load_authentication_config_from_yaml(config_yaml)
            self.load_transport_config_from_yaml(config_yaml)
            return True
        except TypeError:
            return False

    def run(self,config_yaml):
        is_config_loaded = self.load_config_from_yaml(config_yaml)

        if not is_config_loaded:
            base.fatal_fail("Unable to load config file, can't parse the YAML!")

        server = websockets.serve(self.proxy_dispatcher, self.host, self.port, ping_interval=20, ping_timeout=20, close_timeout=10)
        self.logger.info("Initializing PROXY SERVER")
        asyncio.get_event_loop().run_until_complete(server)
        asyncio.get_event_loop().run_forever()

    @asyncio.coroutine
    def proxy_dispatcher(self, proxy_web_socket, path):
        self.logger.info("Connection established with CLIENT")
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

                '''
                未修改
                '''
                proxied_web_socket = yield from self.connect_to_proxy_server(proxied_url_value, proxy_web_socket)
                yield from self.process_arbitrary_requests(proxy_web_socket, proxied_web_socket, connection,proxied_url_value)
            else:
                auth_failed_message = "Authentication failed. Password invalid [" + connection.credentials + "]"
                yield from proxy_web_socket.send(get_json_status_response("error", auth_failed_message + "'}"))
                self.logger.warning("CLIENT authentication credentials [" + connection.credentials + "] rejected.")
        else:
            for i in range(len(self.proxied_port_list)):
                #检测端口是否被占用
                if not is_port_used.get(self.proxied_port_list[i]):
                    is_port_used[self.proxied_port_list[i]] = True
                    proxied_url_value = self.proxied_url + self.proxied_port_list[i]
                    proxied_web_socket = yield from self.connect_to_proxy_server(proxied_url_value, proxy_web_socket)
                    yield from self.process_arbitrary_requests(proxy_web_socket, proxied_web_socket, connection)
                    is_port_used[self.proxied_port_list[i]] = False
                    break
                #如果所有端口被占用，返回{"receive_error":"..."}，引发client异常
                if i == len(self.proxied_port_list) - 1:
                    try:
                        yield from proxy_web_socket.send('{"receive_error": "PROXIED SERVER\'s whole ports are using NOW!"}')
                        self.logger.warning("Client[ " + proxy_web_socket.remote_address[0] + ":" + str(proxy_web_socket.remote_address[1]) + " ] :PROXIED SERVER's whole ports are using NOW!")

                    except websockets.exceptions.ConnectionClosed:
                        self.logger.error("Sending receive ERROR to Client ERROR!")
                        break
                    yield from proxy_web_socket.wait_closed()

    @asyncio.coroutine
    def process_arbitrary_requests(self, proxy_web_socket, proxied_web_socket, connection):

        while not proxied_web_socket.closed:
            # request_for_proxy = yield from proxy_web_socket.recv()
            '''
            part 1:从client接收数据
            '''
            try:
                request_for_proxy = yield from proxy_web_socket.recv()
                # request_for_proxy = yield from asyncio.wait_for(proxy_web_socket.recv(), timeout=10)
            except websockets.exceptions.ConnectionClosed:
                 self.logger.error("Receive response ERROR from PROXY SERVER!")
                 if proxied_web_socket.closed:
                     self.logger.warning("proxied_web_socket is closed(1)")
                 else:
                     self.logger.warning("proxied_web_socket is open(1)")

                 yield from proxy_web_socket.wait_closed()
                 self.logger.warning("Client[ " + proxy_web_socket.remote_address[0] + ":" + str(proxy_web_socket.remote_address[1]) + " ] to proxy is closed")

                 yield from proxied_web_socket.close(code=1000)
                 is_port_used[str(proxied_web_socket.port)] = False
                 self.logger.warning("PROIED SERVER [ ws://"+proxied_web_socket.host +":"+ str(proxied_web_socket.port)+" ] is closed")

                 break


            #检测是否收到关闭请求，格式{"action": "closed"}
            if self.is_close(request_for_proxy):
                self.logger.info("Received CLOSE from CLIENT [" + request_for_proxy + "]")
                #关闭proxied_web_socket
                yield from proxied_web_socket.close(code=1000)
                is_port_used[str(proxied_web_socket.port)] = False
                self.logger.warning("PROIED SERVER [ ws://" + proxied_web_socket.host + ":" + str(proxied_web_socket.port) + " ] is closed")

                # 关闭proxy_web_socket
                yield from proxy_web_socket.send('{"action": "closed"}')
                yield from proxy_web_socket.wait_closed()
                self.logger.warning("PROXY SERVER [ " + proxy_web_socket.remote_address[0] + ":" + str(proxy_web_socket.remote_address[1]) + " ] is closed")

                return

            self.logger.info("Received request from CLIENT [" + request_for_proxy + "]")

            # if self.send_prefix is not None and self.send_suffix is not None:
            #     request_for_proxy = self.send_prefix + request_for_proxy + self.send_suffix

            '''
            part 2:proxy发送数据到server
            '''
            yield from self.send_to_web_socket_connection_aware(proxy_web_socket, proxied_web_socket, request_for_proxy)

            #计算请求数
            connection.request_count += 1

            self.logger.info("Sending request [" + str(connection.request_count) + "] to PROXIED SERVER [" + request_for_proxy + "]")

            '''
            part 3:proxy接受server返回的数据
            '''
            try:
                response_from_proxy = yield from proxied_web_socket.recv()
            except websockets.exceptions.ConnectionClosed:
                self.logger.error("Receive response ERROR from PROXIED SERVER!")
                #关闭proxied_web_socket
                yield from proxied_web_socket.wait_closed()
                self.logger.warning("PROXIED SERVER [ " + proxied_web_socket.host + ":" + str(proxied_web_socket.port) + " ] is closed")
                #关闭proxy_web_socket

                yield from proxy_web_socket.close()
                self.logger.warning("PROXY SERVER [ " + proxy_web_socket.remote_address[0] + ":" + str(proxy_web_socket.remote_address[1]) + " ] is closed")

                is_port_used[str(proxied_web_socket.port)] = False
                return
                # proxied_web_socket = yield from websockets.connect(proxied_url_value,ping_interval=20,ping_timeout=20, close_timeout=10)
                # yield from self.send_to_web_socket_connection_aware(proxy_web_socket, proxied_web_socket,
                #                                                     request_for_proxy)
                # response_from_proxy = yield from proxied_web_socket.recv()

            self.logger.info("Received response from PROXIED SERVER [" + response_from_proxy + "]")

            '''
            part 4:proxy返回数据到client
            '''
            try:
                yield from proxy_web_socket.send(response_from_proxy)
                self.logger.info("Sending response from PROXY to CLIENT [" + response_from_proxy + "]")
            except websockets.exceptions.ConnectionClosed:
                self.logger.error("Sending response from PROXY to CLIENT ERROR!")
                yield from proxy_web_socket.wait_closed()
                self.logger.warning("PROXY SERVER [" + proxy_web_socket.remote_address[0] + ":" + str(proxy_web_socket.remote_address[1]) + " ] is closed")
                break


    def get_post_authentication_directions(self):
        authentication_message = "Authenticated. "

        if self.is_forced_url_server():
            authentication_message += "Socket open for arbitrary proxy requests."
        else:
            authentication_message += "Supply URL."

        return authentication_message

    def has_valid_server_type(self):
        return self.is_open_url_server() or self.is_forced_url_server() or self.is_forced_url_no_password_server()

    @asyncio.coroutine
    def get_proxy_url_from_client(self, proxy_web_socket, ):
        proxied_url_json = yield from proxy_web_socket.recv()
        proxied_url_value = self.parse_destination_url(proxied_url_json)
        self.logger.info("PROXIED SERVER url received [" + proxied_url_value + "]")

        if proxied_url_value is None:
            url_missing_message = "Couldn't establish proxy. Url not provided in [" + proxied_url_json + "]"

            # yield from proxy_web_socket.send(get_json_status_response("error", url_missing_message + "'}"))

        return proxied_url_value

    @asyncio.coroutine
    def connect_to_proxy_server(self, proxied_url_value, proxy_web_socket):
        try:
            proxied_web_socket = yield from websockets.connect(proxied_url_value,ping_interval=20,ping_timeout=20, close_timeout=10)
        except ConnectionRefusedError:
            yield from self.respond_with_proxy_connect_error(proxied_url_value, proxy_web_socket)
            return
        self.logger.info("Established proxied connection with PROXIED SERVER [" + proxied_url_value + "]")

        connection_open_message = "Proxied connection [" + proxied_url_value + "] open for arbitrary requests.'"
        #yield from proxy_web_socket.send(get_json_status_response("ok", connection_open_message))

        return proxied_web_socket

    @asyncio.coroutine
    def send_to_web_socket_connection_aware(self, proxy_web_socket, proxied_web_socket, request_for_proxy):
        try:
            yield from proxied_web_socket.send(request_for_proxy)
        except websockets.exceptions.InvalidState:
            self.logger.info("Send the Request to PROXIED SERVER error" )
            # proxy_web_socket.send(get_json_status_response("ok", "Proxied connection closed."))

    def respond_with_proxy_connect_error(self, proxied_url_value, proxy_web_socket):
            error_message = "Unable to connect with proxied url [" + proxied_url_value + "]. Connection closed."
            #yield from proxy_web_socket.send(get_json_status_response("error", error_message + "'}"))
            self.logger.error(error_message)

    def get_credentials(self, web_socket):
        credentials = yield from web_socket.recv()
        self.logger.info("Credentials received from CLIENT [" + credentials + "]")

        return credentials

class WebSocketConnection:
    request_count = 0
    credentials = ""