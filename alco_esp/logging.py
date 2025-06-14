import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from alco_esp.constants import APP_ROOT_DIR, CSV_DATA_TOPIC_ORDER, CSV_DATA_HEADERS


class CsvRotatingFileHandler(RotatingFileHandler):
    """
    A RotatingFileHandler that writes a header to new files.
    """
    def __init__(self, filename, *args, header=None, **kwargs):
        self.header = header
        # We need to determine if the header needs to be written BEFORE the file is opened for appending.
        # The base class opens the file in its __init__.
        # So, we check for file existence and size here.
        write_header = not os.path.exists(filename) or os.path.getsize(filename) == 0

        super().__init__(filename, *args, **kwargs)

        if write_header and self.header:
            self.stream.write(self.header + '\n')
            self.stream.flush()

    def doRollover(self):
        super().doRollover()
        # After rollover, the new file (self.baseFilename) is empty.
        # The stream has been reopened by the base class.
        if self.header:
            self.stream.write(self.header + '\n')
            self.stream.flush()


def setup_data_logging():
    """Sets up a separate logger for CSV data."""
    main_data_logger.setLevel(logging.INFO)

    log_dir = os.path.join(APP_ROOT_DIR, "log")
    log_file = os.path.join(log_dir, "alco_esp_data.csv")
    csv_header = "Время;" + ";".join([CSV_DATA_HEADERS[topic] for topic in CSV_DATA_TOPIC_ORDER])

    # Use our custom handler to manage the header
    file_handler = CsvRotatingFileHandler(
        log_file,
        mode='a',
        maxBytes=100 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8-sig',
        header=csv_header
    )

    # Formatter that just passes the message through, as we format it ourselves.
    formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(formatter)

    main_data_logger.addHandler(file_handler)

    # Prevent data logs from propagating to the root logger (and thus the console)
    main_data_logger.propagate = False
    logger.info("Data logging to CSV setup complete.")


def setup_all_data_logging():
    """Sets up a separate logger for all incoming device data."""
    all_data_logger.setLevel(logging.INFO)

    log_dir = os.path.join(APP_ROOT_DIR, "log")
    log_file = os.path.join(log_dir, "alco_esp_all_device_data.csv")
    csv_header = "Время;Топик;Значение"

    file_handler = CsvRotatingFileHandler(
        log_file,
        mode='a',
        maxBytes=100 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8-sig',
        header=csv_header
    )

    formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(formatter)
    all_data_logger.addHandler(file_handler)
    all_data_logger.propagate = False
    logger.info("All data logging to all_device_data.csv setup complete.")


def setup_logging():
    logger.setLevel(logging.DEBUG)  # Set the logging level for the logger

    # --- Define log directory and file path ---
    # Log directory is APP_ROOT_DIR/log
    log_dir = os.path.join(APP_ROOT_DIR, "log")
    log_dir_error = None
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            log_dir_error = f"CRITICAL ERROR: Could not create log directory {log_dir}: {e}"
            logger.error(log_dir_error)
            log_dir = APP_ROOT_DIR

    log_file = os.path.join(log_dir, "alco_esp_monitor.log")
    # Rotate log file when it reaches 100MB, keep 5 backup logs
    file_handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file

    # Create a console handler for higher level messages
    console_handler = logging.StreamHandler(sys.stdout) # Explicitly use sys.stdout for the console
    console_handler.setLevel(logging.INFO)  # Show INFO and above on console

    # Create a formatter and set it for both handlers
    # Added module, funcName, and lineno for more detailed logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logging setup complete.")
    if log_dir_error:
        logger.error(log_dir_error)


logger = logging.getLogger("AlcoEspMonitorApp")
setup_logging()
main_data_logger = logging.getLogger("AlcoEspDataLogger")
setup_data_logging()
all_data_logger = logging.getLogger("AlcoEspAllDataLogger")
setup_all_data_logging()
