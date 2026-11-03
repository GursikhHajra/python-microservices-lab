import os
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

PRODUCT_SERVICE_URL = "http://product-service:8001"
CUSTOMER_SERVICE_URL = "http://customer-service:8003"

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/orderdb"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, nullable=False)
    customer_name = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)


class OrderRequest(BaseModel):
    customer_id: int
    product_id: int
    quantity: int


def to_dict(o: Order):
    return {
        "order_id": o.id,
        "customer_id": o.customer_id,
        "customer_name": o.customer_name,
        "product_id": o.product_id,
        "product_name": o.product_name,
        "quantity": o.quantity,
        "unit_price": o.unit_price,
        "total_price": o.total_price,
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Order Service", lifespan=lifespan)


def fetch(url: str, not_found_msg: str, service_name: str):
    """GET a resource from another service, mapping errors to HTTP codes."""
    try:
        response = requests.get(url, timeout=5)
    except requests.RequestException:
        raise HTTPException(status_code=503, detail=f"{service_name} is unavailable")

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=not_found_msg)
    if not response.ok:
        raise HTTPException(status_code=503, detail=f"{service_name} is unavailable")
    return response.json()


@app.get("/")
def home():
    return {"message": "Welcome to Order Service"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "order-service"}


@app.post("/orders")
def create_order(order: OrderRequest, db: Session = Depends(get_db)):
    customer = fetch(
        f"{CUSTOMER_SERVICE_URL}/customers/{order.customer_id}",
        "Customer not found",
        "Customer Service",
    )
    product = fetch(
        f"{PRODUCT_SERVICE_URL}/products/{order.product_id}",
        "Product not found",
        "Product Service",
    )

    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

    if order.quantity > product["stock"]:
        raise HTTPException(status_code=400, detail="Insufficient product stock")

    new_order = Order(
        customer_id=customer["id"],
        customer_name=customer["name"],
        product_id=product["id"],
        product_name=product["name"],
        quantity=order.quantity,
        unit_price=product["price"],
        total_price=product["price"] * order.quantity,
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return {"message": "Order created successfully", "order": to_dict(new_order)}


@app.get("/orders")
def get_orders(db: Session = Depends(get_db)):
    return [to_dict(o) for o in db.query(Order).order_by(Order.id).all()]