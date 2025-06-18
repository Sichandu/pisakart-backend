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
