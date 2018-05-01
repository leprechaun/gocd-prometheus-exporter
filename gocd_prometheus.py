import urllib3
urllib3.disable_warnings()

import yaml
import traceback
import requests
import os
import sys
import random
import time

from yagocd import Yagocd

from prometheus_client import start_http_server
from prometheus_client import Histogram
from prometheus_client import Counter
from prometheus_client import Summary
from prometheus_client import Gauge

import xml.etree.ElementTree as ET

GOCD_SSL_VERIFY = os.getenv("GOCD_SSL_VERIFY", True) in ["true", "True", "yes", "1"]
GOCD_URL = os.getenv("GOCD_URL")
EXPOSE_PORT = os.getenv("PROMETHEUS_PORT", 8000)

start_http_server(EXPOSE_PORT)

go = Yagocd(
	server = GOCD_URL,
	auth=(os.getenv("GOCD_USERNAME"), os.getenv("GOCD_PASSWORD")),
	options = {
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

job_time_spent_by_state = Summary(
	'gocd_job_time_spent_by_state',
	'time spent in jobs',
	["gocd_url", "pipeline_group", "pipeline", "stage", "stage_key", "job", "job_key", "state"]
)

while True:
	try:
		tree = ET.fromstring(requests.get( os.getenv("GOCD_URL") + 'go/cctray.xml', verify=GOCD_SSL_VERIFY).text)

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
			#print(stage.data.result, stage.data)
			pipeline = go.pipelines[ i[0] ]
			instance = pipeline[ i[3] ]
			stage = instance[ i[1] ]
			jobs = go.stages.get(
				pipeline_name = pipeline.data.name,
				pipeline_counter = instance.data.counter,
				stage_name = stage.data.name,
				stage_counter = stage.data.counter
			).jobs()

			for job in jobs:
				#print(pipeline.data.name, stage.data.name, job.data.name, job.data.state, job.data.result)
				job_counts_by_state[job.data.state] += 1

			if stage.data.result in ["Passed", "Cancelled", "Failed"]:
				to_remove.add(i)
		
		for i in to_remove:
			pipeline = go.pipelines[ i[0] ]
			instance = pipeline[ i[3] ]
			stage = instance[ i[1] ]
			jobs = go.stages.get(
				pipeline_name = pipeline.data.name,
				pipeline_counter = instance.data.counter,
				stage_name = stage.data.name,
				stage_counter = stage.data.counter
			).jobs()

			# ["pipeline_group", "pipeline", "stage", "stage_key", "job", "job_key"]
			stage_key = "/".join([ pipeline.group, pipeline.data.name, stage.data.name])
			job_key = "/".join([ pipeline.group, pipeline.data.name, stage.data.name, job.data.name])
			# job_time_spent_by_state = Summary(
			for job in jobs:
				state_dates = {x.state: x.state_change_time for x in job.data.job_state_transitions}
				print(state_dates)

				scheduled = state_dates["Assigned"] - state_dates["Scheduled"]
				assigned = state_dates["Preparing"] - state_dates["Assigned"]
				preparing = state_dates["Building"] - state_dates["Preparing"]
				building = state_dates["Completing"] - state_dates["Building"]
				completing = state_dates["Completed"] - state_dates["Completing"]

				job_time_spent_by_state.labels(
					gocd_url = GOCD_URL,
					pipeline_group = pipeline.group,
					pipeline = pipeline.data.name,
					stage = stage.data.name,
					stage_key = stage_key,
					job = job.data.name,
					job_key = job_key,
					state = "Scheduled"
				).observe(scheduled / 1000)
				job_time_spent_by_state.labels(
					gocd_url = GOCD_URL,
					pipeline_group = pipeline.group,
					pipeline = pipeline.data.name,
					stage = stage.data.name,
					stage_key = stage_key,
					job = job.data.name,
					job_key = job_key,
					state = "Assigned"
				).observe(assigned / 1000)
				job_time_spent_by_state.labels(
					gocd_url = GOCD_URL,
					pipeline_group = pipeline.group,
					pipeline = pipeline.data.name,
					stage = stage.data.name,
					stage_key = stage_key,
					job = job.data.name,
					job_key = job_key,
					state = "Preparing"
				).observe(preparing / 1000)
				job_time_spent_by_state.labels(
					gocd_url = GOCD_URL,
					pipeline_group = pipeline.group,
					pipeline = pipeline.data.name,
					stage = stage.data.name,
					stage_key = stage_key,
					job = job.data.name,
					job_key = job_key,
					state = "Building"
				).observe(building / 1000)
				job_time_spent_by_state.labels(
					gocd_url = GOCD_URL,
					pipeline_group = pipeline.group,
					pipeline = pipeline.data.name,
					stage = stage.data.name,
					stage_key = stage_key,
					job = job.data.name,
					job_key = job_key,
					state = "Completing"
				).observe(completing / 1000)

			watched.remove(i)

		for state in job_counts_by_state:
			job_count_by_state.labels(
				gocd_url = GOCD_URL,
				state=state
			).set(job_counts_by_state[state])

		time.sleep(1)

	except(requests.exceptions.ConnectionError):
		pass
