import httpx

DOLARAPI_URL = "https://dolarapi.com/v1/dolares/{tipo}"

TASAS = {
    "oficial": {"compra": 1000.0, "venta": 1020.0},
    "blue": {"compra": 1200.0, "venta": 1220.0},
}


async def obtener_cotizacion(tipo: str = "blue") -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(DOLARAPI_URL.format(tipo=tipo))
            resp.raise_for_status()
            data = resp.json()
            return {
                "tipo": tipo,
                "compra": data.get("compra"),
                "venta": data.get("venta"),
                "fecha": data.get("fechaActualizacion"),
                "fuente": "dolarapi.com",
            }
    except Exception:
        fallback = TASAS.get(tipo, TASAS["blue"])
        return {
            "tipo": tipo,
            "compra": fallback["compra"],
            "venta": fallback["venta"],
            "fecha": None,
            "fuente": "fallback",
        }
