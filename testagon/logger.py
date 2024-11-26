import logging

logger = logging.getLogger("testagon")

def configure_logger(log_level=logging.INFO):
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s]\t- %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level)
