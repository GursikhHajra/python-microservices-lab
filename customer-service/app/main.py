import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/customerdb"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)


class CustomerRequest(BaseModel):
    name: str
    email: str


def to_dict(c: Customer):
    return {"id": c.id, "name": c.name, "email": c.email}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    # Seed sample customers only if the table is empty
    with SessionLocal() as db:
        if db.query(Customer).count() == 0:
            db.add_all([
                Customer(name="Alice Johnson", email="alice@example.com"),
                Customer(name="Bob Smith", email="bob@example.com"),
            ])
            db.commit()
    yield


app = FastAPI(title="Customer Service", lifespan=lifespan)


@app.get("/")
def home():
    return {"message": "Welcome to Customer Service"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "customer-service"}


@app.get("/customers")
def get_customers(db: Session = Depends(get_db)):
    return [to_dict(c) for c in db.query(Customer).order_by(Customer.id).all()]


@app.get("/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return to_dict(customer)


@app.post("/customers")
def create_customer(customer: CustomerRequest, db: Session = Depends(get_db)):
    new_customer = Customer(name=customer.name, email=customer.email)
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return {
        "message": "Customer registered successfully",
        "customer": to_dict(new_customer),
    }