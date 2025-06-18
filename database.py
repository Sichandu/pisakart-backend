from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["pisakart"]
orders_collection = db["orders"]
