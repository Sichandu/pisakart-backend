from pydantic import BaseModel, Field
from typing import Optional

class Order(BaseModel):
    name: str
    phonenumber: str
    street: str
    village: str
    pincode: str
    city: str
    state: str
    amount: Optional[int] = Field(default=1)