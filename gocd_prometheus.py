import urllib3
import yaml
import traceback
import requests
import os
import sys
import random
import time
import xml.etree.ElementTree as ET
from yagocd import Yagocd

from prometheus_client import start_http_server
from prometheus_client import Histogram
from prometheus_client import Counter
from prometheus_client import Summary
from prometheus_client import Gauge


urllib3.disable_warnings()


GOCD_URL = os.getenv("GOCD_URL")
EXPOSE_PORT = os.getenv("PROMETHEUS_PORT", 8000)
GOCD_USERNAME = os.getenv("GOCD_USERNAME")
GOCD_PASSWORD = os.getenv("GOCD_PASSWORD")
GOCD_SSL_VERIFY = os.getenv("GOCD_SSL_VERIFY", True) in [
  "true", "True", "yes", "1"
]

if GOCD_USERNAME is not None and GOCD_PASSWORD is not None:
    credentials = (GOCD_USERNAME, GOCD_PASSWORD)
else:
    credentials = None

start_http_server(EXPOSE_PORT)

go = Yagocd(
    server=GOCD_URL,
    auth=credentials,
    options={
        'verify': GOCD_SSL_VERIFY
    }
)


watched = set([])
watched_jobs = set([])

job_count_by_state = Gauge(
    'gocd_job_count_by_state',
    'Number of jobs with status',
    ["gocd_url", "state"]
)

latest_stage_result = Gauge(
    'gocd_stage_latest_result',
    'pass or fail of the latest stage run',
    [
        "gocd_url",
        "pipeline_group",
        "pipeline",
        "stage",
        "stage_key"
    ]
)

latest_stage_date = Gauge(
    'gocd_stage_latest_date',
    'pass or fail of the latest stage run',
    [
        "gocd_url",
        "pipeline_group",
        "pipeline",
        "stage",
        "stage_key",
        "result"
    ]
)

latest_job_result = Gauge(
    'gocd_job_latest_result',
    'pass or fail of the latest job run',
    [
        "gocd_url",
        "pipeline_group",
        "pipeline",
        "stage",
        "stage_key",
        "job",
        "job_key"
    ]
)

stage_results = Counter(
  'gocd_stage_results',
  'stage counts by result',
  [
    "gocd_url",
    "pipeline_group",
    "pipeline",
    "stage",
    "stage_key",
    "result"
  ]
)


job_results = Counter(
  'gocd_job_results',
  'job counts by result',
  [
    "gocd_url",
    "pipeline_group",
    "pipeline",
    "stage",
    "stage_key",
    "job",
    "job_key",
    "result"
  ]
)

latest_job_date = Gauge(
    'gocd_job_latest_date',
    'pass or fail of the latest job run',
    [
        "gocd_url",
        "pipeline_group",
        "pipeline",
        "stage",
        "stage_key",
        "job",
        "job_key",
        "result"
    ]
)

job_time_spent_by_state = Summary(
    'gocd_job_time_spent_by_state',
    'time spent in jobs',
    [
      "gocd_url",
      "pipeline_group",
      "pipeline",
      "stage",
      "stage_key",
      "job",
      "job_key",
      "state"
    ]
)

while True:
    try:
        tree = ET.fromstring(
          requests.get(GOCD_URL + 'go/cctray.xml', verify=GOCD_SSL_VERIFY).text
        )

        for project in tree.findall("Project"):
            if project.attrib["activity"] != "Sleeping":
                pipeline = project.attrib["name"].split(" :: ")
                if len(pipeline) == 3:
                    parsedLink = project.attrib["webUrl"].split("/")
                    to_add = (
                        pipeline[0],
                        pipeline[1],
                        pipeline[2],
                        parsedLink[8],
                        parsedLink[10]
                    )
                    if to_add not in watched:
                        watched.add(to_add)

        to_remove = set([])

        job_counts_by_state = {
            "Scheduled": 0,
            "Assigned": 0,
            "Preparing": 0,
            "Building": 0,
            "Completing": 0,
            "Completed": 0
        }

        for i in watched:
            pipeline = go.pipelines[i[0]]
            instance = pipeline[i[3]]
            stage = instance[i[1]]
            jobs = go.stages.get(
                pipeline_name=pipeline.data.name,
                pipeline_counter=instance.data.counter,
                stage_name=stage.data.name,
                stage_counter=stage.data.counter
            ).jobs()

            for job in jobs:
                job_counts_by_state[job.data.state] += 1

            if stage.data.result in ["Passed", "Cancelled", "Failed"]:
                to_remove.add(i)

        for i in to_remove:
            pipeline = go.pipelines[i[0]]
            instance = pipeline[i[3]]
            stage = instance[i[1]]
            jobs = go.stages.get(
                pipeline_name=pipeline.data.name,
                pipeline_counter=instance.data.counter,
                stage_name=stage.data.name,
                stage_counter=stage.data.counter
            ).jobs()

            stage_key = "/".join([
              pipeline.group, pipeline.data.name, stage.data.name
            ])

            job_key = "/".join([
              pipeline.group,
              pipeline.data.name,
              stage.data.name,
              job.data.name
            ])

            for job in jobs:
                transitions = job.data.job_state_transitions
                dates = {
                  x.state: x.state_change_time for x in transitions
                }

                scheduled = dates["Assigned"] - dates["Scheduled"]
                job_time_spent_by_state.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key,
                    state="Scheduled"
                ).observe(scheduled / 1000)

                assigned = dates["Preparing"] - dates["Assigned"]
                job_time_spent_by_state.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key,
                    state="Assigned"
                ).observe(assigned / 1000)

                preparing = dates["Building"] - dates["Preparing"]
                job_time_spent_by_state.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key,
                    state="Preparing"
                ).observe(preparing / 1000)

                building = dates["Completing"] - dates["Building"]
                job_time_spent_by_state.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key,
                    state="Building"
                ).observe(building / 1000)

                completing = dates["Completed"] - dates["Completing"]
                job_time_spent_by_state.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key,
                    state="Completing"
                ).observe(completing / 1000)

                if job.data.result == "Passed":
                    up = 1
                else:
                    up = 0

                job_results.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key,
                    result=job.data.result
                ).inc(1)

                latest_job_date.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key,
                    result=job.data.result
                ).set(int(dates["Completed"]) / 1000)

                latest_job_result.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    job=job.data.name,
                    job_key=job_key
                ).set(up)

            results = set([job.data.result for job in jobs])
            if len(results) == 1:
                if list(results)[0] == "Passed":
                    stage_result = 1
                    stage_result_string = "Passed"
                elif list(results)[0] == "Failed":
                    stage_result_string = "Failed"
                    stage_result = 0

                stage_results.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    result=stage_result_string
                ).inc(1)

                latest_stage_result.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key
                ).set(stage_result)

                latest_stage_date.labels(
                    gocd_url=GOCD_URL,
                    pipeline_group=pipeline.group,
                    pipeline=pipeline.data.name,
                    stage=stage.data.name,
                    stage_key=stage_key,
                    result=stage_result_string
                ).set(int(max(dates.values()) / 1000))

            watched.remove(i)

        for state in job_counts_by_state:
            job_count_by_state.labels(
                gocd_url=GOCD_URL,
                state=state
            ).set(job_counts_by_state[state])

        time.sleep(1)

    except(requests.exceptions.ConnectionError):
        pass
