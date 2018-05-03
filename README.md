# gocd-prometheus

A most basic, and probably flawed gocd stats exporter for GoCD.

The exposed metrics are most likely going to change as I find better ways to express the numbers I'm looking for.

Open to input. Issue/PR to your hearts content.

## Exposed Metrics

Gauge for number of tasks in each state.

```
# HELP gocd_job_count_by_state Number of jobs with status
# TYPE gocd_job_count_by_state gauge
gocd_job_count_by_state{gocd_url="$GOCD_URL",state="$STATE"} $COUNT

Where $STATE is on of {Scheduled,Assigned,Preparing,Building,Completing}
```

```
# HELP gocd_job_time_spent_by_state time spent in jobs
# TYPE gocd_job_time_spent_by_state summary
gocd_job_time_spent_by_state_count{gocd_url="$GOCD_URL",job="$JOB",job_key="$PIPELINE_GROUP/$PIPELINE/$STAGE/$JOB",pipeline="$PIPELINE",pipeline_group="$PIPELINE_GROUP",stage="$STAGE",stage_key="$PIPELINE_GROUP/$PIPELINE/$STAGE",state="$STATE"} $TIME_SPENT

Where $STATE is on of {Scheduled,Assigned,Preparing,Building,Completing}

This only increments once a stage is completed.
```

```
# HELP gocd_job_latest_date pass or fail of the latest job run
# TYPE gocd_job_latest_date gauge
gocd_job_latest_date{gocd_url="$GOCD_URL",job="$JOB",job_key="$PIPELINE_GROUP/$PIPELINE/$STAGE/$JOB",pipeline="$PIPELINE",pipeline_group="$PIPELINE_GROUP",stage="$STAGE",stage_key="$PIPELINE_GROUP/$PIPELINE/$STAGE", result="$RESULT"} 1525350072.0

Where $RESULT is one of {Failed,Passed}
```

## Example dashboard

![example dashboard](https://i.imgur.com/Ym6wIrk.png)
