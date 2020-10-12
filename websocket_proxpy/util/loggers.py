import logging


class ConsoleDebugLogger():
    logger = None

    def __init__(self):
        self.logger = logging.getLogger("ws_proxy")
        self.logger.setLevel(logging.DEBUG)

        # 控制日志输出到控制台
        logging_stream_handler = logging.StreamHandler()

        # 控制日志输出到文件
        file_handler_all = logging.FileHandler('output_log.log')
        file_handler_all.setLevel(logging.DEBUG)

        # 控制error日志输出到文件
        file_handler_error = logging.FileHandler('error.log')
        file_handler_error.setLevel(logging.ERROR)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        logging_stream_handler.setFormatter(formatter)
        file_handler_all.setFormatter(formatter)
        file_handler_error.setFormatter(formatter)

        self.logger.addHandler(logging_stream_handler)
        self.logger.addHandler(file_handler_all)
        self.logger.addHandler(file_handler_error)

    def info(self, message):
        self.logger.info(message)

    def debug(self, message):
        self.logger.debug(message)

    def error(self, message):
        self.logger.error(message)

    def warning(self, message):
        self.logger.warning(message)