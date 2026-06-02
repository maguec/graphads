import vertexai
from vertexai.generative_models import GenerativeModel
import json


class AIService:
    def __init__(self, project_id: str, location: str = "us-central1"):
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-2.5-flash")

    def extract_info(self, post_text: str) -> dict:
        """
        Extract Company Name, Product Name, and Sentiment Score from a Reddit post.
        Returns a dict: {'company_name': str, 'product_name': str, 'sentiment_score': int}
        """
        prompt = f"""
        Extract the following information from the Reddit post text provided below:
        1. Company Name: The name of the company being discussed.
        2. Product Name: The name of the specific product mentioned.
        3. Sentiment Score: A score from 1 to 10 based on sentiment analysis (1 = very negative, 10 = very positive).

        Respond ONLY with a JSON object in the following format:
        {{
            "company_name": "...",
            "product_name": "...",
            "sentiment_score": 5
        }}

        Post Text:
        {post_text}
        """

        response = self.model.generate_content(
            prompt, generation_config={"response_mime_type": "application/json"}
        )
        text = response.text.strip()

        try:
            data = json.loads(text)
            return {
                "company_name": data.get("company_name", "Unknown"),
                "product_name": data.get("product_name", "Unknown"),
                "sentiment_score": data.get("sentiment_score", 5),
            }
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            return {
                "company_name": "Error",
                "product_name": "Error",
                "sentiment_score": 0,
            }

    def summarize_reviews(self, posts_data: list[dict]) -> str:
        """
        Summarize the main points from multiple post texts and their sentiment scores
        in descending order of occurrence.
        """
        formatted_posts = []
        for p in posts_data:
            formatted_posts.append(
                f"Sentiment Score: {p['score']}/10\nReview: {p['text']}"
            )

        combined_text = "\n---\n".join(formatted_posts)
        prompt = f"""
        Below are several Reddit posts and their sentiment scores discussing a product. 
        Please summarize the main points regarding the sentiment (both positive and negative) mentioned across these posts.
        List the points in descending order of how frequently they occur.
        Provide a concise, bulleted list.

        Post Texts:
        {combined_text}
        """

        response = self.model.generate_content(prompt)
        return response.text.strip()


if __name__ == "__main__":
    # Test stub
    # service = AIService("mague-tf")
    pass
