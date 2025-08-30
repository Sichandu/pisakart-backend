from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from bson import ObjectId
import random
from fastapi.responses import HTMLResponse
from typing import Optional, List, Any
from pymongo.errors import DuplicateKeyError
import traceback
from fastapi import Response
import json



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
# MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://pisakart_admin:pisakart2025@cluster0.mongodb.net/PISA")
client = AsyncIOMotorClient(MONGO_URI)
db = client["PISA"]

# Collections
address_history_collection = db["address_history"]
orders_collection = db["customers"]
carts_collection = db["items"]
payment_collection = db["payments"]

# --------------------
# Models (Pydantic)
# --------------------
class CartItem(BaseModel):
    name: str
    price: float
    image: Optional[str] = None
    category: Optional[str] = None

class CartRequest(BaseModel):
    items: List[CartItem]
    status: Optional[str] = None
    subtotal: Optional[str] = "0"
    total: Optional[str] = "0"
    savings: Optional[str] = "0"
    timestamp: Optional[str] = None

class PaymentMethodRequest(BaseModel):
    payment_method: str
    timestamp: Optional[str] = None

class Address(BaseModel):
    name: str
    phonenumber: str
    street: str
    village: str
    pincode: str
    city: str
    state: str
    type: Optional[str] = None
    userCode: Optional[str] = None
    timestamp: Optional[str] = None

class OrderModel(BaseModel):
    pisa_code: Optional[str] = None
    order_ref_id: Optional[str] = None
    created_at: Optional[datetime] = None
    items: Optional[List[CartItem]] = []
    subtotal: Optional[str] = "0"
    total: Optional[str] = "0"
    status: Optional[str] = "Ordered"
    # address fields may be included

# --------------------
# Startup: indexes
# --------------------
@app.on_event("startup")
async def startup_db_client():
    # Create unique index to prevent duplicate addresses for same user
    try:
        await address_history_collection.create_index(
            [
                ("userCode", 1),
                ("street", 1),
                ("pincode", 1),
                ("phonenumber", 1)
            ],
            name="unique_address_per_user",
            unique=True,
            partialFilterExpression={"type": {"$in": ["new", "added"]}}
        )
    except Exception:
        # index may already exist or DB not ready; ignore
        pass

# --------------------
# Helpers
# --------------------
def fix_objectids(doc: Any):
    """
    Convert any Mongo _id to string and keep both '_id' and 'id' for frontend compatibility.
    Works recursively for lists/dicts.
    """
    if isinstance(doc, list):
        return [fix_objectids(item) for item in doc]
    if not isinstance(doc, dict):
        return doc
    if "_id" in doc:
        # convert to str and ensure both fields exist
        doc["_id"] = str(doc["_id"])
        doc["id"] = doc["_id"]
    for key, value in list(doc.items()):
        if isinstance(value, dict):
            doc[key] = fix_objectids(value)
        elif isinstance(value, list):
            doc[key] = [fix_objectids(item) if isinstance(item, dict) else item for item in value]
    return doc

def generate_order_ref_id():
    return str(ObjectId())

async def extract_id_from_request(request: Request, query_id: Optional[str] = None) -> Optional[str]:
    """
    Try to extract id (or _id) from:
      - query param (query_id)
      - JSON body { id, _id, payment_id, address_id, cart_id }
    Returns None if not found.
    """
    if query_id:
        return query_id
    try:
        body = await request.json()
        if isinstance(body, dict):
            return body.get("id") or body.get("_id") or body.get("payment_id") or body.get("address_id") or body.get("cart_id")
    except Exception:
        # No body or not JSON
        pass
    return None

# --------------------
# Address endpoints
# --------------------
@app.post("/create-user")
async def create_user(address: dict):
    """Create new user with initial address"""
    while True:
        user_code = str(random.randint(100000, 999999))
        exists = await orders_collection.find_one({"user_code": user_code})
        if not exists:
            break

    user_doc = {"user_code": user_code, "addresses": [address], "created_at": datetime.utcnow()}
    await orders_collection.insert_one(user_doc)

    # Record in history (non-fatal if duplicate)
    try:
        await address_history_collection.insert_one({
            **address,
            "userCode": user_code,
            "type": "new",
            "timestamp": datetime.utcnow().isoformat()
        })
    except DuplicateKeyError:
        pass
    return {"detail": "User created", "user_code": user_code}

