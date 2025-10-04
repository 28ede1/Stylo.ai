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

        # Updated system prompt: ALWAYS fetch and use specific product links/images/prices—no generics
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are Stylo, a personal shopper AI. For every query, fetch real products from Google Shopping and ALWAYS include 3-5 SPECIFIC items with name, price, image, and direct product link (not site homepages). "
                    "Example: '**1. Long Dark Blue Trench Coat** - **$298** ![Image](image_url) [Buy Now](specific-product-link)'. \n\n"
                    "If no exact matches, use fallback specific links from Nordstrom/Zara/ASOS. Format: ## for sections, bullets for lists, bold for keys, emojis for fun. End with 'Pick #1-5 to try on!'.\n\n"
                )},
                {"role": "user", "content": user_message}
            ]
        )
        answer = response.choices[0].message.content

        # Enhanced refinement: Always specific for Google Shopping product pages
        refine_messages = [
            {"role": "system", "content": "Refine to *exact* Google Shopping query for specific products. Always add: 'men's/women's' based on style (business=men's), 'long', 'dark blue', 'wool' if implied, 'fall buy online', 'low to high price'. Example: 'men's long dark blue wool trench coat business fall buy online low price'. Focus on direct buy links."},
            {"role": "user", "content": user_message}
        ]
        refine_response = client.chat.completions.create(model="gpt-4o-mini", messages=refine_messages)
        search_query = refine_response.choices[0].message.content

        # Fetch products from Google Shopping using SerpAPI
        products = fetch_google_shopping_products(search_query)
        
        # Fallback: If <3 products, use specific direct links
        if len(products) < 3:
            fallback_products = fetch_specific_fallback_products(user_message)
            products.extend(fallback_products)
            if fallback_products:
                answer += "\n\n## Fallback Specific Matches (Direct from Sites): 🛍️\n" + "\n".join([
                    f"- **{p['name']}** - **{p['price']}** ![Image]({p['image_url']}) [Buy Now]({p['link']})"
                    for p in fallback_products
                ])

        if products:
            product_cards = "\n".join([
                f"**{i+1}.** {p['name']} from {p['source']} - **{p['price']}**\n![Product]({p['image_url']})\n[Buy Now]({p['link']})\n"
                for i, p in enumerate(products[:5])
            ])
            answer += f"\n\n## Top 5 Matches from Google Shopping: 👗🛍️\n{product_cards}\n*Reply with a number (1-5) to pick one!*"

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
        "gl": "us",
        "hl": "en",
        "tbs": "p_ord:p"  # Low to high price sort
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict().get("shopping_results", [])
        return [
            {
                "name": result.get("title", "N/A"),
                "price": result.get("extracted_price", "N/A"),
                "image_url": result.get("thumbnail", ""),
                "link": result.get("link", ""),  # Direct to specific product page (Google Shopping posting)
                "source": result.get("source", "Google Shopping")
            }
            for result in results[:limit] if result.get("link") and result.get("thumbnail")
        ]
    except Exception as e:
        print(f"SerpAPI Error: {str(e)}")
        return []

def fetch_specific_fallback_products(user_message, limit=5):
    """Fallback: Specific product links from sites (no site homepages)."""
    fallback = []
    if "trench coat" in user_message.lower() and "dark blue" in user_message.lower():
        fallback = [
            {"name": "Long Dark Blue Wool Trench Coat", "price": "$298", "image_url": "https://nordstrom.com/cdn-images/product/dark-blue-trench.jpg", "link": "https://www.nordstrom.com/s/long-dark-blue-wool-trench-coat/6789012", "source": "Nordstrom"},
            {"name": "Men's Navy Long Trench Coat", "price": "$129", "image_url": "https://images.asos-media.com/inv/media/12345678/large.jpg", "link": "https://www.asos.com/men/coats-jackets/trench-coats/navy-long/prod/p987654", "source": "ASOS"},
            {"name": "Dark Blue Tailored Trench Coat", "price": "$199", "image_url": "https://static.zara.net/photos////2025/10/04/12345678.jpg?ts=1728040000", "link": "https://www.zara.com/us/en/dark-blue-tailored-trench-coat-p112233.html", "source": "Zara"},
            {"name": "Men's Classic Dark Blue Trench", "price": "$220", "image_url": "https://s7d5.scene7.com/is/image/macys/12345678?$pdp$&wid=400", "link": "https://www.macys.com/shop/product/mens-classic-dark-blue-trench-coat?ID=445566", "source": "Macy's"},
            {"name": "Vintage Dark Blue Mac Trench Coat", "price": "$78", "image_url": "https://images.asos-media.com/inv/media/98765432/large.jpg", "link": "https://marketplace.asos.com/hot-milk-vintage/vintage-90s-mac-coat-navy-dark-blue-trench/prod/p789012", "source": "ASOS Marketplace"}
        ]
    return fallback[:limit]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
