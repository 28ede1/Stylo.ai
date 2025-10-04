from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
from dotenv import load_dotenv
from serpapi import GoogleSearch
import traceback

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app with CORS for frontend communication
app = Flask(__name__)
CORS(app)

# Set API keys from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/chat', methods=['POST'])
def chat():
    # Extract user message from JSON request
    data = request.json
    user_message = data.get("message")

    # Validate input
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    try:
        # Initialize OpenAI client
        client = openai.OpenAI()

        # Generate initial response based on Stylo's system prompt
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are Stylo, a highly specialized personal shopper AI assistant with expertise in helping users find clothes based on their descriptions. "
                    "You should always respond in English and provide precise recommendations for outfits, supported by descriptions of matching clothes and potential links to products. \n\n"
                    "For example, if a user says 'I want a fall look, a red flannel or something', suggest fitting outfits, simulate connecting to a backend for streaming results (describe recommended items), and describe generating an image of the user wearing the clothing articles/outfits. \n\n"
                    "If a user asks something unclear, ask for clarification instead of guessing. \n\n"
                    "If no matching clothes are found, say so openly and recommend relevant resources like shopping sites.\n\n"
                    "Your responses should ALWAYS include a source, such as:\n"
                    "- A **reference to a product category** (e.g., 'Similar to items on ASOS').\n"
                    "- A **clickable link** to a shopping site (`[ASOS Flannel Shirts](https://www.asos.com/search/?q=red+flannel)`).\n"
                    "- A **known brand or style reference**.\n\n"
                    "### Format for your responses: \n"
                    "- Use **headings** with # and ## to divide your response.\n"
                    "- Use **bullet points** for lists (- or *).\n"
                    "- Use **bold text** (**bold**) for important points.\n"
                    "- Use *italics* (*italics*) for concepts or terms.\n"
                    "- Insert clickable links ([text](URL)) to sources.\n"
                    "- Add emojis if they fit the context (✅👗🛍️🔗) to improve readability.\n\n"
                )},
                {"role": "user", "content": user_message}
            ]
        )
        answer = response.choices[0].message.content

        # Refine the user message into a search query optimized for Google Shopping
        refine_messages = [
            {"role": "system", "content": "Refine this outfit request into optimized Google Shopping search terms, including style, season, and gender if implied."},
            {"role": "user", "content": user_message}
        ]
        refine_response = client.chat.completions.create(model="gpt-4o-mini", messages=refine_messages)
        search_query = refine_response.choices[0].message.content

        # Fetch products from Google Shopping using SerpAPI
        products = fetch_google_shopping_products(search_query)
        if products:
            product_cards = "\n".join([
                f"**{i+1}.** {p['name']} from {p['source']} - **${p['price']}**\n![Product]({p['image_url']})\n[Buy Now]({p['link']})\n"
                for i, p in enumerate(products)
            ])
            answer += f"\n\n## Top 5 Matches from Google Shopping: 👗🛍️\n{product_cards}\n*Pick a number (1-5) to try on!*"
        else:
            answer += "\n\nNo matches found—try clarifying your outfit description! 🔍"

        return jsonify({"response": answer, "products": products})

    except Exception as e:
        print(traceback.format_exc())  # Log full traceback for debugging
        return jsonify({"error": str(e)}), 500

def fetch_google_shopping_products(search_query, limit=5):
    """Fetch top 5 clothing products from Google Shopping via SerpAPI."""
    params = {
        "engine": "google_shopping",
        "q": search_query,
        "num": limit,
        "api_key": os.getenv("SERPAPI_KEY"),
        "gl": "us",  # Country (adjust based on user location if needed)
        "hl": "en"   # Language
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict().get("shopping_results", [])
        return [
            {
                "name": result.get("title", "N/A"),
                "price": result.get("extracted_price", "N/A"),
                "image_url": result.get("thumbnail", ""),
                "link": result.get("link", ""),
                "source": result.get("source", "")
            }
            for result in results[:limit] if result.get("thumbnail")
        ]
    except Exception as e:
        print(f"SerpAPI Error: {str(e)}")
        return []

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
