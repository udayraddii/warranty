from fastapi import FastAPI
from database import execute_query

app = FastAPI(
    title="Warranty Claims POC"
)

@app.get("/")
def home():
    return {
        "message": "Warranty Claim Intelligence API Running"
    }


@app.get("/products")
def get_products():
    sql = """
    SELECT *
    FROM PRODUCTS
    """
    return execute_query(sql)


@app.get("/suppliers")
def get_suppliers():
    sql = """
    SELECT *
    FROM SUPPLIERS
    """
    return execute_query(sql)

@app.get("/claims")

def get_claims():
    query = "SELECT * FROM WARRANTY_CLAIMS"
    return execute_query(query)