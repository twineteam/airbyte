#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from unittest.mock import MagicMock

from source_lever.source import SourceLever


def test_check_connection(mocker):
    source = SourceLever()
    logger_mock, config_mock = MagicMock(), MagicMock()
    assert source.check_connection(logger_mock, config_mock) == (True, None)


def test_streams(mocker):
    source = SourceLever()
    config_mock = MagicMock()
    streams = source.streams(config_mock)
    expected_streams_number = 14
    assert len(streams) == expected_streams_number
