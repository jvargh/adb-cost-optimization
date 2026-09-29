SELECT *
FROM system.lakeflow.job_run_timeline
WHERE period_start_time < :end_utc
  AND period_end_time >= :start_utc
ORDER BY period_start_time, workspace_id, job_id, run_id
