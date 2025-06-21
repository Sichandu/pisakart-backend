from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["Pisakart"]
customers_collection = db["Customers"]
orders_collection = db["Orders"]

# Models
class Customer(BaseModel):
    name: str
    phonenumber: str  # Changed to string to handle international numbers
    street: str
    village: str
    pincode: str  # Changed to string as pincodes can have leading zeros
    city: str
    state: str

class CustomerInDB(Customer):
    id: str

class CartItem(BaseModel):
    name: str
    price: float
    image: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = 1

class OrderRequest(BaseModel):
    customer: Customer
    items: List[CartItem]
    subtotal: str
    total: str
    savings: str
    timestamp: str

class OrderInDB(OrderRequest):
    id: str
    processed_at: str

# Routes
@app.post("/customers", response_model=CustomerInDB, status_code=201)
async def create_customer(customer: Customer):
    try:
        customer_dict = customer.dict()
        result = await customers_collection.insert_one(customer_dict)
        return {**customer_dict, "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/customers", response_model=List[CustomerInDB])
async def get_customers():
    try:
        customers = []
        async for customer in customers_collection.find():
            customer["id"] = str(customer["_id"])
            customers.append(customer)
        return customers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orders", response_model=OrderInDB, status_code=201)
async def create_order(order: OrderRequest):
    try:
        order_dict = order.dict()
        
        # Add timestamps
        order_dict["processed_at"] = datetime.utcnow().isoformat()
        order_dict["timestamp"] = datetime.fromisoformat(
            order_dict["timestamp"].replace("Z", "")
        ).isoformat()
        
        # Store numeric values for calculations
        order_dict["subtotal_value"] = float(order_dict["subtotal"].replace("₹", "").replace(",", ""))
        order_dict["total_value"] = float(order_dict["total"].replace("₹", "").replace(",", ""))
        order_dict["savings_value"] = float(order_dict["savings"].replace("₹", "").replace(",", ""))
        
        # Insert into MongoDB
        result = await orders_collection.insert_one(order_dict)
        
        # Return the created order with MongoDB ID
        return {**order_dict, "id": str(result.inserted_id)}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/orders", response_model=List[OrderInDB])
async def get_orders():
    try:
        orders = []
        async for order in orders_collection.find():
            order["id"] = str(order["_id"])
            orders.append(order)
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "message": "Pisakart API is running",
        "endpoints": {
            "customers": {
                "POST": "/customers",
                "GET": "/customers"
            },
            "orders": {
                "POST": "/orders",
                "GET": "/orders"
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)








# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from motor.motor_asyncio import AsyncIOMotorClient
# from bson import ObjectId
# import os
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI()

# # CORS Configuration
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["POST", "GET"],
#     allow_headers=["*"],
# )

# # MongoDB Configuration
# MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
# DB_NAME = "pisakart"
# COLLECTION_NAME = "orders"

# # Initialize MongoDB client
# client = AsyncIOMotorClient(MONGODB_URL)
# db = client[DB_NAME]
# orders_collection = db[COLLECTION_NAME]

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
#         # Convert to dict and insert into MongoDB
#         order_dict = order.dict()
#         result = await orders_collection.insert_one(order_dict)
        
#         # Return the created order with MongoDB ID
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















# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pymongo import MongoClient
# from pydantic import BaseModel
# from datetime import datetime
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

# # MongoDB connection
# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
# client = MongoClient(MONGO_URI)
# db = client.pisapack
# carts_collection = db.carts

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
#         # Convert to dictionary and add processed timestamp
#         cart_data = cart.dict()
#         cart_data["processed_at"] = datetime.now().isoformat()
        
#         # Insert into MongoDB
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
#     return {"message": "PisaPack Cart API is running"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)









# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pymongo import MongoClient
# from pydantic import BaseModel, Field, validator
# from datetime import datetime
# from typing import List
# import os
# from dotenv import load_dotenv

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

# # MongoDB connection
# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
# client = MongoClient(MONGO_URI)
# db = client.pisapack
# orders_collection = db.orders  # Changed to orders collection

# class CartItem(BaseModel):
#     name: str = Field(..., min_length=1)
#     price: float = Field(..., gt=0)
#     image: str
#     category: str = "uncategorized"
#     quantity: int = Field(1, gt=0)

# class CartRequest(BaseModel):
#     items: List[CartItem]
#     subtotal: str
#     total: str
#     savings: str
#     timestamp: str

#     @validator('items')
#     def validate_items(cls, v):
#         if not v:
#             raise ValueError("At least one item is required")
#         return v

# @app.post("/save-cart")
# async def save_cart(cart: CartRequest):
#     try:
#         cart_data = cart.dict()
        
#         # Convert string timestamps to datetime objects
#         cart_data["timestamp"] = datetime.fromisoformat(cart_data["timestamp"].replace("Z", ""))
#         cart_data["processed_at"] = datetime.utcnow()
        
#         # Calculate numerical values from strings
#         cart_data["subtotal_value"] = float(cart_data["subtotal"].replace("₹", "").replace(",", ""))
#         cart_data["total_value"] = float(cart_data["total"].replace("₹", "").replace(",", ""))
#         cart_data["savings_value"] = float(cart_data["savings"].replace("₹", "").replace(",", ""))
        
#         # Insert into MongoDB
#         result = orders_collection.insert_one(cart_data)
        
#         return {
#             "status": "success",
#             "cart_id": str(result.inserted_id),
#             "message": "Cart saved successfully",
#             "items_count": len(cart.items)
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Error saving cart: {str(e)}"
#         )

# @app.get("/")
# async def root():
#     return {"message": "PisaPack Cart API is running"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)