from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from datetime import datetime

# Import our Stylo.AI functions
from styloAI import (
    parse_natural_language_query,
    search_clothing,
    generate_outfit_visualization
)

app = FastAPI(
    title="Stylo.AI API",
    version="1.0.0",
    description="Virtual Outfit Generator API - Natural language to outfit visualizations"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class GenerateOutfitRequest(BaseModel):
    prompt: str
    reference_image: Optional[str] = r"C:\Users\Rahul\Stylo.ai\Images\Rahul.jpg"
    max_results: Optional[int] = 2

class ProductInfo(BaseModel):
    brand: str
    image_url: str
    product_link: str

class GenerateOutfitResponse(BaseModel):
    success: bool
    message: str
    user_query: str
    parsed_query: str
    clothing_type: Optional[str]
    style: Optional[str]
    gender: Optional[str]
    products: List[ProductInfo]
    generated_images: List[str]
    timestamp: str

@app.get("/")
async def root():
    """API root - provides information about available endpoints"""
    return {
        "service": "Stylo.AI API",
        "version": "1.0.0",
        "status": "online",
        "description": "Virtual Outfit Generator - Natural language to outfit visualizations",
        "endpoints": {
            "POST /api/generate-outfit": "Generate outfit visualizations from natural language",
            "GET /api/image/{filename}": "Retrieve a generated outfit image",
            "GET /api/images": "List all generated images",
            "DELETE /api/image/{filename}": "Delete a generated image",
            "GET /health": "Health check endpoint",
            "GET /docs": "Interactive API documentation"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Stylo.AI API",
        "version": "1.0.0"
    }

@app.post("/api/generate-outfit", response_model=GenerateOutfitResponse)
async def generate_outfit(request: GenerateOutfitRequest):
    """
    Generate outfit visualizations based on natural language prompt
    
    Args:
        prompt: Natural language description (e.g., "I need a formal suit for a wedding")
        reference_image: Path to user's reference image (optional)
        max_results: Number of products to search (default: 2)
    
    Returns:
        Generated outfit information and image paths
    """
    try:
        print(f"\n🎨 Processing request: {request.prompt}")
        
        # Step 1: Parse natural language query
        parsed_info = parse_natural_language_query(request.prompt)
        search_query = parsed_info.get('search_query', request.prompt)
        
        print(f"   Parsed query: {search_query}")
        
        # Step 2: Search for products
        products = search_clothing(search_query, request.max_results)
        
        if not products:
            raise HTTPException(
                status_code=404,
                detail="No products found for the given query"
            )
        
        print(f"   Found {len(products)} products")
        
        # Step 3: Generate outfit visualizations
        output_dir = r"C:\Users\Rahul\Stylo.ai\backend\clothing_images"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        generated_images = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, product in enumerate(products):
            print(f"   Generating image {i+1}/{len(products)}...")
            
            filename = f"outfit_{timestamp}_{i+1}_{product['brand'].replace(' ', '_')}.png"
            output_path = os.path.join(output_dir, filename)
            
            result = generate_outfit_visualization(
                request.reference_image,
                product['image_url'],
                output_path,
                product_info=product
            )
            
            if result['success']:
                # Store relative path for API response
                generated_images.append(filename)
                print(f"   ✓ Generated: {filename}")
            else:
                print(f"   ✗ Failed: {result['message']}")
        
        if not generated_images:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate any outfit visualizations"
            )
        
        # Step 4: Return response
        return GenerateOutfitResponse(
            success=True,
            message=f"Successfully generated {len(generated_images)} outfit visualization(s)",
            user_query=request.prompt,
            parsed_query=search_query,
            clothing_type=parsed_info.get('clothing_type'),
            style=parsed_info.get('style'),
            gender=parsed_info.get('gender'),
            products=[ProductInfo(**p) for p in products],
            generated_images=generated_images,
            timestamp=timestamp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

@app.get("/api/image/{filename}")
async def get_image(filename: str):
    """
    Retrieve a generated outfit image
    
    Args:
        filename: Name of the generated image file
    
    Returns:
        The image file
    """
    image_path = os.path.join(r"C:\Users\Rahul\Stylo.ai\backend\clothing_images", filename)
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(
        image_path,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@app.get("/api/images")
async def list_images():
    """
    List all generated outfit images
    
    Returns:
        List of available image filenames
    """
    image_dir = r"C:\Users\Rahul\Stylo.ai\backend\clothing_images"
    
    if not os.path.exists(image_dir):
        return {"images": []}
    
    images = [
        f for f in os.listdir(image_dir)
        if f.endswith(('.png', '.jpg', '.jpeg'))
    ]
    
    return {
        "total": len(images),
        "images": sorted(images, reverse=True)  # Most recent first
    }

@app.delete("/api/image/{filename}")
async def delete_image(filename: str):
    """
    Delete a generated outfit image
    
    Args:
        filename: Name of the image file to delete
    
    Returns:
        Success message
    """
    image_path = os.path.join(r"C:\Users\Rahul\Stylo.ai\backend\clothing_images", filename)
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        os.remove(image_path)
        return {"success": True, "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete image: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 Starting Stylo.AI Backend API")
    print("="*60)
    print("📍 API Root: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("💚 Health Check: http://localhost:8000/health")
    print("="*60)
    print("🎨 Ready to generate outfit visualizations!")
    print("⏹️  Press Ctrl+C to stop")
    print("="*60 + "\n")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

