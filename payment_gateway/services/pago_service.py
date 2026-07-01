import httpx
import os

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8001")


async def ejecutar_pago(
    usuario_id: int,
    monto: float,
    descripcion: str,
) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/operaciones/pago",
            json={
                "usuario_id": usuario_id,
                "monto": monto,
                "descripcion": descripcion,
            },
        )
        resp.raise_for_status()
        return resp.json()
