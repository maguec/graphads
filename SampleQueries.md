Go ahead and create the communities

```sql
EXPORT DATA OPTIONS(
  format = 'CLOUD_SPANNER',
  table = 'TempCommunityResults',
  write_mode = 'upsert_ignore_all'
) AS
GRAPH GraphAds
CALL ModularityClustering(
  node_labels => ['Users', 'Subreddits'],
  edge_labels => ['MEMBER_OF']
)
YIELD node, cluster
RETURN node.GraphId AS GraphId, cluster AS community_id;
```
