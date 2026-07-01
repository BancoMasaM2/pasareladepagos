import httpx
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


async def ejecutar_transferencia(
    origen_usuario_id: int,
    destino_usuario_id: int,
    moneda: str,
    monto: float,
) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/operaciones/transferir",
            json={
                "origen_usuario_id": origen_usuario_id,
                "destino_usuario_id": destino_usuario_id,
                "moneda": moneda,
                "monto": monto,
            },
        )
        resp.raise_for_status()
        return resp.json()
