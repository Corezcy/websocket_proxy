# from websocket_proxpy.proxy import WebSocketProxpy
from proxy_await_async_version import WebSocketProxpy

from websocket_proxy.util import loggers
from websocket_proxy.util import base

try:
	import yaml
except ImportError:
    base.fatal_fail("'yaml' library required (pip install yaml). Exiting.")

CONFIG_FILE_NAME = "config.yaml"

config = yaml.load(open(CONFIG_FILE_NAME))


WebSocketProxpy(loggers.ConsoleDebugLogger()).run(config)

