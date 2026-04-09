We are looking to build a WebUI in NiceGUI for python the environment for python should be managed by uv
This will be backed by Google Spanner database.

The frontpage should take the following information in a form

Username 
Subreddit
PostText

There should be menus at the top of the application for submit post, a tab for product analysis which we will create later, a tab for company analysis.

The username and subreddit should be drop downs from the User and Subreddit tables

once this information is correct this should call Vertex AI API and extract a company name and a product name as well as a score from 1-10 sentiment analysis 

This information should then be pre-filled in the form for the next page allowing the user to edit the company / product and score before being submitted to the database.

Database format should have the following tables:

1. Users including a uuidv4, username, create 4 users with random names if the file has more users, do not modify
2. Subreddits including a uuidv4, name, create 4 subreddits named r/cooking, r/chef, r/kitchen and r/homecooks if the file has more than 4 entries do not modify
3. Posts table which includes the ids for the user, subreddit, the post text, company name, product name and sentiment analysis number if the file has any entries do not modify

For each of these tables create a json data file containing this information in a data directory, then have the setup_spanner.py script read from these files and populate the database.  Also have the setup_spanner.py file drop and recreate all tables, but prompt the user to do so.


The company analysis tab should have a drop down scanning the CompanyName of the Posts table for unique company names. When the company is selected it should produce a table showing the minimum, maximum, and average sentiment score for each subreddit by querying the Posts table, include the total number of mentions in the right most column

In the product analysis tab have drop downs for Company name for unique company names and products that should be updated by scanning posts for uniq products that are filtered by the company name after update.  The report should produce a table showing min, max and average sentiment score for each subreddit, include the total number of mentions in the right most column

add a /v1/health endpoint that connects to the spanner database and runs a select 1 to ensure connectivity is working
