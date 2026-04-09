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
            results = snapshot.execute_sql("SELECT Id, Username FROM Users")
            return {row[1]: row[0] for row in results}  # Username: Id mapping

    def get_subreddits(self):
        """Fetch all subreddits from the Subreddits table."""
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql("SELECT Id, Name FROM Subreddits")
            return {row[1]: row[0] for row in results}  # Name: Id mapping

    def get_unique_companies(self):
        """Fetch unique company names from the Posts table."""
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql("SELECT DISTINCT CompanyName FROM Posts WHERE CompanyName IS NOT NULL")
            return [row[0] for row in results]

    def get_company_analysis(self, company_name: str):
        """
        Get min, max, and avg sentiment score per subreddit for a given company.
        Joins with Subreddits table to get the name.
        """
        query = """
            SELECT 
                s.Name,
                MIN(p.SentimentScore) as MinScore,
                MAX(p.SentimentScore) as MaxScore,
                AVG(p.SentimentScore) as AvgScore,
                COUNT(*) as Mentions
            FROM Posts p
            JOIN Subreddits s ON p.SubredditId = s.Id
            WHERE p.CompanyName = @company_name
            GROUP BY s.Name
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={'company_name': company_name},
                param_types={'company_name': spanner.param_types.STRING}
            )
            return [
                {'subreddit': row[0], 'min': row[1], 'max': row[2], 'avg': round(row[3], 2), 'mentions': row[4]}
                for row in results
            ]

    def get_unique_products(self, company_name: str):
        """Fetch unique product names for a specific company from the Posts table."""
        query = "SELECT DISTINCT ProductName FROM Posts WHERE CompanyName = @company_name AND ProductName IS NOT NULL"
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={'company_name': company_name},
                param_types={'company_name': spanner.param_types.STRING}
            )
            return [row[0] for row in results]

    def get_product_analysis(self, company_name: str, product_name: str):
        """
        Get min, max, and avg sentiment score per subreddit for a given company and product.
        Joins with Subreddits table to get the name.
        """
        query = """
            SELECT 
                s.Name,
                MIN(p.SentimentScore) as MinScore,
                MAX(p.SentimentScore) as MaxScore,
                AVG(p.SentimentScore) as AvgScore,
                COUNT(*) as Mentions
            FROM Posts p
            JOIN Subreddits s ON p.SubredditId = s.Id
            WHERE p.CompanyName = @company_name AND p.ProductName = @product_name
            GROUP BY s.Name
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query,
                params={
                    'company_name': company_name,
                    'product_name': product_name
                },
                param_types={
                    'company_name': spanner.param_types.STRING,
                    'product_name': spanner.param_types.STRING
                }
            )
            return [
                {'subreddit': row[0], 'min': row[1], 'max': row[2], 'avg': round(row[3], 2), 'mentions': row[4]}
                for row in results
            ]

    def check_health(self):
        """Run a simple SELECT 1 query to verify connectivity."""
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql("SELECT 1")
            # Consume the results to ensure the query actually executed
            list(results)
            return True

    def save_post(self, data: dict):
        """
        Save the post data to the Posts table.
        Data keys: user_id, subreddit_id, post_text, company_name, product_name, sentiment_score
        """
        with self.database.batch() as batch:
            batch.insert(
                table='Posts',
                columns=[
                    'Id', 'UserId', 'SubredditId', 'PostText', 
                    'CompanyName', 'ProductName', 'SentimentScore', 'CreatedAt'
                ],
                values=[(
                    str(uuid.uuid4()),
                    data['user_id'],
                    data['subreddit_id'],
                    data['post_text'],
                    data['company_name'],
                    data['product_name'],
                    int(data['sentiment_score']),
                    spanner.COMMIT_TIMESTAMP
                )]
            )
        print("Post saved successfully to Spanner.")

if __name__ == "__main__":
    # Test stub
    pass
