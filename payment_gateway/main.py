from fastapi import FastAPI
from payment_gateway.routes.transferencias import router as transferencias_router
from payment_gateway.routes.conversiones import router as conversiones_router
from payment_gateway.routes.pagos import router as pagos_router

app = FastAPI(title="Payment Gateway", version="1.0.0")

app.include_router(transferencias_router)
app.include_router(conversiones_router)
app.include_router(pagos_router)


@app.get("/payments/health")
def health():
    return {"status": "ok"}
