SELECT *
FROM system.access.audit
WHERE event_time >= :start_utc
  AND event_time < :end_utc
  AND service_name IN ('accounts', 'clusters', 'jobs', 'pipelines', 'sql', 'unityCatalog')
ORDER BY event_time, workspace_id
