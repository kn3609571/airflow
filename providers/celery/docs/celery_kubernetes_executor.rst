 .. Licensed to the Apache Software Foundation (ASF) under one
    or more contributor license agreements.  See the NOTICE file
    distributed with this work for additional information
    regarding copyright ownership.  The ASF licenses this file
    to you under the Apache License, Version 2.0 (the
    "License"); you may not use this file except in compliance
    with the License.  You may obtain a copy of the License at

 ..   http://www.apache.org/licenses/LICENSE-2.0

 .. Unless required by applicable law or agreed to in writing,
    software distributed under the License is distributed on an
    "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
    KIND, either express or implied.  See the License for the
    specific language governing permissions and limitations
    under the License.

CeleryKubernetes Executor
=========================

.. note::

    As of Airflow 2.7.0, you need to install both the ``celery`` and ``cncf.kubernetes`` provider package to use
    this executor. This can be done by installing ``apache-airflow-providers-celery>=3.3.0`` and
    ``apache-airflow-providers-cncf-kubernetes>=7.4.0`` or by installing Airflow
    with the ``celery`` and ``cncf.kubernetes`` extras: ``pip install 'apache-airflow[celery,cncf.kubernetes]'``.

.. note::

    ``CeleryKubernetesExecutor`` is no longer supported starting from Airflow 3.0.0. You can use the
    :ref:`Using Multiple Executors Concurrently <using-multiple-executors-concurrently>` feature instead,
    which provides equivalent functionality in a more flexible manner.

The :class:`~airflow.providers.celery.executors.celery_kubernetes_executor.CeleryKubernetesExecutor` allows users
to run simultaneously a ``CeleryExecutor`` and a ``KubernetesExecutor``.
An executor is chosen to run a task based on the task's queue.

``CeleryKubernetesExecutor`` inherits the scalability of the ``CeleryExecutor`` to
handle the high load at the peak time and runtime isolation of the ``KubernetesExecutor``.

The configuration parameters of the Celery Executor can be found in the Celery provider's :doc:`configurations-ref`.


When to use CeleryKubernetesExecutor
####################################

The ``CeleryKubernetesExecutor`` should only be used at certain cases, given that
it requires setting up the ``CeleryExecutor`` and the ``KubernetesExecutor``.

We recommend considering the ``CeleryKubernetesExecutor`` when your use case meets:

1. The number of tasks needed to be scheduled at the peak exceeds the scale that your Kubernetes cluster
   can comfortably handle

2. A relative small portion of your tasks requires runtime isolation.

3. You have plenty of small tasks that can be executed on Celery workers
   but you also have resource-hungry tasks that will be better to run in predefined environments.
