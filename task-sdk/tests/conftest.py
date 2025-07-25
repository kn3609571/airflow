# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, Protocol
from unittest.mock import patch

import pytest

pytest_plugins = "tests_common.pytest_plugin"

# Task SDK does not need access to the Airflow database
os.environ["_AIRFLOW_SKIP_DB_TESTS"] = "true"
os.environ["_AIRFLOW__AS_LIBRARY"] = "true"

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from structlog.typing import EventDict, WrappedLogger

    from airflow.sdk.api.datamodels._generated import AssetEventDagRunReference, TIRunContext


@pytest.hookimpl()
def pytest_addhooks(pluginmanager: pytest.PytestPluginManager):
    # Python 3.12 starts warning about mixing os.fork + Threads, and the pytest-rerunfailures plugin uses
    # threads internally. Since this is new code, and it should be flake free, we disable the re-run failures
    # plugin early (so that it doesn't run it's pytest_configure which is where the thread starts up if xdist
    # is discovered).
    pluginmanager.set_blocked("rerunfailures")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    config.inicfg["airflow_deprecations_ignore"] = []

    # Always skip looking for tests in these folders!
    config.addinivalue_line("norecursedirs", "tests/test_dags")

    import airflow.settings

    airflow.settings.configure_policy_plugin_manager()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if next(item.iter_markers(name="db_test"), None):
        pytest.fail("Task SDK tests must not use database")


class LogCapture:
    # Like structlog.typing.LogCapture, but that doesn't add log_level in to the event dict
    entries: list[EventDict | bytes]

    def __init__(self) -> None:
        self.entries = []

    def __call__(self, _: WrappedLogger, method_name: str, event: EventDict | bytes) -> NoReturn:
        from structlog.exceptions import DropEvent

        if isinstance(event, dict):
            if "level" not in event:
                event["_log_level"] = method_name

        self.entries.append(event)

        raise DropEvent


@pytest.fixture
def test_dags_dir():
    return Path(__file__).parent.joinpath("task_sdk", "dags")


@pytest.fixture
def captured_logs(request):
    import structlog

    from airflow.sdk.log import configure_logging, reset_logging

    # Use our real log config
    reset_logging()
    configure_logging(enable_pretty_log=False)

    # Get log level from test parameter, which can either be a single log level or a
    # tuple of log level and desired output type, defaulting to INFO if not provided
    log_level = logging.INFO
    output = "dict"
    param = getattr(request, "param", logging.INFO)
    if isinstance(param, int):
        log_level = param
    elif isinstance(param, tuple):
        log_level = param[0]
        output = param[1]

    # We want to capture all logs, but we don't want to see them in the test output
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(log_level))

    cur_processors = structlog.get_config()["processors"]
    processors = cur_processors.copy()
    if output == "dict":
        # We need to replace remove the last processor (the one that turns JSON into text, as we want the
        # event dict for tests)
        proc = processors.pop()
        assert isinstance(proc, (structlog.dev.ConsoleRenderer, structlog.processors.JSONRenderer)), (
            "Pre-condition"
        )
    try:
        cap = LogCapture()
        processors.append(cap)
        structlog.configure(processors=processors)
        task_logger = logging.getLogger("airflow.task")

        from airflow.sdk.execution_time.secrets_masker import SecretsMasker

        task_logger.addFilter(SecretsMasker())
        yield cap.entries
    finally:
        structlog.configure(processors=cur_processors)


@pytest.fixture(autouse=True, scope="session")
def _disable_ol_plugin():
    # The OpenLineage plugin imports setproctitle, and that now causes (C) level thread calls, which on Py
    # 3.12+ issues a warning when os.fork happens. So for this plugin we disable it

    # And we load plugins when setting the priority_weight field
    import airflow.plugins_manager

    old = airflow.plugins_manager.plugins

    assert old is None, "Plugins already loaded, too late to stop them being loaded!"

    airflow.plugins_manager.plugins = []

    yield

    airflow.plugins_manager.plugins = None


class MakeTIContextCallable(Protocol):
    def __call__(
        self,
        dag_id: str = ...,
        run_id: str = ...,
        logical_date: str | datetime = ...,
        data_interval_start: str | datetime = ...,
        data_interval_end: str | datetime = ...,
        clear_number: int = ...,
        start_date: str | datetime = ...,
        run_after: str | datetime = ...,
        run_type: str = ...,
        task_reschedule_count: int = ...,
        conf: dict[str, Any] | None = ...,
        should_retry: bool = ...,
        max_tries: int = ...,
        consumed_asset_events: Sequence[AssetEventDagRunReference] = ...,
    ) -> TIRunContext: ...


