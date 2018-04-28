import urllib3
urllib3.disable_warnings()

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

go = Yagocd(
	server=os.getenv("GOCD_URL"),
	auth=(os.getenv("GOCD_USERNAME"), os.getenv("GOCD_PASSWORD")),
	options={
		'verify': os.getenv("GOCD_SSL_VERIFY", True) in ["true", "True", "yes", "1"]
	}
)


group_count = Counter('gocd_group_count', 'gocd group count', ["pipeline_group"])
pipeline_count = Counter('gocd_pipeline_count', 'gocd pipeline count', ["pipeline_group", "pipeline", "pipeline_key"])
stage_count = Counter('gocd_pipeline_stage_count', 'gocd stage count', ["pipeline_group", "pipeline", "stage", "result", "pipeline_key", "stage_key"])
job_count = Counter('gocd_pipeline_stage_job_counter', 'gocd job count', ["pipeline_group", "pipeline", "stage", "job", "pipeline_key", "stage_key", "job_key", "state"])
job_duration = Summary('gocd_pipeline_stage_job_duration', 'length of jobs running on gocd', ["pipeline_group", "pipeline", "stage", "job", "pipeline_key", "stage_key", "job_key"])
start_http_server( int(os.getenv("PROMETHEUS_PORT") or 8000) )

largest_id_by_job = {}
is_first_run = True

while True:
	try:
		for pipeline in go.pipelines:   # Iterate over all pipelines
			try:
				instance = pipeline.last()
				if instance is None:
					continue

				for stage in instance:  # Iterate over each stages of some pipeline instance
					for job in stage:   # Iterate over each job of some pipeline
					# print([ pipeline.data.id ], [job.data.id, job.data.name, job.data.result]])
						obj = {
							"pipeline": {
								"key": pipeline.group + "/" + pipeline.data.name,
								"group": pipeline.group,
								"name": pipeline.data.name,
								"counter": instance.data.counter
							},
							"stage": {
								"key": pipeline.group + "/" + pipeline.data.name + "/" + stage.data.name,
								"name": stage.data.name,
								"counter": stage.data.counter,
								"result": stage.data.result,
							},
							"job": {
								"key": pipeline.group + "/" + pipeline.data.name + "/" + stage.data.name + "/" + job.data.name,
								"name": job.data.name,
								"id": job.data.id,
								"state": job.data.state
							}
						}


						if job.data.state == "Completed":
							duration = job.properties["cruise_job_duration"]
						else:
							duration = 0

						obj["job"]["duration"] = int(duration)
						print(obj["job"]["key"] + " - " + str(job.data.state))

						if not is_first_run:
							if obj["job"]["id"] > largest_id_by_job.get( obj["job"]["key"], 0 ):
								print(" - ".join( [obj["job"]["key"], str(obj["job"]["duration"])]))
								largest_id_by_job[ obj["job"]["key"] ] = obj["job"]["id"]
								group_count.labels(
										pipeline_group = obj["pipeline"]["group"]
								).inc(1)

								pipeline_count.labels(
										pipeline_group = obj["pipeline"]["group"],
										pipeline = obj["pipeline"]["name"],
										pipeline_key = obj["pipeline"]["key"]
								).inc(1)

								stage_count.labels(
									pipeline_group = obj["pipeline"]["group"],
									pipeline = obj["pipeline"]["name"],
									stage = obj["stage"]["name"],
									result = obj["stage"]["result"],
									pipeline_key = obj["pipeline"]["key"],
									stage_key = obj["stage"]["key"]
								).inc(1)

								job_count.labels(
									pipeline_group = obj["pipeline"]["group"],
									pipeline = obj["pipeline"]["name"],
									stage = obj["stage"]["name"],
									job = obj["job"]["name"],
									pipeline_key = obj["pipeline"]["key"],
									stage_key = obj["stage"]["key"],
									job_key = obj["job"]["key"],
									state =  obj["job"]["state"]
								).inc(1)


								job_duration.labels(
									pipeline_group = obj["pipeline"]["group"],
									pipeline = obj["pipeline"]["name"],
									stage = obj["stage"]["name"],
									job = obj["job"]["name"],
									pipeline_key = obj["pipeline"]["key"],
									stage_key = obj["stage"]["key"],
									job_key = obj["job"]["key"]
								).observe(
									obj["job"]["duration"]
								)
							else:
								pass
			except TypeError:
				raise
				#traceback.print_tb(sys.exc_info()[2])
				#pass
			except:
				print "Unexpected error:", sys.exc_info()[0]
				raise
	except requests.exceptions.ConnectionError:
		print "Unexpected error:", sys.exc_info()[0]
		#raise
		pass

	print("looped")
	is_first_run = False
	time.sleep( int(os.getenv("SAMPLE_FREQUENCY") or 10) )
