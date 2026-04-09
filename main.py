from nicegui import ui, app
from ai_service import AIService
from db_service import SpannerService
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Configuration from environment variables
PROJECT_ID = os.getenv("GOOGLE_PROJECT")
SPANNER_INSTANCE = os.getenv("GOOGLE_SPANNER_INSTANCE")
SPANNER_DATABASE = os.getenv("GOOGLE_SPANNER_DATABASE")

if not all([PROJECT_ID, SPANNER_INSTANCE, SPANNER_DATABASE]):
    print("Error: Missing required environment variables GOOGLE_PROJECT, GOOGLE_SPANNER_INSTANCE, or GOOGLE_SPANNER_DATABASE.")
    os._exit(1)

# Initialize Services
ai_service = AIService(PROJECT_ID)
db_service = SpannerService(PROJECT_ID, SPANNER_INSTANCE, SPANNER_DATABASE)

# Health Check Endpoint (FastAPI)
@app.get('/v1/health')
async def health_check():
    try:
        db_service.check_health()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500

# Endpoint to fetch graph data for the frontend
@app.get('/api/influencer_graph/{company}/{sentiment}')
async def influencer_graph_api(company: str, sentiment: str):
    try:
        data = db_service.get_influencer_graph(company, sentiment)
        return data
    except Exception as e:
        return {"error": str(e)}, 500

# Navigation Menu Component

def nav_menu():
    with ui.header().classes("bg-blue-600 text-white p-4 items-center"):
        ui.label("GraphAds").classes("text-2xl font-bold mr-8")
        with ui.row().classes("gap-4"):
            ui.button("Submit Post", on_click=lambda: ui.navigate.to("/")).props(
                "flat text-white"
            )
            ui.button(
                "Product Analysis", on_click=lambda: ui.navigate.to("/product_analysis")
            ).props("flat text-white")
            ui.button(
                "Company Analysis", on_click=lambda: ui.navigate.to("/company_analysis")
            ).props("flat text-white")
            ui.button(
                "Influencer Sentiment", on_click=lambda: ui.navigate.to("/influencer_sentiment")
            ).props("flat text-white")
            ui.button(
                "Sentiment Drill Down", on_click=lambda: ui.navigate.to("/sentiment_drill_down")
            ).props("flat text-white")


@ui.page("/")
def home():
    nav_menu()

    # Fetch seed data for dropdowns
    try:
        users = db_service.get_users()
        subreddits = db_service.get_subreddits()
    except Exception as e:
        ui.notify(f"Database error: {e}", type="negative")
        users = {}
        subreddits = {}

    ui.label("Submit Reddit Post for Extraction").classes("text-3xl mt-8 mb-4 px-4")

    with ui.card().classes("w-full max-w-xl p-4 mx-4"):
        username_select = ui.select(
            options=list(users.keys()), label="Username"
        ).classes("w-full mb-2")
        subreddit_select = ui.select(
            options=list(subreddits.keys()), label="Subreddit"
        ).classes("w-full mb-2")
        post_text = (
            ui.textarea(
                "Post Text", placeholder="Paste the Reddit post content here..."
            )
            .classes("w-full mb-4")
            .props("rows=10")
        )

        async def process():
            if (
                not username_select.value
                or not subreddit_select.value
                or not post_text.value
            ):
                ui.notify("Please fill in all fields", type="warning")
                return

            with ui.dialog() as dialog, ui.card():
                ui.label("Processing with AI...").classes("text-lg")
                ui.spinner(size="lg")
            dialog.open()

            try:
                # Call AI Service
                extracted = ai_service.extract_info(post_text.value)

                # Store in session (using app.storage.user)
                app.storage.user["username"] = username_select.value
                app.storage.user["user_id"] = users[username_select.value]
                app.storage.user["subreddit"] = subreddit_select.value
                app.storage.user["subreddit_id"] = subreddits[subreddit_select.value]
                app.storage.user["post_text"] = post_text.value
                app.storage.user["company_name"] = extracted["company_name"]
                app.storage.user["product_name"] = extracted["product_name"]
                app.storage.user["sentiment_score"] = extracted["sentiment_score"]

                dialog.close()
                ui.navigate.to("/review")
            except Exception as e:
                dialog.close()
                ui.notify(f"Error: {str(e)}", type="negative")

        ui.button("Process with AI", on_click=process).classes(
            "w-full bg-blue-500 text-white"
        )