class MakeTIContextDictCallable(Protocol):
    def __call__(
        self,
        dag_id: str = ...,
        run_id: str = ...,
        logical_date: str = ...,
        data_interval_start: str | datetime = ...,
        data_interval_end: str | datetime = ...,
        clear_number: int = ...,
        start_date: str | datetime = ...,
        run_after: str | datetime = ...,
        run_type: str = ...,
        task_reschedule_count: int = ...,
        conf=None,
        consumed_asset_events: Sequence[AssetEventDagRunReference] = ...,
    ) -> dict[str, Any]: ...


@pytest.fixture
def make_ti_context() -> MakeTIContextCallable:
    """Factory for creating TIRunContext objects."""
    from airflow.sdk.api.datamodels._generated import DagRun, TIRunContext
    from airflow.utils.state import DagRunState

    def _make_context(
        dag_id: str = "test_dag",
        run_id: str = "test_run",
        logical_date: str | datetime = "2024-12-01T01:00:00Z",
        data_interval_start: str | datetime = "2024-12-01T00:00:00Z",
        data_interval_end: str | datetime = "2024-12-01T01:00:00Z",
        clear_number: int = 0,
        start_date: str | datetime = "2024-12-01T01:00:00Z",
        run_after: str | datetime = "2024-12-01T01:00:00Z",
        run_type: str = "manual",
        task_reschedule_count: int = 0,
        conf: dict[str, Any] | None = None,
        should_retry: bool = False,
        max_tries: int = 0,
        consumed_asset_events: Sequence[AssetEventDagRunReference] = (),
    ) -> TIRunContext:
        return TIRunContext(
            dag_run=DagRun(
                dag_id=dag_id,
                run_id=run_id,
                logical_date=logical_date,  # type: ignore
                data_interval_start=data_interval_start,  # type: ignore
                data_interval_end=data_interval_end,  # type: ignore
                clear_number=clear_number,  # type: ignore
                start_date=start_date,  # type: ignore
                run_type=run_type,  # type: ignore
                run_after=run_after,  # type: ignore
                state=DagRunState.RUNNING,
                conf=conf,  # type: ignore
                consumed_asset_events=list(consumed_asset_events),
            ),
            task_reschedule_count=task_reschedule_count,
            max_tries=max_tries,
            should_retry=should_retry,
        )

    return _make_context


@pytest.fixture
def make_ti_context_dict(make_ti_context: MakeTIContextCallable) -> MakeTIContextDictCallable:
    """Factory for creating context dictionaries suited for API Server response."""

    def _make_context_dict(
        dag_id: str = "test_dag",
        run_id: str = "test_run",
        logical_date: str | datetime = "2024-12-01T00:00:00Z",
        data_interval_start: str | datetime = "2024-12-01T00:00:00Z",
        data_interval_end: str | datetime = "2024-12-01T01:00:00Z",
        clear_number: int = 0,
        start_date: str | datetime = "2024-12-01T00:00:00Z",
        run_after: str | datetime = "2024-12-01T00:00:00Z",
        run_type: str = "manual",
        task_reschedule_count: int = 0,
        conf=None,
        consumed_asset_events: Sequence[AssetEventDagRunReference] = (),
    ) -> dict[str, Any]:
        context = make_ti_context(
            dag_id=dag_id,
            run_id=run_id,
            logical_date=logical_date,
            data_interval_start=data_interval_start,
            data_interval_end=data_interval_end,
            clear_number=clear_number,
            start_date=start_date,
            run_after=run_after,
            run_type=run_type,
            conf=conf,
            task_reschedule_count=task_reschedule_count,
            consumed_asset_events=consumed_asset_events,
        )
        return context.model_dump(exclude_unset=True, mode="json")

    return _make_context_dict


@pytest.fixture
def patched_secrets_masker():
    from airflow.sdk.execution_time.secrets_masker import SecretsMasker

    secrets_masker = SecretsMasker()
    with patch("airflow.sdk.execution_time.secrets_masker._secrets_masker", return_value=secrets_masker):
        yield secrets_masker
