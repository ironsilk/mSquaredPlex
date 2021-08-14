import logging

custom_settings = {
    # Mysql
    'mysql_db_name': 'news',
    'mysql_table_root': 'fb',
    'mysql_host': '192.168.1.99',
    'mysql_port': 5433,
    'mysql_user': 'crab',
    'mysql_pass': 'MadMen1!',
}


# Logger settings
def setup_logger(name, log_file=None, level=logging.INFO):
    """Function to setup as many loggers as you want"""
    formatter = logging.Formatter('[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s')
    out_handler = logging.StreamHandler()
    out_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(out_handler)
    if log_file:
        handler = logging.FileHandler(log_file, encoding='utf8')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logger('PlexService')
