import json
import os
from google.cloud import spanner

from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_PROJECT")
SPANNER_INSTANCE = os.getenv("GOOGLE_SPANNER_INSTANCE")
SPANNER_DATABASE = os.getenv("GOOGLE_SPANNER_DATABASE")

if not all([PROJECT_ID, SPANNER_INSTANCE, SPANNER_DATABASE]):
    print("Error: Missing required environment variables GOOGLE_PROJECT, GOOGLE_SPANNER_INSTANCE, or GOOGLE_SPANNER_DATABASE.")
    os._exit(1)

def setup_database():
    client = spanner.Client(project=PROJECT_ID, disable_builtin_metrics=True)
    instance = client.instance(SPANNER_INSTANCE)
    database = instance.database(SPANNER_DATABASE)

    confirm = input("This will DROP and recreate all tables. Are you sure? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborting.")
        return

    # Drop tables if they exist
    print("Dropping tables...")
    try:
        database.update_ddl([
            "DROP TABLE Posts",
            "DROP TABLE Users",
            "DROP TABLE Subreddits"
        ]).result()
    except Exception as e:
        print(f"Note: Some tables might not have existed to drop: {e}")

    # Create tables
    print("Creating tables...")
    operation = database.update_ddl([
        """
        CREATE TABLE Users (
            Id STRING(36) NOT NULL,
            Username STRING(MAX) NOT NULL
        ) PRIMARY KEY (Id)
        """,
        """
        CREATE TABLE Subreddits (
            Id STRING(36) NOT NULL,
            Name STRING(MAX) NOT NULL
        ) PRIMARY KEY (Id)
        """,
        """
        CREATE TABLE Posts (
            Id STRING(36) NOT NULL,
            UserId STRING(36) NOT NULL,
            SubredditId STRING(36) NOT NULL,
            PostText STRING(MAX) NOT NULL,
            CompanyName STRING(MAX),
            ProductName STRING(MAX),
            SentimentScore INT64,
            CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
            CONSTRAINT FK_User FOREIGN KEY (UserId) REFERENCES Users (Id),
            CONSTRAINT FK_Subreddit FOREIGN KEY (SubredditId) REFERENCES Subreddits (Id)
        ) PRIMARY KEY (Id)
        """
    ])
    operation.result()
    print("Tables created successfully.")

    # Seed data
    print("Seeding data...")
    seed_from_json(database, 'Users', 'data/users.json')
    seed_from_json(database, 'Subreddits', 'data/subreddits.json')
    seed_from_json(database, 'Posts', 'data/posts.json')
    print("Database setup and seeding complete.")

def seed_from_json(database, table_name, json_file):
    if not os.path.exists(json_file):
        print(f"Seed file {json_file} not found.")
        return

    with open(json_file, 'r') as f:
        data = json.load(f)

    if not data:
        return

    with database.batch() as batch:
        columns = list(data[0].keys())
        values = [tuple(item.values()) for item in data]
        batch.insert(table=table_name, columns=columns, values=values)
    print(f"Seeded {len(data)} rows into {table_name}.")

if __name__ == "__main__":
    setup_database()
