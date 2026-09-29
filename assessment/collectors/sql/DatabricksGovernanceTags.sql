SELECT
  account_id,
  workspace_id,
  usage_start_time,
  sku_name,
  usage_quantity,
  custom_tags,
  usage_metadata,
  identity_metadata
FROM system.billing.usage
WHERE usage_start_time >= :start_utc
  AND usage_start_time < :end_utc
ORDER BY usage_start_time, workspace_id
