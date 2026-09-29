SELECT *
FROM system.query.history
WHERE start_time >= :start_utc
  AND start_time < :end_utc
ORDER BY start_time, workspace_id, statement_id
