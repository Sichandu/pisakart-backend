from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from bson import ObjectId
from fastapi import status
import random
from fastapi.responses import HTMLResponse
from typing import Optional, List

# Load env vars
load_dotenv()

app = FastAPI()

# CORS
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
db = client["PISA"]

# Collections
products_collection = db["products"]
orders_collection = db["customers"]
carts_collection = db["items"]
payment_collection = db["payments"]

# ----------------- Models -----------------
class Order(BaseModel):
    name: str
    phonenumber: int
    street: str
    village: str
    pincode: int
    city: str
    state: str
    pisa_code: str = None

class OrderInDB(Order):
    id: str
    order_ref_id: str

class CartItem(BaseModel):
    name: str
    price: float
    image: str
    category: str

class CartRequest(BaseModel):
    items: list[CartItem]
    status: Optional[str] = None  # Make status optional
    subtotal: str
    total: str
    savings: str
    timestamp: str

class PaymentMethodRequest(BaseModel):
    payment_method: str

class Address(BaseModel):
    name: str
    phonenumber: int
    street: str
    village: str
    pincode: int
    city: str
    state: str

class StatusUpdate(BaseModel):
    order_id: str
    new_status: str

class Customer(BaseModel):
    user_code: str
    name: str
    addresses: List[Address]
    order_ref_ids: List[str] = []  # Track all order references for this customer
    created_at: datetime = None

class Order(BaseModel):
    pisa_code: str  # Now required field
    order_ref_id: str
    created_at: datetime = None
    items: List[CartItem] = []
    subtotal: str = "0"
    total: str = "0"
    status: str = "Ordered"

class Payment(BaseModel):
    order_ref_id: str
    payment_method: str
    timestamp: datetime = None

class CustomerResponse(BaseModel):
    name: str
    address: str
    pisa_code: str

class OrderItem(BaseModel):
    name: str
    price: float
    image: str
    category: str

class OrderResponse(BaseModel):
    order_id: str
    date: str
    items: List[OrderItem]
    subtotal: float
    total: float
    savings: float
    status: str
    payment_method: str    
# ----------------- Helper Functions -----------------
def fix_objectids(doc):
    if isinstance(doc, list):
        return [fix_objectids(item) for item in doc]
    if not isinstance(doc, dict):
        return doc
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    for key, value in doc.items():
        if isinstance(value, dict):
            doc[key] = fix_objectids(value)
        elif isinstance(value, list):
            doc[key] = [fix_objectids(item) if isinstance(item, dict) else item for item in value]
    return doc

def generate_order_ref_id():
    return str(ObjectId())

@app.post("/save-cart")
async def save_cart(cart: CartRequest):
    try:
        cart_data = cart.dict()
        cart_data["processed_at"] = datetime.utcnow()

        # 👇 Fetch latest user pisa_code from orders collection
        latest_user = await orders_collection.find_one(sort=[("_id", -1)])
        pisa_code = latest_user.get("pisa_code") or latest_user.get("user_code") if latest_user else None

        cart_data["user_code"] = pisa_code  # ✅ Attach pisa_code to the cart

        # 🟢 Status handling
        if "status" not in cart_data or not cart_data["status"]:
            if "items" in cart_data and cart_data["items"]:
                cart_data["status"] = "ordered"
            else:
                cart_data["status"] = "Ordered"

        # 💾 Insert into DB
        result = await carts_collection.insert_one(cart_data)

        return {
            "status": "success",
            "cart_id": str(result.inserted_id),
            "user_code": pisa_code,
            "message": "Cart saved successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/payment-method")
async def save_payment_method(request: PaymentMethodRequest):
    if request.payment_method not in ["prepaid", "cod"]:
        raise HTTPException(status_code=400, detail="Invalid payment method")

    # 👉 Get latest pisa_code
    latest_user = await orders_collection.find_one(sort=[("_id", -1)])
    pisa_code = latest_user.get("pisa_code") or latest_user.get("user_code") if latest_user else None

    doc = {
        "payment_method": request.payment_method, 
        "timestamp": datetime.utcnow(),
        "user_code": pisa_code
    }
    result = await payment_collection.insert_one(doc)
    return {"status": "success", "payment_id": str(result.inserted_id)}