@ui.page("/review")
def review():
    nav_menu()

    # Check if we have data
    if "username" not in app.storage.user:
        ui.navigate.to("/")
        return

    ui.label("Review & Confirm Extraction").classes("text-3xl mt-8 mb-4 px-4")

    with ui.card().classes("w-full max-w-xl p-4 mx-4"):
        ui.label(f"User: {app.storage.user['username']}").classes("text-gray-600 mb-1")
        ui.label(f"Subreddit: {app.storage.user['subreddit']}").classes(
            "text-gray-600 mb-4"
        )

        company = ui.input(
            "Company Name", value=app.storage.user["company_name"]
        ).classes("w-full mb-2")
        product = ui.input(
            "Product Name", value=app.storage.user["product_name"]
        ).classes("w-full mb-2")
        sentiment = ui.number(
            "Sentiment Score (1-10)",
            value=app.storage.user["sentiment_score"],
            min=1,
            max=10,
        ).classes("w-full mb-4")

        async def submit():
            with ui.dialog() as dialog, ui.card():
                ui.label("Saving to Spanner...").classes("text-lg")
                ui.spinner(size="lg")
            dialog.open()

            try:
                data = {
                    "user_id": app.storage.user["user_id"],
                    "subreddit_id": app.storage.user["subreddit_id"],
                    "post_text": app.storage.user["post_text"],
                    "company_name": company.value,
                    "product_name": product.value,
                    "sentiment_score": sentiment.value,
                }

                db_service.save_post(data)

                dialog.close()
                ui.notify("Successfully saved to Spanner!", type="positive")
                ui.navigate.to("/")
            except Exception as e:
                dialog.close()
                ui.notify(f"Error saving to database: {str(e)}", type="negative")

        with ui.row().classes("w-full justify-between gap-4 mt-4"):
            ui.button("Back", on_click=lambda: ui.navigate.to("/")).props(
                "outline"
            ).classes("w-1/3")
            ui.button("Submit to Database", on_click=submit).classes(
                "w-1/2 bg-green-500 text-white"
            )


