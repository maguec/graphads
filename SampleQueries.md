Go ahead and create the communities

```sql
EXPORT DATA OPTIONS(
  format = 'CLOUD_SPANNER',
  table = 'CommunityResults',
  write_mode = 'update_ignore_all'
) AS
GRAPH GraphAds
CALL ModularityClustering(
  node_labels => ['Users', 'Subreddits'],
  edge_labels => ['MEMBER_OF']
)
YIELD node, cluster
RETURN node.UserId AS UserId, cluster AS RawClusterId;
```

```sql
GRAPH GraphAds
MATCH (p:Posts)-[:POSTED_TO]->(s:Subreddits)<-[:MEMBER_OF]-(u:Users)-[:IN_COMMUNITY]->(c:CommunityResults)
WHERE p.CompanyName = 'Global' 
  AND c.CommunityId IS NOT NULL
RETURN c.CommunityId, AVG(p.SentimentScore) AS avg_sentiment
GROUP BY c.CommunityId
ORDER BY avg_sentiment DESC
LIMIT 10;
```
