from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["PISA"]  # 🔁 Unified database name

# Collections
orders_collection = db["customers"]  # orders → customers collection
carts_collection = db["items"]       # cart → items collection

# ----------------- Models -----------------
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

class CartItem(BaseModel):
    name: str
    price: float
    image: str
    category: str

class CartRequest(BaseModel):
    items: list[CartItem]
    subtotal: str
    total: str
    savings: str
    timestamp: str

# ----------------- API Routes -----------------

@app.post("/orders", response_model=OrderInDB, status_code=201)
async def add_order(order: Order):
    try:
        order_dict = order.dict()
        result = await orders_collection.insert_one(order_dict)
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

@app.post("/save-cart")
async def save_cart(cart: CartRequest):
    try:
        cart_data = cart.dict()
        cart_data["processed_at"] = datetime.now().isoformat()
        result = await carts_collection.insert_one(cart_data)
        return {
            "status": "success",
            "cart_id": str(result.inserted_id),
            "message": "Cart saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "PISA DB API for Orders and Cart is running"}

# Optional: Only needed if running this file directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)









# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from datetime import datetime
# from motor.motor_asyncio import AsyncIOMotorClient
# from pymongo import MongoClient
# from bson import ObjectId
# import os
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# app = FastAPI()

# # CORS configuration
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- Order Functionality (Using Motor) ---
# MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
# DB_NAME = "pisakart"
# COLLECTION_NAME = "orders"

# motor_client = AsyncIOMotorClient(MONGODB_URL)
# order_db = motor_client[DB_NAME]
# orders_collection = order_db[COLLECTION_NAME]

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

# # --- Cart Functionality (Using PyMongo) ---
# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
# pymongo_client = MongoClient(MONGO_URI)
# cart_db = pymongo_client.pisapack
# carts_collection = cart_db.carts

# class CartItem(BaseModel):
#     name: str
#     price: float
#     image: str
#     category: str

# class CartRequest(BaseModel):
#     items: list[CartItem]
#     subtotal: str
#     total: str
#     savings: str
#     timestamp: str

# @app.post("/save-cart")
# async def save_cart(cart: CartRequest):
#     try:
#         cart_data = cart.dict()
#         cart_data["processed_at"] = datetime.now().isoformat()
#         result = carts_collection.insert_one(cart_data)
#         return {
#             "status": "success",
#             "cart_id": str(result.inserted_id),
#             "message": "Cart saved successfully"
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/")
# async def root():
#     return {"message": "PisaKart Orders + PisaPack Cart API is running"}

# # Optional: Only needed if running this file directly
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)