@ui.page("/company_analysis")
def company_analysis():
    nav_menu()

    ui.label("Company Analysis").classes("text-3xl mt-8 mb-4 px-4")

    # Fetch unique companies for selection
    try:
        companies = db_service.get_unique_companies()
    except Exception as e:
        ui.notify(f"Error fetching companies: {e}", type="negative")
        companies = []

    with ui.card().classes("w-full max-w-2xl p-4 mx-4"):
        if not companies:
            ui.label(
                "No data available in Posts table. Please submit some posts first."
            ).classes("text-red-500 italic")
            return

        selected_company = ui.select(
            options=companies,
            label="Select Company",
            on_change=lambda e: update_table(e.value),
        ).classes("w-full mb-4")

        table_container = ui.column().classes("w-full")

        def update_table(company_name):
            table_container.clear()
            with table_container:
                try:
                    analysis_data = db_service.get_company_analysis(company_name)
                    if not analysis_data:
                        ui.label("No analysis data found for this company.").classes(
                            "italic text-gray-500"
                        )
                        return

                    columns = [
                        {
                            "name": "subreddit",
                            "label": "Subreddit",
                            "field": "subreddit",
                            "align": "left",
                        },
                        {
                            "name": "min",
                            "label": "Min Sentiment",
                            "field": "min",
                            "align": "center",
                        },
                        {
                            "name": "max",
                            "label": "Max Sentiment",
                            "field": "max",
                            "align": "center",
                        },
                        {
                            "name": "avg",
                            "label": "Avg Sentiment",
                            "field": "avg",
                            "align": "center",
                        },
                        {
                            "name": "mentions",
                            "label": "Mentions",
                            "field": "mentions",
                            "align": "center",
                        },
                    ]
                    table = ui.table(
                        columns=columns, rows=analysis_data, row_key="subreddit"
                    ).classes("w-full shadow-lg border rounded-lg")
                    
                    # Add conditional formatting for sentiment columns
                    table.add_slot('body-cell-min', '''
                        <q-td :props="props" :style="{ color: props.value <= 4 ? 'red' : (props.value <= 6 ? '#EAB308' : 'green'), fontWeight: 'bold' }">
                            {{ props.value }}
                        </q-td>
                    ''')
                    table.add_slot('body-cell-max', '''
                        <q-td :props="props" :style="{ color: props.value <= 4 ? 'red' : (props.value <= 6 ? '#EAB308' : 'green'), fontWeight: 'bold' }">
                            {{ props.value }}
                        </q-td>
                    ''')
                    table.add_slot('body-cell-avg', '''
                        <q-td :props="props" :style="{ color: props.value <= 4 ? 'red' : (props.value <= 6 ? '#EAB308' : 'green'), fontWeight: 'bold' }">
                            {{ props.value }}
                        </q-td>
                    ''')
                except Exception as e:
                    ui.notify(f"Error during analysis: {e}", type="negative")


@ui.page("/product_analysis")
def product_analysis():
    nav_menu()

    ui.label("Product Analysis").classes("text-3xl mt-8 mb-4 px-4")

    # Fetch initial companies
    try:
        companies = db_service.get_unique_companies()
    except Exception as e:
        ui.notify(f"Error fetching companies: {e}", type="negative")
        companies = []

    with ui.card().classes("w-full max-w-2xl p-4 mx-4"):
        if not companies:
            ui.label("No data available. Please submit some posts first.").classes(
                "text-red-500 italic"
            )
            return

        # Company Dropdown
        company_select = ui.select(
            options=companies,
            label="Select Company",
            on_change=lambda e: on_company_change(e),
        ).classes("w-full mb-4")

        # Product Dropdown (initially empty)
        product_select = ui.select(
            options=[], label="Select Product", on_change=lambda e: on_product_change(e)
        ).classes("w-full mb-4")

        table_container = ui.column().classes("w-full")

        async def on_company_change(e):
            company_name = e.value
            try:
                products = db_service.get_unique_products(company_name)
                product_select.options = products
                product_select.value = None
                product_select.update()
                table_container.clear()
            except Exception as ex:
                ui.notify(f"Error fetching products: {ex}", type="negative")

        async def on_product_change(e):
            product_name = e.value
            if not product_name or not company_select.value:
                return

            table_container.clear()
            with table_container:
                try:
                    analysis_data = db_service.get_product_analysis(
                        company_select.value, product_name
                    )
                    if not analysis_data:
                        ui.label("No analysis data found for this product.").classes(
                            "italic text-gray-500"
                        )
                        return

                    columns = [
                        {
                            "name": "subreddit",
                            "label": "Subreddit",
                            "field": "subreddit",
                            "align": "left",
                        },
                        {
                            "name": "min",
                            "label": "Min Sentiment",
                            "field": "min",
                            "align": "center",
                        },
                        {
                            "name": "max",
                            "label": "Max Sentiment",
                            "field": "max",
                            "align": "center",
                        },
                        {
                            "name": "avg",
                            "label": "Avg Sentiment",
                            "field": "avg",
                            "align": "center",
                        },
                        {
                            "name": "mentions",
                            "label": "Mentions",
                            "field": "mentions",
                            "align": "center",
                        },
                    ]
                    table = ui.table(
                        columns=columns, rows=analysis_data, row_key="subreddit"
                    ).classes("w-full shadow-lg border rounded-lg")
                    
                    # Add conditional formatting for sentiment columns
                    table.add_slot('body-cell-min', '''
                        <q-td :props="props" :style="{ color: props.value <= 4 ? 'red' : (props.value <= 6 ? '#EAB308' : 'green'), fontWeight: 'bold' }">
                            {{ props.value }}
                        </q-td>
                    ''')
                    table.add_slot('body-cell-max', '''
                        <q-td :props="props" :style="{ color: props.value <= 4 ? 'red' : (props.value <= 6 ? '#EAB308' : 'green'), fontWeight: 'bold' }">
                            {{ props.value }}
                        </q-td>
                    ''')
                    table.add_slot('body-cell-avg', '''
                        <q-td :props="props" :style="{ color: props.value <= 4 ? 'red' : (props.value <= 6 ? '#EAB308' : 'green'), fontWeight: 'bold' }">
                            {{ props.value }}
                        </q-td>
                    ''')
                except Exception as ex:
                    ui.notify(f"Error during analysis: {ex}", type="negative")