@app.post("/orders", response_model=OrderInDB, status_code=201)
async def add_order(order: Order):
    try:
        order_dict = order.dict()
        order_dict["created_at"] = datetime.utcnow()
        order_dict["order_ref_id"] = generate_order_ref_id()
        
        # Store the complete address with each order
        order_dict["address"] = {
            "street": order_dict.get("street"),
            "village": order_dict.get("village"),
            "pincode": order_dict.get("pincode"),
            "city": order_dict.get("city"),
            "state": order_dict.get("state")
        }

        # Rest of your existing order processing logic...
        # (pisa_code handling, cart linking, payment linking, etc.)

        result = await orders_collection.insert_one(order_dict)
        return {**order_dict, "id": str(result.inserted_id)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders")
async def get_orders():
    orders = []
    async for doc in orders_collection.find():
        # Handle both old and new format orders
        if "address" in doc:
            # New format with embedded address
            address = doc["address"]
            order_data = {
                "id": str(doc["_id"]),
                "pisa_code": doc.get("user_code", doc.get("pisa_code", "-")),
                "name": doc.get("name", "-"),
                "phonenumber": doc.get("phonenumber", "-"),
                "street": address.get("street", "-"),
                "village": address.get("village", "-"),
                "pincode": address.get("pincode", "-"),
                "city": address.get("city", "-"),
                "state": address.get("state", "-"),
                "created_at": doc.get("created_at", datetime.utcnow())
            }
            orders.append(order_data)
        else:
            # Old format with addresses array
            for address in doc.get("addresses", []):
                order_data = {
                    "id": str(doc["_id"]),
                    "pisa_code": doc.get("user_code", doc.get("pisa_code", "-")),
                    "name": doc.get("name", address.get("name", "-")),
                    "phonenumber": doc.get("phonenumber", address.get("phonenumber", "-")),
                    "street": address.get("street", "-"),
                    "village": address.get("village", "-"),
                    "pincode": address.get("pincode", "-"),
                    "city": address.get("city", "-"),
                    "state": address.get("state", "-"),
                    "created_at": doc.get("created_at", datetime.utcnow())
                }
                orders.append(order_data)
    
    # Sort by creation date (newest first)
    orders.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
    return orders

@app.get("/carts")
async def get_carts():
    carts = []
    async for cart in carts_collection.find():
        cart_data = {
            "id": str(cart.get("_id")),
            "pisa_code": cart.get("user_code", "-"),
            "items": cart.get("items", []),
            "status": cart.get("status", "Ordered"),  # Ensure status is included
            "subtotal": cart.get("subtotal", "0"),
            "total": cart.get("total", "0"),
            "savings": cart.get("savings", "0"),
            "timestamp": cart.get("timestamp"),
            "processed_at": cart.get("processed_at")
        }
        carts.append(cart_data)
    return carts

@app.get("/payments", response_model=list[dict])
async def get_payments():
    payments = []
    async for payment in payment_collection.find():
        payments.append(fix_objectids(payment))
    return payments


@app.post("/carts/update-status")
async def update_cart_status(request: Request):
    data = await request.json()
    order_id = data.get('order_id')
    new_status = data.get('new_status')
    
    result = await carts_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 1:
        return {"message": f"Status updated to {new_status}"}
    else:
        raise HTTPException(status_code=404, detail="Order not found")

@app.get("/carts/notifications")
async def get_notifications():
    carts = []
    async for cart in carts_collection.find({
        "status": {"$in": ["cancelled", "requested for return"]},
        "viewed": {"$ne": True}
    }).sort("updated_at", -1).limit(10):
        carts.append(fix_objectids(cart))
    return carts

# New endpoints for myorders.html
@app.get("/my-orders", response_class=HTMLResponse)
async def my_orders_page():
    with open("myorders.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/user-info/{pisa_code}")
async def get_user_info(pisa_code: str):
    # Try both pisa_code and user_code fields
    user = await orders_collection.find_one({
        "$or": [
            {"pisa_code": pisa_code},
            {"user_code": pisa_code}
        ]
    })
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="We couldn't find your account. Please check your PISA Code."
        )
    
    # Get name from either top level or first address
    name = user.get("name")
    if not name and "addresses" in user and user["addresses"]:
        name = user["addresses"][0].get("name")
    
    # Build address from available fields
    address = format_user_address(user)
    
    return {
        "name": name or "Customer",
        "address": address or "Address not available"
    }

