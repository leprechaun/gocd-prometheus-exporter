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

go = Yagocd(
	server=os.getenv("GOCD_URL"),
	auth=(os.getenv("GOCD_USERNAME"), os.getenv("GOCD_PASSWORD")),
	options={
		'verify': os.getenv("GOCD_SSL_VERIFY", True) in ["true", "True", "yes", "1"]
	}
)

start_http_server(8000)

# go.stages.get(pipeline_name="nginx-static-app-build", pipeline_counter="145", stage_name="build-image", stage_counter="3").jobs()

watched = set([])

watched_jobs = set([])

job_count_by_state = Gauge('gocd_job_count_by_state', 'Number of jobs with status', ["state"])

while True:
	try:
		tree = ET.fromstring(requests.get('https://gocd.k8s.fscker.org/go/cctray.xml').text)
		#tree = ET.fromstring(cctray.text)

		for project in tree.findall("Project"):
			#print(project.attrib)
			# {'lastBuildLabel': '0.1-21-97dfc48d', 'name': 'gocd-exporter-build :: build-image', 'activity': 'Sleeping', 'lastBuildStatus': 'Success', 'webUrl': 'https://gocd.k8s.fscker.org/go/pipelines/gocd-exporter-build/21/build-image/1', 'lastBuildTime': '2018-04-28T10:42:45'}
			if project.attrib["activity"] != "Sleeping":
				pipeline = project.attrib["name"].split(" :: ")
				if len(pipeline) == 3:
					parsedLink = project.attrib["webUrl"].split("/")
					# print project.attrib["name"] + " " + project.attrib["activity"] + " " + parsedLink[8] + " " + parsedLink[10]
					to_add = (
						pipeline[0],
						pipeline[1],
						pipeline[2],
						parsedLink[8],
						parsedLink[10]
					)
					if to_add not in watched:
						#print("add", to_add)
						watched.add(to_add)

		#go.pipelines["nginx-static-app-deploy-prod"][67]["dummer-stage"]
		to_remove = set([])


		job_counts_by_state = {
			"Scheduled": 0,
			"Assigned": 0,
			"Preparing": 0,
			"Building": 0,
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
			s = go.pipelines[ i[0] ][ i[3] ][ i[1] ]
			#print("remove", i, s.data.result )
			#print(s.data)
			#print('remove', i)
			watched.remove(i)

		for state in job_counts_by_state:
			job_count_by_state.labels(
				state=state
			).set(job_counts_by_state[state])

		time.sleep(1)
	except(requests.exceptions.ConnectionError):
		pass