@ui.page("/influencer_sentiment")
def influencer_sentiment():
    nav_menu()

    # Include force-graph library
    ui.add_head_html('<script src="https://unpkg.com/force-graph"></script>')

    ui.label("Influencer Sentiment").classes("text-3xl mt-8 mb-4 px-4")

    # Fetch unique companies for selection
    try:
        companies = db_service.get_unique_companies()
    except Exception as e:
        ui.notify(f"Error fetching companies: {e}", type="negative")
        companies = []

    with ui.row().classes("w-full px-4 gap-4"):
        with ui.card().classes("w-1/4 p-4"):
            company_select = ui.select(
                options=companies,
                label="Select Company",
                on_change=lambda e: update_graph(),
            ).classes("w-full mb-4")
            
            sentiment_toggle = ui.radio(
                ["Positive", "Negative"],
                value="Positive",
                on_change=lambda e: update_graph(),
            ).props("inline")
            
            ui.label("Legend:").classes("font-bold mt-4")
            ui.label("Posts").classes("text-[#ff7f0e]")
            ui.label("Subreddits").classes("text-[#1f77b4]")
            ui.label("Users").classes("text-[#2ca02c]")

        with ui.card().classes("w-3/4 p-4 items-center justify-center h-[750px]"):
            graph_container = ui.html('<div id="graph" style="width: 700px; height: 700px; border: 1px solid #ddd;"></div>')

    def update_graph():
        if not company_select.value:
            return
        
        # We'll use JS to fetch and render the graph
        js_code = f"""
        fetch('/api/influencer_graph/{company_select.value}/{sentiment_toggle.value}')
            .then(res => res.json())
            .then(data => {{
                if (data.error) {{
                    console.error(data.error);
                    return;
                }}
                
                const elem = document.getElementById('graph');
                elem.innerHTML = ''; // Clear previous graph
                
                const Graph = ForceGraph()(elem)
                    .graphData(data)
                    .height(700)
                    .width(700)
                    .cooldownTicks(100)
                    .nodeId('id')
                    .nodeAutoColorBy('group')
                    .nodeCanvasObject((node, ctx, globalScale) => {{
                        const label = node.name;
                        const fontSize = 14/globalScale;
                        ctx.font = `${{fontSize}}px Sans-Serif-Bold`;
                        const textWidth = ctx.measureText(label).width;
                        const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); // some padding

                        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                        ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillStyle = node.color;
                        ctx.fillText(label, node.x, node.y);

                        node.__bckgDimensions = bckgDimensions; // to re-use in nodePointerAreaPaint
                    }})
                    .nodePointerAreaPaint((node, color, ctx) => {{
                        ctx.fillStyle = color;
                        const bckgDimensions = node.__bckgDimensions;
                        bckgDimensions && ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
                    }});
                
                Graph.d3Force('charge').strength(-200);
                Graph.d3Force('center', null);
                Graph.onEngineStop(() => Graph.zoomToFit(.8));
            }});
        """
        ui.run_javascript(js_code)


