from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from payment_gateway.services.conversion_service import ejecutar_conversion
from payment_gateway.providers.cotizacion_api import obtener_cotizacion

router = APIRouter(prefix="/payments", tags=["conversiones"])


class ConversionRequest(BaseModel):
    usuario_id: int
    monto: float
    desde: str
    hacia: str


@router.post("/conversiones")
async def convertir(req: ConversionRequest):
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser positivo")
    if req.desde not in ("ARS", "USD") or req.hacia not in ("ARS", "USD"):
        raise HTTPException(status_code=400, detail="Moneda debe ser ARS o USD")
    if req.desde == req.hacia:
        raise HTTPException(status_code=400, detail="Las monedas deben ser distintas")
    try:
        resultado = await ejecutar_conversion(
            req.usuario_id, req.monto, req.desde, req.hacia
        )
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/cotizacion")
async def cotizacion(tipo: str = "blue"):
    data = await obtener_cotizacion(tipo)
    return data
