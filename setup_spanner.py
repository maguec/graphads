import json
import os
from google.cloud import spanner
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_PROJECT")
SPANNER_INSTANCE = os.getenv("GOOGLE_SPANNER_INSTANCE")
SPANNER_DATABASE = os.getenv("GOOGLE_SPANNER_DATABASE")

if not all([PROJECT_ID, SPANNER_INSTANCE, SPANNER_DATABASE]):
    print("Error: Missing required environment variables.")
    os._exit(1)


def setup_database():
    client = spanner.Client(project=PROJECT_ID, disable_builtin_metrics=True)
    instance = client.instance(SPANNER_INSTANCE)
    database = instance.database(SPANNER_DATABASE)

    confirm = input(
        "This will DROP and recreate all tables and the GRAPH. Are you sure? (y/n): "
    )
    if confirm.lower() != "y":
        print("Aborting.")
        return

    print("Dropping graph and tables...")
    try:
        database.update_ddl(["DROP PROPERTY GRAPH GraphAds"]).result()
        print("Dropped graph GraphAds.")
    except Exception as e:
        print(f"Note: GraphAds might not have existed.")

    tables_to_drop = [
        "CommunityResults",
        "Posts2Subreddit",
        "Users2Subreddit",
        "Posts",
        "Users",
        "Subreddits",
    ]
    for table in tables_to_drop:
        try:
            database.update_ddl([f"DROP TABLE {table}"]).result()
            print(f"Dropped table {table}.")
        except Exception as e:
            print(f"Note: Table {table} might not have existed.")

    print("Creating Node tables...")
    operation = database.update_ddl(
        [
            """
        CREATE TABLE Users (
            UserId STRING(36) NOT NULL,
            Username STRING(MAX) NOT NULL
        ) PRIMARY KEY (UserId)
        """,
            # Added a generated UserId column to spoof the graph algorithm pipeline
            """
        CREATE TABLE Subreddits (
            SubredditId STRING(36) NOT NULL,
            Name STRING(MAX) NOT NULL,
            UserId STRING(36) AS (SubredditId) STORED
        ) PRIMARY KEY (SubredditId)
        """,
            """
        CREATE TABLE Posts (
            PostId STRING(36) NOT NULL,
            PostText STRING(MAX) NOT NULL,
            CompanyName STRING(MAX),
            ProductName STRING(MAX),
            SentimentScore INT64,
            CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
        ) PRIMARY KEY (PostId)
        """,
        ]
    )
    operation.result()

    print("Creating Edge tables & Results table (Interleaved)...")
    operation = database.update_ddl(
        [
            """
        CREATE TABLE Users2Subreddit (
            UserId STRING(36) NOT NULL,
            SubredditId STRING(36) NOT NULL,
            CONSTRAINT FK_UserEdge FOREIGN KEY (UserId) REFERENCES Users (UserId),
            CONSTRAINT FK_SubredditEdge FOREIGN KEY (SubredditId) REFERENCES Subreddits (SubredditId)
        ) PRIMARY KEY (UserId, SubredditId), INTERLEAVE IN PARENT Users ON DELETE CASCADE
        """,
            """
        CREATE TABLE Posts2Subreddit (
            PostId STRING(36) NOT NULL,
            SubredditId STRING(36) NOT NULL,
            CONSTRAINT FK_PostEdge FOREIGN KEY (PostId) REFERENCES Posts (PostId),
            CONSTRAINT FK_SubredditPostEdge FOREIGN KEY (SubredditId) REFERENCES Subreddits (SubredditId)
        ) PRIMARY KEY (PostId, SubredditId), INTERLEAVE IN PARENT Posts ON DELETE CASCADE
        """,
            # Permanent Results table with auto-formatting column
            """
        CREATE TABLE CommunityResults (
            UserId STRING(36) NOT NULL,
            RawClusterId INT64,
            CommunityId STRING(MAX) AS (
                CASE WHEN RawClusterId IS NOT NULL 
                THEN CONCAT('Community_', CAST(RawClusterId AS STRING)) 
                ELSE NULL END
            ) STORED
        ) PRIMARY KEY (UserId), INTERLEAVE IN PARENT Users ON DELETE CASCADE
        """
        ]
    )
    operation.result()

    print("Creating Property Graph...")
    operation = database.update_ddl(
        [
            """
        CREATE PROPERTY GRAPH GraphAds
        NODE TABLES (
            Users,
            Subreddits,
            Posts,
            CommunityResults
        )
        EDGE TABLES (
            Users2Subreddit
                SOURCE KEY (UserId) REFERENCES Users (UserId)
                DESTINATION KEY (SubredditId) REFERENCES Subreddits (SubredditId)
                LABEL MEMBER_OF,
            Posts2Subreddit
                SOURCE KEY (PostId) REFERENCES Posts (PostId)
                DESTINATION KEY (SubredditId) REFERENCES Subreddits (SubredditId)
                LABEL POSTED_TO,
            
            -- Exposing the Results table as a native Graph Edge
            CommunityResults AS USER_COMMUNITY
                SOURCE KEY (UserId) REFERENCES Users (UserId)
                DESTINATION KEY (UserId) REFERENCES CommunityResults (UserId)
                LABEL IN_COMMUNITY
        )
        """
        ]
    )
    operation.result()
    print("Graph and tables created successfully.")

    print("Seeding data...")
    seed_nodes(database)
    seed_edges(database)
    print("Database setup complete.")


def seed_nodes(database):
    with open("data/users.json", "r") as f:
        users = json.load(f)
    
    with database.batch() as batch:
        batch.insert(
            table="Users",
            columns=["UserId", "Username"],
            values=[(u["id"], u["username"]) for u in users],
        )
        # Prepopulate CommunityResults so update_ignore_all works perfectly
        batch.insert(
            table="CommunityResults",
            columns=["UserId"],
            values=[(u["id"],) for u in users],
        )
    print(f"Seeded {len(users)} users and prepopulated CommunityResults.")

    with open("data/subreddits.json", "r") as f:
        subreddits = json.load(f)
    with database.batch() as batch:
        batch.insert(
            table="Subreddits",
            columns=["SubredditId", "Name"],
            values=[(s["id"], s["name"]) for s in subreddits],
        )
    print(f"Seeded {len(subreddits)} subreddits.")

    with open("data/posts.json", "r") as f:
        posts = json.load(f)
    with database.batch() as batch:
        batch.insert(
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
                    p["Id"],
                    p["PostText"],
                    p.get("CompanyName"),
                    p.get("ProductName"),
                    p["SentimentScore"],
                    p["CreatedAt"],
                )
                for p in posts
            ],
        )
    print(f"Seeded {len(posts)} posts.")


def seed_edges(database):
    with open("data/posts.json", "r") as f:
        posts = json.load(f)

    user_sub_edges = set()
    post_sub_edges = set()

    for p in posts:
        user_sub_edges.add((p["UserId"], p["SubredditId"]))
        post_sub_edges.add((p["Id"], p["SubredditId"]))

    with database.batch() as batch:
        batch.insert(
            table="Users2Subreddit",
            columns=["UserId", "SubredditId"],
            values=list(user_sub_edges),
        )
    print(f"Seeded {len(user_sub_edges)} Users2Subreddit edges.")

    with database.batch() as batch:
        batch.insert(
            table="Posts2Subreddit",
            columns=["PostId", "SubredditId"],
            values=list(post_sub_edges),
        )
    print(f"Seeded {len(post_sub_edges)} Posts2Subreddit edges.")


if __name__ == "__main__":
    setup_database()