import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/productdb"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=False)


def to_dict(p: Product):
    return {"id": p.id, "name": p.name, "price": p.price, "stock": p.stock}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    # Seed sample products only if the table is empty
    with SessionLocal() as db:
        if db.query(Product).count() == 0:
            db.add_all([
                Product(name="Laptop", price=1200, stock=10),
                Product(name="Keyboard", price=50, stock=25),
                Product(name="Mouse", price=30, stock=40),
                Product(name="Monitor", price=300, stock=15),
            ])
            db.commit()
    yield


app = FastAPI(title="Product Service", lifespan=lifespan)


@app.get("/")
def home():
    return {"message": "Welcome to Product Service"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "product-service"}


@app.get("/products")
def get_products(db: Session = Depends(get_db)):
    return [to_dict(p) for p in db.query(Product).order_by(Product.id).all()]


@app.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return to_dict(product)