@app.post("/add-address/{user_code}")
async def add_address(user_code: str, address: dict):
    existing_address = await address_history_collection.find_one({
        "userCode": user_code,
        "street": address.get("street"),
        "pincode": address.get("pincode"),
        "phonenumber": address.get("phonenumber")
    })
    if existing_address:
        raise HTTPException(status_code=400, detail="This address already exists for this user")
    result = await orders_collection.update_one({"user_code": user_code}, {"$push": {"addresses": address}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await address_history_collection.insert_one({
        **address,
        "userCode": user_code,
        "type": "added",
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"detail": "Address added"}

@app.get("/get-user/{user_code}")
async def get_user(user_code: str):
    user = await orders_collection.find_one({"user_code": user_code})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_code": user["user_code"], "addresses": user.get("addresses", [])}

@app.post("/api/record-address")
async def record_address(address: dict):
    """Record when an address is selected for an order"""
    if address.get("type") != "selected":
        return {"status": "skipped", "reason": "only tracking selections"}
    address["timestamp"] = datetime.utcnow().isoformat()
    await address_history_collection.insert_one(address)
    return {"status": "success"}

@app.get("/api/get-address-history")
async def get_address_history():
    addresses = []
    async for doc in address_history_collection.find().sort("timestamp", -1):
        addresses.append(fix_objectids(doc))
    return addresses

@app.delete("/api/delete-address")
async def api_delete_address(request: Request, id: Optional[str] = None):
    """
    Delete an address. Accepts id via:
      - query param ?id=...
      - JSON body { id: '...' } or { _id: '...' } or { address_id: '...' }
    """
    address_id = await extract_id_from_request(request, id)
    if not address_id or address_id.lower() == "undefined":
        raise HTTPException(status_code=400, detail="Address id is missing. Send ?id=... or JSON body {id:'...'}")
    try:
        oid = ObjectId(address_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid address id format.")
    res = await address_history_collection.find_one_and_delete({"_id": oid})
    if not res:
        raise HTTPException(status_code=404, detail="Address not found")
    return {"message": "Address deleted", "deletedItem": fix_objectids(res)}

@app.delete("/api/clear-address-history")
async def api_clear_address_history():
    result = await address_history_collection.delete_many({})
    return {"message": "Cleared address history", "deleted_count": result.deleted_count}


@app.post("/api/restore-address")
async def api_restore_address(payload: dict, request: Request):
    """
    Restore an address record. Accepts whatever the frontend sends.
    Returns clear errors instead of 500.
    """
    try:
        if not payload or not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a JSON object with address fields.")

        # Remove id fields so Mongo creates a fresh _id
        payload.pop("id", None)
        payload.pop("_id", None)

        # Fill minimal fields if missing (frontend often sends these)
        if "timestamp" not in payload or not payload.get("timestamp"):
            payload["timestamp"] = datetime.utcnow().isoformat()
        # ensure userCode exists (optional)
        payload["userCode"] = payload.get("userCode") or payload.get("user_code") or None

        # Insert (duplicate key will raise DuplicateKeyError)
        try:
            await address_history_collection.insert_one(payload)
            return {"message": "Address restored", "restored": fix_objectids(payload)}
        except DuplicateKeyError:
            # If duplicate because of unique index, return 409
            raise HTTPException(status_code=409, detail="Address already exists (duplicate).")
    except HTTPException:
        # re-raise known HTTP exceptions
        raise
    except Exception as e:
        # Log the traceback so you can inspect terminal
        traceback.print_exc()
        # Return friendly message for frontend
        raise HTTPException(status_code=500, detail=f"Server error while restoring address: {str(e)}")


@app.post("/carts", status_code=201)
async def create_cart_any(payload: dict, request: Request):
    """
    Accepts flexible cart payloads (not strict Pydantic) — coerces to DB-friendly shape.
    Returns 400 with details when data is invalid instead of 422.
    """
    try:
        if not payload or not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

        # Normalize items: frontend may send HTML, strings or objects; expect array of objects
        items = payload.get("items", [])
        # If items is a string that looks like JSON, parse it
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except Exception:
                # fallback to empty list
                items = []

        # Ensure items is an array
        if not isinstance(items, list):
            items = []

        # Coerce prices to numbers inside each item when possible
        normalized_items = []
        for it in items:
            if isinstance(it, str):
                # try parse JSON per item string
                try:
                    it = json.loads(it)
                except Exception:
                    it = {"name": str(it), "price": 0}
            if isinstance(it, dict):
                price = it.get("price", 0)
                try:
                    price = float(str(price).replace('₹', '').replace(',', '').strip())
                except Exception:
                    price = 0.0
                normalized_items.append({
                    "name": it.get("name", "") or "-",
                    "price": price,
                    "image": it.get("image"),
                    "category": it.get("category")
                })
        # build doc
        doc = {}
        doc["items"] = normalized_items
        # numbers: subtotal/total/savings might be strings with ₹ — coerce
        def _num(val):
            try:
                return float(str(val).replace('₹', '').replace(',', '').strip())
            except Exception:
                return 0.0
        doc["subtotal"] = str(_num(payload.get("subtotal", payload.get("sub_total", 0))))
        doc["total"] = str(_num(payload.get("total", payload.get("grand_total", 0))))
        doc["savings"] = str(_num(payload.get("savings", 0)))
        # timestamp handling: accept human readable or ISO
        ts = payload.get("timestamp") or payload.get("processed_at") or datetime.utcnow().isoformat()
        doc["timestamp"] = ts
        doc["processed_at"] = datetime.utcnow().isoformat()
        # attach user_code if provided, else recent user
        latest_user = await orders_collection.find_one(sort=[("_id", -1)])
        doc["user_code"] = payload.get("user_code") or (latest_user.get("pisa_code") or latest_user.get("user_code") if latest_user else None)
        doc["status"] = payload.get("status") or "Ordered"

        # Insert to DB
        inserted = await carts_collection.insert_one(doc)
        new_doc = await carts_collection.find_one({"_id": inserted.inserted_id})
        return fix_objectids(new_doc)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error creating cart: {str(e)}")


# --------------------
# Cart endpoints
# --------------------
@app.post("/save-cart")
async def save_cart(cart: CartRequest):
    try:
        cart_data = cart.dict()
        cart_data["processed_at"] = datetime.utcnow().isoformat()

        latest_user = await orders_collection.find_one(sort=[("_id", -1)])
        pisa_code = None
        if latest_user:
            pisa_code = latest_user.get("pisa_code") or latest_user.get("user_code")
        cart_data["user_code"] = pisa_code

        if "status" not in cart_data or not cart_data["status"]:
            cart_data["status"] = "ordered" if cart_data.get("items") else "Ordered"

        result = await carts_collection.insert_one(cart_data)
        return {"status": "success", "cart_id": str(result.inserted_id), "user_code": pisa_code, "message": "Cart saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/carts", status_code=201)
async def create_cart(payload: CartRequest):
    try:
        doc = payload.dict()
        if not doc.get("timestamp"):
            doc["timestamp"] = datetime.utcnow().isoformat()
        doc["processed_at"] = datetime.utcnow().isoformat()
        latest_user = await orders_collection.find_one(sort=[("_id", -1)])
        pisa_code = None
        if latest_user:
            pisa_code = latest_user.get("pisa_code") or latest_user.get("user_code")
        doc["user_code"] = pisa_code
        inserted = await carts_collection.insert_one(doc)
        new_doc = await carts_collection.find_one({"_id": inserted.inserted_id})
        return fix_objectids(new_doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/carts/{cart_id}")
async def delete_cart(cart_id: str):
    try:
        oid = ObjectId(cart_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cart id")
    result = await carts_collection.find_one_and_delete({"_id": oid})
    if not result:
        raise HTTPException(status_code=404, detail="Cart not found")
    return {"message": "Cart deleted", "deletedItem": fix_objectids(result)}

@app.delete("/carts")
async def delete_cart_by_body(request: Request, id: Optional[str] = None):
    cart_id = await extract_id_from_request(request, id)
    if not cart_id or cart_id.lower() == "undefined":
        raise HTTPException(status_code=400, detail="Cart id is missing. Send ?id=... or JSON body {id:'...'}")
    try:
        oid = ObjectId(cart_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cart id format.")
    res = await carts_collection.find_one_and_delete({"_id": oid})
    if not res:
        raise HTTPException(status_code=404, detail="Cart not found")
    return {"message": "Cart deleted", "deletedItem": fix_objectids(res)}

@app.post("/carts/update-status")
async def update_cart_status(request: Request):
    data = await request.json()
    order_id = data.get('order_id')
    new_status = data.get('new_status')
    if not order_id:
        raise HTTPException(status_code=400, detail="order_id missing")
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order id")
    result = await carts_collection.update_one({"_id": oid}, {"$set": {"status": new_status, "updated_at": datetime.utcnow().isoformat()}})
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

@app.get("/carts")
async def get_carts():
    carts = []
    async for cart in carts_collection.find():
        cart_data = {
            "id": str(cart.get("_id")),
            "pisa_code": cart.get("user_code", "-"),
            "items": cart.get("items", []),
            "status": cart.get("status", "Ordered"),
            "subtotal": cart.get("subtotal", "0"),
            "total": cart.get("total", "0"),
            "savings": cart.get("savings", "0"),
            "timestamp": cart.get("timestamp"),
            "processed_at": cart.get("processed_at")
        }
        carts.append(cart_data)
    return carts

# --------------------
# Payment endpoints
# --------------------
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

@app.get("/payments")
async def get_payments():
    payments = []
    async for payment in payment_collection.find().sort("timestamp", -1):
        payments.append(fix_objectids(payment))
    return payments

@app.post("/payments", status_code=201)
async def create_payment(request: PaymentMethodRequest):
    pm = request.payment_method
    latest_user = await orders_collection.find_one(sort=[("_id", -1)])
    pisa_code = None
    if latest_user:
        pisa_code = latest_user.get("pisa_code") or latest_user.get("user_code")
    doc = {
        "payment_method": pm,
        "timestamp": request.timestamp if request.timestamp else datetime.utcnow().isoformat(),
        "user_code": pisa_code
    }
    inserted = await payment_collection.insert_one(doc)
    new_doc = await payment_collection.find_one({"_id": inserted.inserted_id})
    return fix_objectids(new_doc)

@app.delete("/payments/{payment_id}")
async def delete_payment_by_param(payment_id: str):
    if not payment_id or payment_id.lower() == "undefined":
        raise HTTPException(status_code=400, detail="Payment id is missing or undefined.")
    try:
        oid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payment id format.")
    result = await payment_collection.find_one_and_delete({"_id": oid})
    if not result:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"message": "Payment deleted", "deletedItem": fix_objectids(result)}

@app.delete("/payments")
async def delete_payment(request: Request, id: Optional[str] = None):
    payment_id = await extract_id_from_request(request, id)
    if not payment_id or payment_id.lower() == "undefined":
        raise HTTPException(status_code=400, detail="Payment id is missing. Send ?id=... or JSON body {id:'...'}")
    try:
        oid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payment id format. Expected a Mongo ObjectId string.")
    res = await payment_collection.find_one_and_delete({"_id": oid})
    if not res:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"message": "Payment deleted", "deletedItem": fix_objectids(res)}

# --------------------
# Orders / my-orders / admin listing
# --------------------
@app.post("/orders", status_code=201)
async def add_order(order: OrderModel):
    try:
        order_dict = order.dict()
        order_dict["created_at"] = datetime.utcnow()
        order_dict["order_ref_id"] = generate_order_ref_id()
        # store address if provided in top-level fields (optional)
        order_dict["address"] = {
            "street": order_dict.get("street"),
            "village": order_dict.get("village"),
            "pincode": order_dict.get("pincode"),
            "city": order_dict.get("city"),
            "state": order_dict.get("state")
        }
        result = await orders_collection.insert_one(order_dict)
        return {**order_dict, "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/my-orders", response_class=HTMLResponse)
async def my_orders_page():
    with open("myorders.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

def format_user_address(user):
    if "street" in user:
        return ", ".join(filter(None, [
            user.get("street"),
            user.get("village"),
            user.get("city"),
            user.get("state"),
            str(user.get("pincode", ""))
        ]))
    elif "addresses" in user and user["addresses"]:
        addr = user["addresses"][0]
        return ", ".join(filter(None, [
            addr.get("street"),
            addr.get("village"),
            addr.get("city"),
            addr.get("state"),
            str(addr.get("pincode", ""))
        ]))
    return None

@app.get("/user-info/{pisa_code}")
async def get_user_info(pisa_code: str):
    user = await orders_collection.find_one({"$or": [{"pisa_code": pisa_code}, {"user_code": pisa_code}]})
    if not user:
        raise HTTPException(status_code=404, detail="We couldn't find your account. Please check your PISA Code.")
    name = user.get("name")
    if not name and "addresses" in user and user["addresses"]:
        name = user["addresses"][0].get("name")
    address = format_user_address(user)
    return {"name": name or "Customer", "address": address or "Address not available"}

@app.get("/my-orders/{pisa_code}")
async def get_my_orders(pisa_code: str):
    user = await orders_collection.find_one({"$or": [{"pisa_code": pisa_code}, {"user_code": pisa_code}]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please check your PISA Code.")
    orders = []
    async for order in orders_collection.find({"$or": [{"pisa_code": pisa_code}, {"user_code": pisa_code}]}):
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
    orders.sort(key=lambda x: x["order_date"], reverse=True)
    address_parts = []
    if all(field in user for field in ["street", "city", "state", "pincode"]):
        address_parts.extend([user.get("street", ""), user.get("village", ""), user.get("city", ""), user.get("state", ""), str(user.get("pincode", ""))])
    elif "addresses" in user and user["addresses"]:
        address = user["addresses"][0]
        address_parts.extend([address.get("street", ""), address.get("village", ""), address.get("city", ""), address.get("state", ""), str(address.get("pincode", ""))])
    return {"name": user.get("name", "Customer"), "address": ", ".join(filter(None, address_parts)) or "Address not available", "orders": orders}

@app.get("/orders")
async def get_orders():
    orders = []
    async for doc in orders_collection.find():
        if "address" in doc:
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
    orders.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
    return orders

# --------------------
# Keep uvicorn debug run for standalone
# --------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)