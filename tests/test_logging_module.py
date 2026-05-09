import logging
from pathlib import Path

from alco_esp import logging as app_logging


def test_csv_rotating_file_handler_writes_header_for_new_file(tmp_path):
    log_path = tmp_path / "data.csv"

    handler = app_logging.CsvRotatingFileHandler(
        str(log_path),
        mode="a",
        maxBytes=1024,
        backupCount=1,
        encoding="utf-8",
        header="col1;col2",
    )
    handler.close()

    content = log_path.read_text(encoding="utf-8")
    assert content.startswith("col1;col2\n")


def test_csv_rotating_file_handler_does_not_duplicate_header_on_reopen(tmp_path):
    log_path = tmp_path / "data.csv"

    handler1 = app_logging.CsvRotatingFileHandler(
        str(log_path),
        mode="a",
        maxBytes=1024,
        backupCount=1,
        encoding="utf-8",
        header="h1;h2",
    )
    handler1.stream.write("a;b\n")
    handler1.stream.flush()
    handler1.close()

    handler2 = app_logging.CsvRotatingFileHandler(
        str(log_path),
        mode="a",
        maxBytes=1024,
        backupCount=1,
        encoding="utf-8",
        header="h1;h2",
    )
    handler2.close()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines.count("h1;h2") == 1


def test_csv_rotating_file_handler_rewrites_header_after_rollover(tmp_path):
    log_path = tmp_path / "roll.csv"

    handler = app_logging.CsvRotatingFileHandler(
        str(log_path),
        mode="a",
        maxBytes=20,
        backupCount=1,
        encoding="utf-8",
        header="h1;h2",
    )
    handler.stream.write("payload\n")
    handler.stream.flush()

    # Explicit rollover ensures the post-rollover header branch is exercised.
    handler.doRollover()
    handler.close()

    assert log_path.exists()
    assert log_path.read_text(encoding="utf-8").splitlines()[0] == "h1;h2"


class DummyCsvHandler:
    last_header = None

    def __init__(self, *_args, header=None, **_kwargs):
        DummyCsvHandler.last_header = header

    def setFormatter(self, _formatter):
        pass


class DummyLogger:
    def __init__(self):
        self.level = None
        self.handlers = []
        self.propagate = True

    def setLevel(self, level):
        self.level = level

    def addHandler(self, handler):
        self.handlers.append(handler)


def test_setup_data_logging_respects_csv_topic_order(monkeypatch):
    main_logger = DummyLogger()

    monkeypatch.setattr(app_logging, "main_data_logger", main_logger)
    monkeypatch.setattr(app_logging, "CsvRotatingFileHandler", DummyCsvHandler)
    monkeypatch.setattr(app_logging, "CSV_DATA_TOPIC_ORDER", ["b", "a"])
    monkeypatch.setattr(app_logging, "CSV_DATA_HEADERS", {"a": "A", "b": "B"})

    app_logging.setup_data_logging()

    assert DummyCsvHandler.last_header == "Время;B;A"
    assert main_logger.propagate is False
    assert len(main_logger.handlers) == 1


def test_setup_all_data_logging_uses_expected_header(monkeypatch):
    all_logger = DummyLogger()

    monkeypatch.setattr(app_logging, "all_data_logger", all_logger)
    monkeypatch.setattr(app_logging, "CsvRotatingFileHandler", DummyCsvHandler)

    app_logging.setup_all_data_logging()

    assert DummyCsvHandler.last_header == "Время;Топик;Значение"
    assert all_logger.propagate is False
    assert len(all_logger.handlers) == 1
