import logging

'''
    returns a formatted logger object
'''


def Logger(logger):
    formatter = logging.Formatter("%(asctime)s - %(name)s  :   %(levelname)s - %(message)s")
    file_formatter = logging.Formatter("%(asctime)s - %(name)s  :   %(levelname)s - %(message)s")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler("/tmp/wpms.log")
    fh.setLevel(logging.WARNING)
    fh.setFormatter(file_formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger
