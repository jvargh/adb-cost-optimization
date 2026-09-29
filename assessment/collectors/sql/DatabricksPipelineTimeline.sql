SELECT *
FROM system.lakeflow.pipeline_update_timeline
WHERE period_start_time < :end_utc
  AND period_end_time >= :start_utc
ORDER BY period_start_time, workspace_id, pipeline_id, update_id
