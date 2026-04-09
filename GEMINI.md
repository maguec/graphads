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

The database should be constructed as a Spanner Graph database.

Database should have the following node tables:

1. Users including a uuidv4, username, create 4 users with random names if the file has more users, do not modify
2. Subreddits including a uuidv4, name, create 4 subreddits named r/cooking, r/chef, r/kitchen and r/homecooks if the file has more than 4 entries do not modify
3. Posts table which includes the ids for the the post text, company name, product name and sentiment analysis number if the file has any entries do not modify

Database should have the following edge tables:

1. Users2Subreddit with the id of the user linked to the id of the subreddit with foreign keys and a composite key of userid and subredditid with the label MEMBER_OF and interleaved in the Usbreddit table
2. Posts2Subreddit with the id of the post linked to the id of the subreddit with foreign keys and a composite key of postid and subredditid with the lable of POSTED_TO and interleaved in the Posts table


The Spanner Graph schema should include:

1. Those node tables
2. Those edge tables with the proper URLs
3. a Graph called GraphAds

For each of these tables create a json data file containing this information in a data directory, then have the setup_spanner.py script read from these files and populate the database.  Also have the setup_spanner.py file drop and recreate all tables, but prompt the user to do so.  The setup_spanner script should use the posts.json file to populate the Users2Subreddit and Posts2Subreddit edge tables handling the case where the composite key alreday exissts.


The company analysis tab should have a drop down scanning the CompanyName of the Posts table for unique company names. When the company is selected it should produce a table showing the minimum, maximum, and average sentiment score for each subreddit by querying the Posts table, include the total number of mentions in the right most column

In the product analysis tab have drop downs for Company name for unique company names and products that should be updated by scanning posts for uniq products that are filtered by the company name after update.  The report should produce a table showing min, max and average sentiment score for each subreddit, include the total number of mentions in the right most column

add a /v1/health endpoint that connects to the spanner database and runs a select 1 to ensure connectivity is working

create a sentiment drill down table have a dropdown for the company name by scanning posts for uniq companies and they product name by scanning posts for uniq products and the subreddit it by scanning posts for uniq subreddits - given a subreddit and a company create a table that shows the username of the post, the text of the post and they sentiment score of that post - this requires no database updates - I don't want the user id in the post use a graph query to determine the post ID

Create another tab called "Influencer Sentiment" this should be a form that takes the company name wht a drop down scanning the Posts table for uniq company names and has a toggle for "Negative" and "Positive"

Then it should run the following query:

GRAPH GraphAds
MATCH k=(p:Posts)-[post_edge]->(s:Subreddits)<-[user_edge]-(u:Users)
WHERE p.CompanyName = @comany_name AND p.SentimentScore <= 4 if Negative and >= 6 if "positive"
RETURN s.SubredditId as Subreddit, u.Username as Username
RETURN SAFE_TO_JSON(k) AS JSON

This JSON return should be returned and mapped using d3.js similar to the following:

```python
def data_from_graph(card_id):
    node_set = []
    link_set = []
    query = """
    GRAPH TransitGraph
        MATCH (o:Oyster{{id: {}}})-[o1:HAS_OYSTER]->(p:Person)<-[:HAS_INHABITANT]-(a:Address)-[:HAS_INHABITANT]->(q:Person)-[o2:HAS_OYSTER]-(r:Oyster)
        WHERE q.id != p.id
        RETURN p.id as pid, p.firstname as src_firstanme, p.lastname as src_lastname,
        o.id as src_card_id,
        a.id as address_id, a.address,
        q.firstname as tgt_firstanme, q.lastname as tgt_lastname, q.id as p2id,  r.id as linked_card_id, r.is_suspect as sus
    """.format(
        card_id
    )
    with client.snapshot() as snapshot:
        results = snapshot.execute_sql(query)
        for row in results:
            node_set.append(
                Person(
                    "Person{}".format(row[0]), "{} {}".format(row[1], row[2]), "person"
                )
            )
            node_set.append(
                Person(
                    "Person{}".format(row[8]), "{} {}".format(row[6], row[7]), "person"
                )
            )
            node_set.append(Address("Address{}".format(row[4]), row[5], "address"))
            node_set.append(
                Card("Oyster{}".format(row[3]), "Oyster{}".format(row[3]), "card")
            )
            if row[10] > 0:
                node_set.append(
                    Card(
                        "Oyster{}".format(row[9]),
                        "SUSPECT-Oyster{}".format(row[9]),
                        "card{}".format(row[10]),
                    )
                )
            else:
                node_set.append(
                    Card(
                        "Oyster{}".format(row[9]),
                        "Oyster{}".format(row[9]),
                        "card{}".format(row[10]),
                    )
                )

            link_set.append(
                Edge("Person{}".format(row[8]), "Oyster{}".format(row[9]), "owns")
            )
            link_set.append(
                Edge("Person{}".format(row[0]), "Oyster{}".format(row[3]), "owns")
            )
            link_set.append(
                Edge("Person{}".format(row[0]), "Address{}".format(row[4]), "resides")
            )
            link_set.append(
                Edge("Person{}".format(row[8]), "Address{}".format(row[4]), "resides")
            )
    return json.dumps(
        {
            "nodes": [n._asdict() for n in set(node_set)],
            "links": [l._asdict() for l in set(link_set)],
        }
    )
```

with d3js setup linked

```html
   <script>
     fetch('/data/{{card_id}}').then(res => res.json()).then(data => {
       const Graph = ForceGraph()
        (document.getElementById('graph'))
          .graphData(data)
          .height(700)
          .width(700)
          .cooldownTicks(100)
          .nodeId('id')
          .nodeAutoColorBy('group')
          .nodeCanvasObject((node, ctx, globalScale) => {
            const label = node.name;
            const fontSize = 14/globalScale;
            ctx.font = `${fontSize}px Sans-Serif-Bold`;
            const textWidth = ctx.measureText(label).width;
            const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); // some padding

            ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = node.color;
            ctx.fillText(label, node.x, node.y);

            node.__bckgDimensions = bckgDimensions; // to re-use in nodePointerAreaPaint
          })
          .nodePointerAreaPaint((node, color, ctx) => {
            ctx.fillStyle = color;
            const bckgDimensions = node.__bckgDimensions;
            bckgDimensions && ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
          });
       Graph.d3Force('charge').strength(-200);
       Graph.d3Force('center', null);
       Graph.onEngineStop(() => Graph.zoomToFit(.8));
      });
   </script>
```

