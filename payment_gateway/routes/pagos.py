from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from payment_gateway.services.pago_service import ejecutar_pago

router = APIRouter(prefix="/payments", tags=["pagos"])


class PagoRequest(BaseModel):
    usuario_id: int
    monto: float
    descripcion: str = ""


@router.post("/pagos")
async def pagar(req: PagoRequest):
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser positivo")
    try:
        resultado = await ejecutar_pago(req.usuario_id, req.monto, req.descripcion)
        return {"estado": "completada", "detalle": resultado}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
