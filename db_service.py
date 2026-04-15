import uuid
from google.cloud import spanner


class SpannerService:
    def __init__(self, project_id: str, instance_id: str, database_id: str):
        self.client = spanner.Client(project=project_id, disable_builtin_metrics=True)
        self.instance = self.client.instance(instance_id)
        self.database = self.instance.database(database_id)

    def get_users(self):
        """Fetch all users from the Users table."""
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql("SELECT UserId, Username FROM Users")
            return {row[1]: row[0] for row in results}  # Username: UserId mapping

    def get_subreddits(self):
        """Fetch all subreddits from the Subreddits table."""
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql("SELECT SubredditId, Name FROM Subreddits")
            return {row[1]: row[0] for row in results}  # Name: SubredditId mapping

    def get_unique_companies(self):
        """Fetch unique company names from the Posts table."""
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                "SELECT DISTINCT CompanyName FROM Posts WHERE CompanyName IS NOT NULL"
            )
            return [row[0] for row in results]

    def get_company_analysis(self, company_name: str):
        """
        Get min, max, and avg sentiment score per subreddit for a given company.
        Uses Spanner Graph (GQL) via GRAPH_TABLE.
        """
        query = """
            SELECT 
                SubredditName,
                MIN(SentimentScore) as MinScore,
                MAX(SentimentScore) as MaxScore,
                AVG(SentimentScore) as AvgScore,
                COUNT(*) as Mentions
            FROM GRAPH_TABLE(GraphAds
                MATCH (p:Posts)-[post_edge:POSTED_TO]->(s:Subreddits)
                WHERE p.CompanyName = @company_name
                COLUMNS(s.Name as SubredditName, p.SentimentScore)
            )
            GROUP BY SubredditName
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={"company_name": company_name},
                param_types={"company_name": spanner.param_types.STRING},
            )
            return [
                {
                    "subreddit": row[0],
                    "min": row[1],
                    "max": row[2],
                    "avg": round(row[3], 2),
                    "mentions": row[4],
                }
                for row in results
            ]

    def get_unique_products(self, company_name: str):
        """Fetch unique product names for a specific company from the Posts table."""
        query = "SELECT DISTINCT ProductName FROM Posts WHERE CompanyName = @company_name AND ProductName IS NOT NULL"
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={"company_name": company_name},
                param_types={"company_name": spanner.param_types.STRING},
            )
            return [row[0] for row in results]

    def get_unique_subreddits_for_drill_down(
        self, company_name: str, product_name: str
    ):
        """Fetch unique subreddits that have posts for a specific company and product."""
        query = """
            SELECT DISTINCT s.Name
            FROM Posts p
            JOIN Posts2Subreddit p2s ON p.PostId = p2s.PostId
            JOIN Subreddits s ON p2s.SubredditId = s.SubredditId
            WHERE p.CompanyName = @company_name 
              AND p.ProductName = @product_name
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={"company_name": company_name, "product_name": product_name},
                param_types={
                    "company_name": spanner.param_types.STRING,
                    "product_name": spanner.param_types.STRING,
                },
            )
            return [row[0] for row in results]

    def get_sentiment_drill_down(
        self, company_name: str, product_name: str, subreddit_name: str
    ):
        """
        Get username, post text, and sentiment score for posts matching company, product, and subreddit.
        Uses Graph to connect Posts to Users via Subreddits.
        """
        query = """
            GRAPH GraphAds
            MATCH (p:Posts)-[:POSTED_TO]->(s:Subreddits)<-[:MEMBER_OF]-(u:Users)
            WHERE p.CompanyName = @company_name 
              AND p.ProductName = @product_name
              AND s.Name = @subreddit_name
            RETURN u.Username, p.PostText, p.SentimentScore
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={
                    "company_name": company_name,
                    "product_name": product_name,
                    "subreddit_name": subreddit_name,
                },
                param_types={
                    "company_name": spanner.param_types.STRING,
                    "product_name": spanner.param_types.STRING,
                    "subreddit_name": spanner.param_types.STRING,
                },
            )
            return [
                {"username": row[0], "text": row[1], "score": row[2]} for row in results
            ]

    def get_post_texts(self, company_name: str, product_name: str, subreddit_name: str):
        """Fetch all post texts and sentiment scores for a specific company, product, and subreddit using Graph."""
        query = """
            GRAPH GraphAds
            MATCH (p:Posts)-[:POSTED_TO]->(s:Subreddits)
            WHERE p.CompanyName = @company_name 
              AND p.ProductName = @product_name
              AND s.Name = @subreddit_name
            RETURN p.PostText, p.SentimentScore
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={
                    "company_name": company_name,
                    "product_name": product_name,
                    "subreddit_name": subreddit_name,
                },
                param_types={
                    "company_name": spanner.param_types.STRING,
                    "product_name": spanner.param_types.STRING,
                    "subreddit_name": spanner.param_types.STRING,
                },
            )
            return [{"text": row[0], "score": row[1]} for row in results]

    def get_product_analysis(self, company_name: str, product_name: str):
        """
        Get min, max, and avg sentiment score per subreddit for a given company and product.
        Uses Spanner Graph (GQL) via GRAPH_TABLE.
        """
        query = """
            SELECT 
                SubredditName,
                MIN(SentimentScore) as MinScore,
                MAX(SentimentScore) as MaxScore,
                AVG(SentimentScore) as AvgScore,
                COUNT(*) as Mentions
            FROM GRAPH_TABLE(GraphAds
                MATCH (p:Posts)-[post_edge:POSTED_TO]->(s:Subreddits)
                WHERE p.CompanyName = @company_name AND p.ProductName = @product_name
                COLUMNS(s.Name as SubredditName, p.SentimentScore)
            )
            GROUP BY SubredditName
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={"company_name": company_name, "product_name": product_name},
                param_types={
                    "company_name": spanner.param_types.STRING,
                    "product_name": spanner.param_types.STRING,
                },
            )
            return [
                {
                    "subreddit": row[0],
                    "min": row[1],
                    "max": row[2],
                    "avg": round(row[3], 2),
                    "mentions": row[4],
                }
                for row in results
            ]

    def get_influencer_graph(self, company_name: str, sentiment_type: str):
        """
        Fetch influencer graph data for a given company and sentiment type.
        Returns data in a format compatible with force-graph (nodes and links).
        """
        sentiment_filter = (
            "p.SentimentScore <= 4"
            if sentiment_type == "Negative"
            else "p.SentimentScore >= 6"
        )

        query = f"""
            GRAPH GraphAds
            MATCH (p:Posts)-[post_edge:POSTED_TO]->(s:Subreddits)<-[member_edge:MEMBER_OF]-(u:Users)
            WHERE p.CompanyName = @company_name AND {sentiment_filter}
            RETURN p.PostId, p.ProductName, s.SubredditId, s.Name as SubredditName, u.UserId, u.Username
        """

        nodes = {}
        links = []

        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={"company_name": company_name},
                param_types={"company_name": spanner.param_types.STRING},
            )

            for row in results:
                post_id, product_name, sub_id, sub_name, user_id, username = row

                # Add Post node
                if post_id not in nodes:
                    nodes[post_id] = {
                        "id": post_id,
                        "name": f"Post: {product_name}",
                        "group": "post",
                        "color": "#ff7f0e",
                    }

                # Add Subreddit node
                if sub_id not in nodes:
                    nodes[sub_id] = {
                        "id": sub_id,
                        "name": sub_name,
                        "group": "subreddit",
                        "color": "#1f77b4",
                    }

                # Add User node
                if user_id not in nodes:
                    nodes[user_id] = {
                        "id": user_id,
                        "name": username,
                        "group": "user",
                        "color": "#2ca02c",
                    }

                # Add links
                links.append({"source": post_id, "target": sub_id, "type": "POSTED_TO"})
                links.append({"source": user_id, "target": sub_id, "type": "MEMBER_OF"})

        # Deduplicate links
        unique_links = []
        seen_links = set()
        for link in links:
            link_key = (link["source"], link["target"], link["type"])
            if link_key not in seen_links:
                unique_links.append(link)
                seen_links.add(link_key)

        return {"nodes": list(nodes.values()), "links": unique_links}

    def check_health(self):
        """Run a simple SELECT 1 query to verify connectivity."""
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql("SELECT 1")
            list(results)
            return True

    def save_post(self, data: dict):
        """
        Save the post data to the Posts table and create the edges.
        Data keys: user_id, subreddit_id, post_text, company_name, product_name, sentiment_score
        """
        post_id = str(uuid.uuid4())

        def run_transaction(transaction):
            # Insert Post
            transaction.insert(
                table="Posts",
                columns=[
                    "PostId",
                    "PostText",
                    "CompanyName",
                    "ProductName",
                    "SentimentScore",
                    "CreatedAt",
                ],
                values=[
                    (
                        post_id,
                        data["post_text"],
                        data["company_name"],
                        data["product_name"],
                        int(data["sentiment_score"]),
                        spanner.COMMIT_TIMESTAMP,
                    )
                ],
            )

            # Create Edge: Posts -> Subreddit
            transaction.insert(
                table="Posts2Subreddit",
                columns=["PostId", "SubredditId"],
                values=[(post_id, data["subreddit_id"])],
            )

            # Create Edge: User -> Subreddit
            transaction.insert_or_update(
                table="Users2Subreddit",
                columns=["SubredditId", "UserId"],
                values=[(data["subreddit_id"], data["user_id"])],
            )

        self.database.run_in_transaction(run_transaction)
        print("Post and Graph Edges saved successfully to Spanner.")
