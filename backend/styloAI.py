from google import genai
import os
import sys
import json
from serpapi import GoogleSearch
from PIL import Image
from io import BytesIO
import requests

# Import API keys from secrets file
try:
    from secrets import GEMINI_API_KEY, SERPAPI_KEY
except ImportError:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SERPAPI_KEY = os.getenv('SERPAPI_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("No Gemini API key found. Please add GEMINI_API_KEY to secrets.py")
    if not SERPAPI_KEY:
        raise ValueError("No SerpAPI key found. Please add SERPAPI_KEY to secrets.py")

os.environ['GOOGLE_API_KEY'] = GEMINI_API_KEY
client = genai.Client(api_key=GEMINI_API_KEY)

def search_clothing(query, max_results=10):
    """
    Search Google Shopping using SerpAPI for clothing items
    
    Args:
        query: Search query (e.g., "blue shirt", "red dress")
        max_results: Maximum number of results to return
    
    Returns:
        List of product dictionaries with brand, image_url, and product_link
    """
    print(f"🔍 Searching Google Shopping for '{query}' via SerpAPI...")
    
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": max_results
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        products = []
        shopping_results = results.get("shopping_results", [])
        
        print(f"   Found {len(shopping_results)} products!")
        
        for item in shopping_results[:max_results]:
            product = {
                "brand": item.get("source", "Unknown"),
                "image_url": item.get("thumbnail", "N/A"),
                "product_link": item.get("product_link", "N/A"),
            }
            products.append(product)
            print(f"   ✓ {product['brand']}")
        
        return products
        
    except Exception as e:
        print(f"❌ SerpAPI search failed: {str(e)}")
        print("\n💡 Make sure you have a valid SerpAPI key in secrets.py")
        return []

def download_image(url, save_path):
    """
    Download an image from URL
    
    Args:
        url: Image URL
        save_path: Path to save the image
    
    Returns:
        True if successful, False otherwise
    """
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            img.save(save_path)
            return True
    except Exception as e:
        print(f"   ✗ Failed to download image: {str(e)}")
    return False

def generate_outfit_visualization(user_image_path, clothing_image_url, output_path, product_info=None):
    """
    Generate an image of the user wearing the clothing using Gemini
    
    Args:
        user_image_path: Path to user's reference image
        clothing_image_url: URL or path to clothing image
        output_path: Where to save the generated image
        product_info: Optional dict with brand and product info
    
    Returns:
        Dictionary with success status and message
    """
    try:
        # Load user image
        print(f"\n🎨 Generating outfit visualization...")
        user_image = Image.open(user_image_path)
        
        # Download or load clothing image
        if clothing_image_url.startswith('http'):
            print(f"   Downloading clothing image...")
            response = requests.get(clothing_image_url, timeout=10)
            clothing_image = Image.open(BytesIO(response.content))
        else:
            clothing_image = Image.open(clothing_image_url)
        
        # Create prompt
        if product_info:
            prompt = f"""Create a realistic image of this person wearing the clothing item shown in the second image.

Product: {product_info.get('brand', 'Unknown brand')}

Instructions:
- Keep the person's face, body type, and skin tone exactly as shown
- Naturally fit the clothing item onto the person
- Maintain realistic lighting and shadows
- Ensure the clothing fits naturally and looks realistic
- Keep the background similar or neutral

Generate a high-quality, photorealistic result."""
        else:
            prompt = """Create a realistic image of this person wearing the clothing item shown in the second image. 
Keep the person's appearance natural and make the clothing fit realistically."""
        
        print(f"   Processing with Gemini...")
        
        # Generate the image
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt, user_image, clothing_image],
        )
        
        # Process the response
        image_saved = False
        text_response = ""
        
        # Check if response has candidates
        if not response or not hasattr(response, 'candidates') or not response.candidates:
            return {
                "success": False,
                "message": "Gemini returned no response. The model may not support image generation.",
                "text_response": ""
            }
        
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                text_response += part.text
            elif part.inline_data is not None:
                generated_image = Image.open(BytesIO(part.inline_data.data))
                generated_image.save(output_path)
                print(f"   ✅ Image saved as '{output_path}'")
                image_saved = True
        
        if image_saved:
            return {
                "success": True,
                "message": f"Image saved to {output_path}",
                "text_response": text_response
            }
        else:
            return {
                "success": False,
                "message": "No image data returned",
                "text_response": text_response
            }
            
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def main():
    """Main function to search for clothes and generate outfit visualizations"""
    if len(sys.argv) < 2:
        print("Usage: python styloAI.py <search_query> [--reference <path>] [--max-results N] [--generate-all]")
        print()
        print("Examples:")
        print('  python styloAI.py "blue shirt"')
        print('  python styloAI.py "red dress" --reference myimage.jpg')
        print('  python styloAI.py "black jeans" --max-results 5 --generate-all')
        print()
        print("Options:")
        print("  --reference PATH   Path to your reference image (default: ../Images/0B6103C4-3B57-44F7-AA0D-FD7F0CE3A3CF.jpg)")
        print("  --max-results N    Maximum number of products to search (default: 5)")
        print("  --generate-all     Generate visualizations for ALL products (default: first 3)")
        print()
        sys.exit(1)
    
    # Parse arguments
    args = sys.argv[1:]
    
    # Get max results
    max_results = 5
    if '--max-results' in args:
        idx = args.index('--max-results')
        if idx + 1 < len(args):
            try:
                max_results = int(args[idx + 1])
            except ValueError:
                print("⚠️  Invalid max-results value, using default: 5")
    
    # Get reference image
    reference_image = r"C:\Users\Rahul\Stylo.ai\Images\0B6103C4-3B57-44F7-AA0D-FD7F0CE3A3CF.jpg"
    if '--reference' in args:
        idx = args.index('--reference')
        if idx + 1 < len(args):
            reference_image = args[idx + 1]
    
    # Check if reference image exists
    if not os.path.exists(reference_image):
        print(f"❌ Reference image not found: {reference_image}")
        print("Please provide a valid reference image path with --reference")
        sys.exit(1)
    
    generate_all = '--generate-all' in args
    
    # Remove flags from query
    query = " ".join([arg for arg in args if not arg.startswith('--') and not arg.isdigit()])
    
    print(f"\n{'='*70}")
    print(f"👔 STYLO.AI - Virtual Outfit Generator")
    print(f"{'='*70}")
    print(f"Search: {query}")
    print(f"Reference Image: {reference_image}")
    print(f"{'='*70}\n")
    
    # Search for products
    products = search_clothing(query, max_results)
    
    if not products:
        print("\n❌ No products found. Try a different search query.")
        return
    
    print(f"\n{'='*70}")
    print(f"✅ Found {len(products)} products!")
    print(f"{'='*70}\n")
    
    # Display results
    for i, product in enumerate(products, 1):
        print(f"{i}. Brand: {product['brand']}")
        print(f"   🔗 Product Link: {product['product_link']}")
        print(f"   📸 Image URL: {product['image_url']}")
        print()
    
    # Save search results to JSON
    output_file = f"search_results_{query.replace(' ', '_')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"💾 Search results saved to: {output_file}\n")
    
    # Generate outfit visualizations
    print(f"{'='*70}")
    print(f"🎨 Generating Outfit Visualizations")
    print(f"{'='*70}\n")
    
    # Determine how many to generate
    num_to_generate = len(products) if generate_all else min(3, len(products))
    
    generated_images = []
    
    for i in range(num_to_generate):
        product = products[i]
        print(f"[{i+1}/{num_to_generate}] Generating outfit with {product['brand']}...")
        
        output_path = f"generated_outfit_{query.replace(' ', '_')}_{i+1}_{product['brand'].replace(' ', '_')}.png"
        
        result = generate_outfit_visualization(
            reference_image,
            product['image_url'],
            output_path,
            product_info=product
        )
        
        if result['success']:
            generated_images.append(output_path)
            print(f"   ✅ Success!\n")
        else:
            print(f"   ❌ Failed: {result['message']}\n")
    
    # Summary
    print(f"{'='*70}")
    print(f"✨ SUMMARY")
    print(f"{'='*70}")
    print(f"Products Found: {len(products)}")
    print(f"Outfits Generated: {len(generated_images)}/{num_to_generate}")
    print(f"\nGenerated Images:")
    for img in generated_images:
        print(f"  • {img}")
    print(f"\n💡 Tip: Use --generate-all to create visualizations for all products!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()

