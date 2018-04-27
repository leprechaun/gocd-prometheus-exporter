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


job_duration = Summary('gocd_pipeline_stage_job_duration', 'length of jobs running on gocd', ["pipeline_group", "pipeline", "stage", "job"])
group_count = Counter('gocd_group_count', 'gocd group count', ["pipeline_group"])
pipeline_count = Counter('gocd_pipeline_count', 'gocd pipeline count', ["pipeline_group", "pipeline"])
stage_count = Counter('gocd_pipeline_stage_count', 'gocd stage count', ["pipeline_group", "pipeline", "stage", "result"])
job_count = Counter('gocd_pipeline_stage_job_counter', 'gocd job count', ["pipeline_group", "pipeline", "stage", "job"])
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
						try:
							props = job.properties.items()
							result = [a for a in props if a[0] == "cruise_job_duration" ]
							duration = result[0][1]
						except:
							duration = "unknown"
							continue

						obj = {
							"pipeline": {
								"group": pipeline.group,
								"name": pipeline.data.name,
								"counter": instance.data.counter
							},
							"stage": {
								"name": stage.data.name,
								"counter": stage.data.counter,
								"result": stage.data.result,
							},
							"job": {
								"name": job.data.name,
								"id": job.data.id,
								"duration": int(job.properties["cruise_job_duration"])
							}
						}

						job_key = "-".join([obj["pipeline"]["group"], obj["stage"]["name"], obj["job"]["name"]])

						if not is_first_run:
							if obj["job"]["id"] > largest_id_by_job.get( job_key, 0 ):
								print(" - ".join( [job_key, str(obj["job"]["duration"])]))
								largest_id_by_job[ job_key ] = obj["job"]["id"]
								group_count.labels(
										pipeline_group = obj["pipeline"]["group"]
								).inc(1)

								pipeline_count.labels(
										pipeline_group = obj["pipeline"]["group"],
										pipeline = obj["pipeline"]["name"]
								).inc(1)

								stage_count.labels(
										pipeline_group = obj["pipeline"]["group"],
										pipeline = obj["pipeline"]["name"],
										stage = obj["stage"]["name"],
										result = obj["stage"]["result"]
								).inc(1)

								job_count.labels(
										pipeline_group = obj["pipeline"]["group"],
										pipeline = obj["pipeline"]["name"],
										stage = obj["stage"]["name"],
										job = obj["job"]["name"]
								).inc(1)


								job_duration.labels(
									pipeline_group = obj["pipeline"]["group"],
									pipeline = obj["pipeline"]["name"],
									stage = obj["stage"]["name"],
									job = obj["job"]["name"]
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
