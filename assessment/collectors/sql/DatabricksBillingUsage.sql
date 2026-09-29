SELECT *
FROM system.billing.usage
WHERE usage_start_time >= :start_utc
  AND usage_start_time < :end_utc
ORDER BY usage_start_time, workspace_id