@ui.page("/sentiment_drill_down")
def sentiment_drill_down():
    nav_menu()

    ui.label("Sentiment Drill Down").classes("text-3xl mt-8 mb-4 px-4")

    # Fetch initial companies
    try:
        companies = db_service.get_unique_companies()
    except Exception as e:
        ui.notify(f"Error fetching companies: {e}", type="negative")
        companies = []

    with ui.card().classes("w-full max-w-4xl p-4 mx-4"):
        if not companies:
            ui.label("No data available. Please submit some posts first.").classes(
                "text-red-500 italic"
            )
            return

        with ui.row().classes("w-full gap-4"):
            # Company Dropdown
            company_select = ui.select(
                options=companies,
                label="Select Company",
                on_change=lambda e: on_company_change(e),
            ).classes("flex-1")

            # Product Dropdown (initially empty)
            product_select = ui.select(
                options=[],
                label="Select Product",
                on_change=lambda e: on_product_change(e),
            ).classes("flex-1")

            # Subreddit Dropdown (initially empty)
            subreddit_select = ui.select(
                options=[],
                label="Select Subreddit",
                on_change=lambda e: on_subreddit_change(e),
            ).classes("flex-1")

        table_container = ui.column().classes("w-full mt-4")

        async def on_company_change(e):
            company_name = e.value
            try:
                products = db_service.get_unique_products(company_name)
                product_select.options = products
                product_select.value = None
                product_select.update()
                
                subreddit_select.options = []
                subreddit_select.value = None
                subreddit_select.update()
                
                table_container.clear()
            except Exception as ex:
                ui.notify(f"Error fetching products: {ex}", type="negative")

        async def on_product_change(e):
            product_name = e.value
            if not product_name or not company_select.value:
                return
            
            try:
                subreddits = db_service.get_unique_subreddits_for_drill_down(
                    company_select.value, product_name
                )
                subreddit_select.options = subreddits
                subreddit_select.value = None
                subreddit_select.update()
                
                table_container.clear()
            except Exception as ex:
                ui.notify(f"Error fetching subreddits: {ex}", type="negative")

        async def on_subreddit_change(e):
            subreddit_name = e.value
            if not subreddit_name or not product_select.value or not company_select.value:
                return

            table_container.clear()
            with table_container:
                try:
                    drill_data = db_service.get_sentiment_drill_down(
                        company_select.value, product_select.value, subreddit_name
                    )
                    if not drill_data:
                        ui.label("No posts found for this selection.").classes(
                            "italic text-gray-500"
                        )
                        return

                    columns = [
                        {
                            "name": "username",
                            "label": "Username",
                            "field": "username",
                            "align": "left",
                        },
                        {
                            "name": "text",
                            "label": "Post Text",
                            "field": "text",
                            "align": "left",
                            "classes": "whitespace-normal",
                        },
                        {
                            "name": "score",
                            "label": "Sentiment Score",
                            "field": "score",
                            "align": "center",
                        },
                    ]
                    
                    table = ui.table(
                        columns=columns, rows=drill_data, row_key="text"
                    ).classes("w-full shadow-lg border rounded-lg")
                    
                    # Add conditional formatting for sentiment score
                    table.add_slot('body-cell-score', '''
                        <q-td :props="props" :style="{ color: props.value <= 4 ? 'red' : (props.value <= 6 ? '#EAB308' : 'green'), fontWeight: 'bold' }">
                            {{ props.value }}
                        </q-td>
                    ''')
                except Exception as ex:
                    ui.notify(f"Error fetching drill down data: {ex}", type="negative")

# Run the app
ui.run(title="GraphAds", storage_secret="6087b286-35a1-426c-9477-83d5a499318a")
