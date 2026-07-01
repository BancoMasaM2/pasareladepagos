from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from payment_gateway.services.transferencia_service import ejecutar_transferencia

router = APIRouter(prefix="/payments", tags=["transferencias"])


class TransferenciaRequest(BaseModel):
    origen_usuario_id: int
    destino_usuario_id: int
    moneda: str
    monto: float


@router.post("/transferencias")
async def transferir(req: TransferenciaRequest):
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser positivo")
    if req.moneda not in ("ARS", "USD"):
        raise HTTPException(status_code=400, detail="Moneda debe ser ARS o USD")
    try:
        resultado = await ejecutar_transferencia(
            req.origen_usuario_id, req.destino_usuario_id, req.moneda, req.monto
        )
        return {"estado": "completada", "detalle": resultado}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
