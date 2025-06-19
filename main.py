from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = "pisakart"
COLLECTION_NAME = "orders"

# Initialize MongoDB client
client = AsyncIOMotorClient(MONGODB_URL)
db = client[DB_NAME]
orders_collection = db[COLLECTION_NAME]

class Order(BaseModel):
    name: str
    phonenumber: int
    street: str
    village: str
    pincode: int
    city: str
    state: str

class OrderInDB(Order):
    id: str

@app.post("/orders", response_model=OrderInDB, status_code=201)
async def add_order(order: Order):
    try:
        # Convert to dict and insert into MongoDB
        order_dict = order.dict()
        result = await orders_collection.insert_one(order_dict)
        
        # Return the created order with MongoDB ID
        return {**order_dict, "id": str(result.inserted_id)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders", response_model=list[OrderInDB])
async def get_orders():
    orders = []
    async for order in orders_collection.find():
        order["id"] = str(order["_id"])
        orders.append(order)
    return orders















# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from motor.motor_asyncio import AsyncIOMotorClient
# from fastapi.middleware.cors import CORSMiddleware
# import os

# app = FastAPI()

# # === CORS MIDDLEWARE ===
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # You can replace * with your Netlify URL for security
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # === MongoDB CONFIG ===
# MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
# DB_NAME = "pisakart"
# COLLECTION_NAME = "orders"

# # === CONNECT TO DB ===
# client = AsyncIOMotorClient(MONGODB_URL)
# db = client[DB_NAME]
# orders_collection = db[COLLECTION_NAME]

# # === Pydantic Models ===
# class Order(BaseModel):
#     name: str
#     phonenumber: int
#     street: str
#     village: str
#     pincode: int
#     city: str
#     state: str

# class OrderInDB(Order):
#     id: str

# # === Create Order Endpoint ===
# @app.post("/orders", response_model=OrderInDB, status_code=201)
# async def add_order(order: Order):
#     try:
#         order_dict = order.dict()
#         result = await orders_collection.insert_one(order_dict)
#         return {**order_dict, "id": str(result.inserted_id)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/orders", response_model=list[OrderInDB])
# async def get_orders():
#     orders = []
#     async for order in orders_collection.find():
#         order["id"] = str(order["_id"])
#         orders.append(order)
#     return orders


















#CART BACKEND CODE

# import os
# from fastapi import FastAPI, HTTPException, Request
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
# from fastapi.responses import HTMLResponse, RedirectResponse
# from pydantic import BaseModel
# from typing import List, Optional
# from datetime import datetime
# import motor.motor_asyncio
# from bson import ObjectId
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.encoders import jsonable_encoder


# app = FastAPI()

# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Mount static files
# app.mount("/static", StaticFiles(directory="templates"), name="static")

# # Templates
# templates = Jinja2Templates(directory="templates")

# # MongoDB setup
# MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
# client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
# db = client.pisakart

# # Models
# class Product(BaseModel):
#     name: str
#     description: str
#     price: float
#     image: str

# class CartItem(BaseModel):
#     product_id: str
#     quantity: int = 1

# class Cart(BaseModel):
#     user_id: str = "default"
#     items: List[CartItem] = []
#     created_at: datetime = datetime.now()
#     updated_at: datetime = datetime.now()

# # Helper functions
# async def get_product(product_id: str):
#     try:
#         product = await db.products.find_one({"_id": ObjectId(product_id)})
#         if not product:
#             raise HTTPException(status_code=404, detail="Product not found")
#         product["_id"] = str(product["_id"])
#         return product
#     except:
#         raise HTTPException(status_code=400, detail="Invalid product ID")

# async def get_user_cart(user_id: str = "default"):
#     cart = await db.carts.find_one({"user_id": user_id})
#     if not cart:
#         # Create a new cart if none exists
#         new_cart = Cart()
#         result = await db.carts.insert_one(new_cart.dict())
#         cart = await db.carts.find_one({"_id": result.inserted_id})
#     return cart

# # Routes
# @app.get("/", response_class=HTMLResponse)
# async def home(request: Request):
#     return templates.TemplateResponse("home.html", {"request": request})

# @app.get("/cart", response_class=HTMLResponse)
# async def cart_page(request: Request):
#     return templates.TemplateResponse("cart.html", {"request": request})

# # API Endpoints
# @app.get("/api/products")
# async def get_products():
#     products = []
#     async for product in db.products.find():
#         product["_id"] = str(product["_id"])
#         products.append(product)
#     return products

# @app.get("/api/cart")
# async def get_cart():
#     cart = await get_user_cart()
#     cart_items = []
    
#     for item in cart["items"]:
#         try:
#             product = await get_product(item["product_id"])
#             cart_items.append({
#                 "product": product,
#                 "quantity": item["quantity"]
#             })
#         except:
#             continue  # Skip invalid products
    
#     return {"items": cart_items}

# @app.get("/api/cart/count")
# async def get_cart_count():
#     cart = await get_user_cart()
#     count = sum(item["quantity"] for item in cart["items"])
#     return {"count": count}


# # Update the add_to_cart endpoint
# @app.post("/api/cart")
# async def add_to_cart(item: CartItem):
#     try:
#         # Verify product exists first
#         product = await get_product(item.product_id)
        
#         cart = await get_user_cart()
        
#         # Check if product already exists in cart
#         existing_item = next((i for i in cart["items"] if i["product_id"] == item.product_id), None)
        
#         if existing_item:
#             # Update quantity
#             new_quantity = existing_item["quantity"] + item.quantity
#             await db.carts.update_one(
#                 {"user_id": "default", "items.product_id": item.product_id},
#                 {"$set": {"items.$.quantity": new_quantity, "updated_at": datetime.now()}}
#             )
#         else:
#             # Add new item
#             await db.carts.update_one(
#                 {"user_id": "default"},
#                 {"$push": {"items": jsonable_encoder(item)}, "$set": {"updated_at": datetime.now()}}
#             )
        
#         return {"status": "success", "message": "Item added to cart"}
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))


