from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests

router = APIRouter()

INSTAMOJO_API_URL = "https://www.instamojo.com/api/1.1/payment-requests/"
API_KEY = "your_api_key"
AUTH_TOKEN = "your_auth_token"

class PaymentRequest(BaseModel):
    purpose: str
    amount: float
    buyer_name: str
    email: str
    phone: str
    redirect_url: str

@router.post("/create_payment")
def create_payment(payment: PaymentRequest):
    payload = {
        "purpose": payment.purpose,
        "amount": payment.amount,
        "buyer_name": payment.buyer_name,
        "email": payment.email,
        "phone": payment.phone,
        "redirect_url": payment.redirect_url,
        "send_email": True,
        "send_sms": True,
        "allow_repeated_payments": False,
    }

    headers = {
        "X-Api-Key": API_KEY,
        "X-Auth-Token": AUTH_TOKEN,
    }

    response = requests.post(INSTAMOJO_API_URL, data=payload, headers=headers)
    if response.status_code != 201:
        raise HTTPException(status_code=500, detail="Payment creation failed")

    response_data = response.json()
    payment_url = response_data.get("payment_request", {}).get("longurl")
    if not payment_url:
        raise HTTPException(status_code=500, detail="Payment URL not found")

    return {"payment_url": payment_url}