def format_user_address(user):
    """Helper to format address from either direct fields or addresses array"""
    if "street" in user:  # New format
        return ", ".join(filter(None, [
            user.get("street"),
            user.get("village"),
            user.get("city"),
            user.get("state"),
            str(user.get("pincode", ""))
        ]))
    elif "addresses" in user and user["addresses"]:  # Old format
        addr = user["addresses"][0]
        return ", ".join(filter(None, [
            addr.get("street"),
            addr.get("village"),
            addr.get("city"),
            addr.get("state"),
            str(addr.get("pincode", ""))
        ]))
    return None

@app.get("/my-orders/{pisa_code}")
async def get_my_orders(pisa_code: str):
    # Find user by either pisa_code or user_code
    user = await orders_collection.find_one({
        "$or": [
            {"pisa_code": pisa_code},
            {"user_code": pisa_code}
        ]
    })
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found. Please check your PISA Code."
        )
    
    orders = []
    
    # Find all orders for this user
    async for order in orders_collection.find({
        "$or": [
            {"pisa_code": pisa_code},
            {"user_code": pisa_code}
        ]
    }):
        order_ref_id = order.get("order_ref_id")
        if not order_ref_id:
            continue
            
        cart = await carts_collection.find_one({"order_ref_id": order_ref_id})
        if not cart:
            continue
            
        orders.append({
            "order_id": str(order.get("_id")),
            "order_date": order.get("created_at", datetime.utcnow()),
            "items": cart.get("items", []),
            "total": cart.get("total", "0"),
            "status": cart.get("status", "Processing")
        })
    
    # Sort by date (newest first)
    orders.sort(key=lambda x: x["order_date"], reverse=True)
    
    # Build address
    address_parts = []
    if all(field in user for field in ["street", "city", "state", "pincode"]):
        address_parts.extend([
            user.get("street", ""),
            user.get("village", ""),
            user.get("city", ""),
            user.get("state", ""),
            str(user.get("pincode", ""))
        ])
    elif "addresses" in user and user["addresses"]:
        address = user["addresses"][0]
        address_parts.extend([
            address.get("street", ""),
            address.get("village", ""),
            address.get("city", ""),
            address.get("state", ""),
            str(address.get("pincode", ""))
        ])
    
    return {
        "name": user.get("name", "Customer"),
        "address": ", ".join(filter(None, address_parts)) or "Address not available",
        "orders": orders
    }

@app.post("/create-user")
async def create_user(address: Address):
    while True:
        user_code = str(random.randint(100000, 999999))
        exists = await orders_collection.find_one({"user_code": user_code})
        if not exists:
            break

    user_doc = {
        "user_code": user_code,
        "addresses": [address.dict()],
        "created_at": datetime.utcnow()
    }
    await orders_collection.insert_one(user_doc)
    return {"detail": "User created", "user_code": user_code}

@app.post("/create_user")
async def create_user(data: dict):
    pisa_code = str(random.randint(100000, 999999))
    while await orders_collection.find_one({"pisa_code": pisa_code}):
        pisa_code = str(random.randint(100000, 999999))
    data["pisa_code"] = pisa_code
    data["orders"] = []
    data["created_at"] = datetime.utcnow()
    await orders_collection.insert_one(data)
    return {"pisa_code": pisa_code}

@app.get("/get-user/{user_code}")
async def get_user(user_code: str):
    user = await orders_collection.find_one({"user_code": user_code})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_code": user["user_code"],
        "addresses": user.get("addresses", [])
    }

@app.post("/add-address/{user_code}")
async def add_address(user_code: str, address: Address):
    result = await orders_collection.update_one(
        {"user_code": user_code},
        {"$push": {"addresses": address.dict()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "Address added"}