# @app.put("/api/cart/{product_id}")
# async def update_cart_item(product_id: str, item: CartItem):
#     # Verify product exists first
#     await get_product(product_id)
    
#     cart = await get_user_cart()
    
#     # Check if product exists in cart
#     existing_item = next((i for i in cart["items"] if i["product_id"] == product_id), None)
    
#     if not existing_item:
#         raise HTTPException(status_code=404, detail="Item not found in cart")
    
#     await db.carts.update_one(
#         {"user_id": "default", "items.product_id": product_id},
#         {"$set": {"items.$.quantity": item.quantity, "updated_at": datetime.now()}}
#     )
    
#     return {"status": "success", "message": "Cart updated"}

# @app.delete("/api/cart/{product_id}")
# async def remove_cart_item(product_id: str):
#     result = await db.carts.update_one(
#         {"user_id": "default"},
#         {"$pull": {"items": {"product_id": product_id}}, "$set": {"updated_at": datetime.now()}}
#     )
    
#     if result.modified_count == 0:
#         raise HTTPException(status_code=404, detail="Item not found in cart")
    
#     return {"status": "success", "message": "Item removed from cart"}

# @app.post("/api/cart/checkout")
# async def checkout():
#     cart = await get_user_cart()
    
#     if not cart["items"]:
#         raise HTTPException(status_code=400, detail="Cart is empty")
    
#     # Clear the cart
#     await db.carts.update_one(
#         {"user_id": "default"},
#         {"$set": {"items": [], "updated_at": datetime.now()}}
#     )
    
#     return {"status": "success", "message": "Checkout successful"}

# # Initialize database with sample data
# @app.on_event("startup")
# async def startup_db():
#     # Check if products exist
#     if await db.products.count_documents({}) == 0:
#         sample_products = [
#             {
#                 "name": "Wireless Headphones",
#                 "description": "High-quality wireless headphones with noise cancellation",
#                 "price": 99.99,
#                 "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop"
#             },
#             {
#                 "name": "Smart Watch",
#                 "description": "Feature-rich smartwatch with health monitoring",
#                 "price": 199.99,
#                 "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&auto=format&fit=crop"
#             },
#             {
#                 "name": "Bluetooth Speaker",
#                 "description": "Portable speaker with 20h battery life",
#                 "price": 59.99,
#                 "image": "https://images.unsplash.com/photo-1572569511254-d8f925fe2cbb?w=500&auto=format&fit=crop"
#             },
#             {
#                 "name": "Laptop Backpack",
#                 "description": "Durable backpack with USB charging port",
#                 "price": 49.99,
#                 "image": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&auto=format&fit=crop"
#             }
#         ]
#         await db.products.insert_many(sample_products)
#         print("Inserted sample products")