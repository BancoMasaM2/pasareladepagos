import httpx
import os
from payment_gateway.providers.cotizacion_api import obtener_cotizacion

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8001")


async def ejecutar_conversion(
    usuario_id: int,
    monto: float,
    desde: str,
    hacia: str,
) -> dict:
    cotizacion = await obtener_cotizacion("blue")
    if desde == "ARS" and hacia == "USD":
        tasa = cotizacion["venta"]
        monto_destino = round(monto / tasa, 2)
    elif desde == "USD" and hacia == "ARS":
        tasa = cotizacion["compra"]
        monto_destino = round(monto * tasa, 2)
    else:
        raise ValueError("Par de monedas no soportado")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/operaciones/conversion",
            json={
                "usuario_id": usuario_id,
                "monto_origen": monto,
                "moneda_origen": desde,
                "monto_destino": monto_destino,
                "moneda_destino": hacia,
                "tasa": tasa,
            },
        )
        resp.raise_for_status()
        return {
            "monto_origen": monto,
            "moneda_origen": desde,
            "monto_destino": monto_destino,
            "moneda_destino": hacia,
            "tasa": tasa,
            "resultado": resp.json(),
        }
