SELECT *
FROM system.compute.node_timeline
WHERE start_time < :end_utc
  AND end_time >= :start_utc
ORDER BY start_time, cluster_id, instance_id
