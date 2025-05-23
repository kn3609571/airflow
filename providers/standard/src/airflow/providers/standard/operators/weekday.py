#
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

from collections.abc import Iterable
from typing import TYPE_CHECKING

from airflow.providers.standard.operators.branch import BaseBranchOperator
from airflow.providers.standard.utils.weekday import WeekDay
from airflow.utils import timezone

if TYPE_CHECKING:
    try:
        from airflow.sdk.definitions.context import Context
    except ImportError:
        # TODO: Remove once provider drops support for Airflow 2
        from airflow.utils.context import Context


class BranchDayOfWeekOperator(BaseBranchOperator):
    """
    Branches into one of two lists of tasks depending on the current day.

    For more information on how to use this operator, take a look at the guide:
    :ref:`howto/operator:BranchDayOfWeekOperator`

    **Example** (with single day):

    .. code-block:: python

        from airflow.providers.standard.operators.empty import EmptyOperator
        from airflow.operators.weekday import BranchDayOfWeekOperator

        monday = EmptyOperator(task_id="monday")
        other_day = EmptyOperator(task_id="other_day")

        monday_check = BranchDayOfWeekOperator(
            task_id="monday_check",
            week_day="Monday",
            use_task_logical_date=True,
            follow_task_ids_if_true="monday",
            follow_task_ids_if_false="other_day",
        )
        monday_check >> [monday, other_day]

    **Example** (with :class:`~airflow.utils.weekday.WeekDay` enum):

    .. code-block:: python

        # import WeekDay Enum
        from airflow.providers.standard.utils.weekday import WeekDay
        from airflow.providers.standard.operators.empty import EmptyOperator
        from airflow.operators.weekday import BranchDayOfWeekOperator

        workday = EmptyOperator(task_id="workday")
        weekend = EmptyOperator(task_id="weekend")
        weekend_check = BranchDayOfWeekOperator(
            task_id="weekend_check",
            week_day={WeekDay.SATURDAY, WeekDay.SUNDAY},
            use_task_logical_date=True,
            follow_task_ids_if_true="weekend",
            follow_task_ids_if_false="workday",
        )
        # add downstream dependencies as you would do with any branch operator
        weekend_check >> [workday, weekend]

    :param follow_task_ids_if_true: task_id, task_group_id, or a list of task_ids and/or task_group_ids
        to follow if criteria met.
    :param follow_task_ids_if_false: task_id, task_group_id, or a list of task_ids and/or task_group_ids
        to follow if criteria not met.
    :param week_day: Day of the week to check (full name). Optionally, a set
        of days can also be provided using a set. Example values:

        * ``"MONDAY"``,
        * ``{"Saturday", "Sunday"}``
        * ``{WeekDay.TUESDAY}``
        * ``{WeekDay.SATURDAY, WeekDay.SUNDAY}``

        To use `WeekDay` enum, import it from `airflow.utils.weekday`

    :param use_task_logical_date: If ``True``, uses task's logical date to compare
        with is_today. Execution Date is Useful for backfilling.
        If ``False``, uses system's day of the week.
    """

    def __init__(
        self,
        *,
        follow_task_ids_if_true: str | Iterable[str],
        follow_task_ids_if_false: str | Iterable[str],
        week_day: str | Iterable[str] | WeekDay | Iterable[WeekDay],
        use_task_logical_date: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.follow_task_ids_if_true = follow_task_ids_if_true
        self.follow_task_ids_if_false = follow_task_ids_if_false
        self.week_day = week_day
        self.use_task_logical_date = use_task_logical_date
        self._week_day_num = WeekDay.validate_week_day(week_day)

    def choose_branch(self, context: Context) -> str | Iterable[str]:
        if self.use_task_logical_date:
            now = context.get("logical_date")
            if not now:
                dag_run = context.get("dag_run")
                now = dag_run.run_after  # type: ignore[union-attr, assignment]
        else:
            now = timezone.make_naive(timezone.utcnow(), self.dag.timezone)

        if now.isoweekday() in self._week_day_num:  # type: ignore[union-attr]
            return self.follow_task_ids_if_true
        return self.follow_task_ids_if_false
