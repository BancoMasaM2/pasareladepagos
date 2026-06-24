import os
import smtplib
import random
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
 
import psycopg2
import psycopg2.extras
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
 
psycopg2.extras.register_default_jsonb(loads=lambda x: x)
load_dotenv()
 
app = Flask(__name__)
 
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "billetera_virtual"),
    "user": os.getenv("DB_USER", "user"),
    "password": os.getenv("DB_PASSWORD", "password"),
}
 
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
BCRA_API_URL = os.getenv(
    "BCRA_API_URL", "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones"
)
 
# Tiempo de validez del código de autorización (en minutos)
OTP_EXPIRACION_MINUTOS = 10
 
 
def get_db():
    return psycopg2.connect(**DB_CONFIG)
 
 
def enviar_correo(destinatario: str, asunto: str, cuerpo: str):
    msg = MIMEText(cuerpo, "html")
    msg["Subject"] = asunto
    msg["From"] = SMTP_USER
    msg["To"] = destinatario
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
 
 
def generar_codigo_otp() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(6))
 
 
def obtener_email_usuario(alias: str) -> str | None:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.email FROM usuarios u
                JOIN cuentas c ON c.usuario_id = u.id
                WHERE c.alias = %s
            """,
                (alias,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()
 
 
def obtener_cotizacion_dolar() -> dict:
    """
    Consulta la API del BCRA y devuelve la cotización oficial USD/ARS.
    """
    try:
        resp = requests.get(BCRA_API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for cotizacion in data.get("results", []):
            if cotizacion.get("codigoMoneda") == "USD":
                return {
                    "moneda_base": "USD",
                    "moneda_destino": "ARS",
                    "cotizacion_oficial": float(cotizacion.get("cotizacion", 0)),
                    "fecha_actualizacion": datetime.now(timezone.utc).isoformat(),
                }
    except Exception:
        pass
    return {
        "moneda_base": "USD",
        "moneda_destino": "ARS",
        "cotizacion_oficial": 0.0,
        "fecha_actualizacion": datetime.now(timezone.utc).isoformat(),
    }
 
 
# -----------------------------------------------------------------
# NUEVO: conversión entre ARS y USD usando la cotización del BCRA
# -----------------------------------------------------------------
@app.route("/api/rates/convert", methods=["POST"])
def convertir_moneda():
    """
    Convierte un monto entre ARS y USD usando la cotización oficial del BCRA.
 
    JSON esperado desde el frontend:
    {
        "monto": 1000,
        "moneda_origen": "ARS",   // o "USD"
        "moneda_destino": "USD"   // o "ARS"
    }
 
    Respuesta:
    {
        "success": true,
        "monto_original": 1000,
        "moneda_origen": "ARS",
        "monto_convertido": 0.83,
        "moneda_destino": "USD",
        "cotizacion_usada": 1205.50,
        "fecha_actualizacion": "..."
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"mensaje": "Datos inválidos", "success": False}), 400
 
    monto = data.get("monto")
    moneda_origen = str(data.get("moneda_origen", "")).upper()
    moneda_destino = str(data.get("moneda_destino", "")).upper()
 
    if monto is None or moneda_origen not in ("ARS", "USD") or moneda_destino not in ("ARS", "USD"):
        return jsonify(
            {"mensaje": "Debe indicar monto, moneda_origen y moneda_destino (ARS o USD)", "success": False}
        ), 400
 
    if moneda_origen == moneda_destino:
        return jsonify(
            {"mensaje": "moneda_origen y moneda_destino no pueden ser iguales", "success": False}
        ), 400
 
    try:
        monto_decimal = Decimal(str(monto))
    except Exception:
        return jsonify({"mensaje": "Monto inválido", "success": False}), 400
 
    cotizacion = obtener_cotizacion_dolar()
    valor_usd = cotizacion["cotizacion_oficial"]
 
    if valor_usd <= 0:
        return jsonify(
            {"mensaje": "No se pudo obtener la cotización del BCRA en este momento", "success": False}
        ), 503
 
    valor_usd_decimal = Decimal(str(valor_usd))
 
    if moneda_origen == "ARS" and moneda_destino == "USD":
        monto_convertido = monto_decimal / valor_usd_decimal
    else:  # USD -> ARS
        monto_convertido = monto_decimal * valor_usd_decimal
 
    return jsonify(
        {
            "success": True,
            "monto_original": float(monto_decimal),
            "moneda_origen": moneda_origen,
            "monto_convertido": round(float(monto_convertido), 2),
            "moneda_destino": moneda_destino,
            "cotizacion_usada": valor_usd,
            "fecha_actualizacion": cotizacion["fecha_actualizacion"],
        }
    )
 
 
@app.route("/api/rates/usd", methods=["GET"])
def get_usd_rate():
    return jsonify(obtener_cotizacion_dolar())
 
 
@app.route("/api/payments/transferir/iniciar", methods=["POST"])
def iniciar_transferencia():
    data = request.get_json()
    if not data:
        return jsonify({"mensaje": "Datos inválidos", "success": False}), 400
 
    email_remitente = data.get("email_remitente", "")
    cuenta_origen_moneda = data.get("cuenta_origen", "")
    alias_destino = data.get("alias_destino", "")
    monto = data.get("monto")
 
    if not all([email_remitente, cuenta_origen_moneda, alias_destino, monto]):
        return jsonify({"mensaje": "Faltan datos requeridos", "success": False}), 400
 
    monto_decimal = Decimal(str(monto))
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cuentas WHERE alias = %s", (alias_destino,))
            destino = cur.fetchone()
            if not destino:
                return jsonify(
                    {"mensaje": "Cuenta destino no encontrada", "success": False}
                ), 404
 
            cur.execute(
                """
                SELECT c.id, c.saldo FROM cuentas c
                JOIN usuarios u ON u.id = c.usuario_id
                WHERE u.email = %s AND c.moneda = %s
            """,
                (email_remitente, cuenta_origen_moneda.upper()),
            )
            origen = cur.fetchone()
            if not origen:
                return jsonify(
                    {"mensaje": "Cuenta origen no encontrada", "success": False}
                ), 404
 
            if Decimal(str(origen[1])) < monto_decimal:
                return jsonify({"mensaje": "Saldo insuficiente", "success": False}), 400
 
            codigo = generar_codigo_otp()
            tx_id = str(uuid.uuid4())
            now = datetime.now()
            # NUEVO: momento exacto en que el código deja de ser válido
            expira_en = now + timedelta(minutes=OTP_EXPIRACION_MINUTOS)
 
            cur.execute(
                """
                INSERT INTO movimientos (id, cuenta_origen_id, cuenta_destino_id, monto,
                    tipo_movimiento, estado_movimiento, fecha_creacion, codigo_autorizacion,
                    codigo_expira_en, descripcion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    tx_id,
                    origen[0],
                    destino[0],
                    str(monto_decimal),
                    "TRANSFERENCIA",
                    "PENDIENTE_AUTORIZACION",
                    now,
                    codigo,
                    expira_en,
                    f"Transferencia de ${monto_decimal} a {alias_destino}",
                ),
            )
            conn.commit()
 
            try:
                enviar_correo(
                    email_remitente,
                    "Autorización de Transferencia - Billetera Virtual",
                    f"""
                    <h2>Billetera Virtual</h2>
                    <p>Se ha solicitado una transferencia de <strong>${monto_decimal}</strong>
                    a la cuenta <strong>{alias_destino}</strong>.</p>
                    <p>Tu código de autorización es:</p>
                    <h1 style="letter-spacing:8px;font-size:32px;">{codigo}</h1>
                    <p>Este código vence en <strong>{OTP_EXPIRACION_MINUTOS} minutos</strong>.</p>
                    <p>Si no solicitaste esta transferencia, ignora este mensaje.</p>
                    """,
                )
            except Exception:
                pass
 
            return jsonify(
                {
                    "mensaje": "Transferencia iniciada. Revisa tu correo para autorizar.",
                    "success": True,
                    "id_transaccion": tx_id,
                    "codigo_expira_en_minutos": OTP_EXPIRACION_MINUTOS,
                }
            ), 202
    finally:
        conn.close()
 
 
@app.route("/api/payments/transferir/confirmar", methods=["POST"])
def confirmar_transferencia():
    data = request.get_json()
    if not data:
        return jsonify({"mensaje": "Datos inválidos", "success": False}), 400
 
    tx_id = data.get("id_transaccion", "")
    codigo = data.get("codigo_autorizacion", "")
 
    if not tx_id or not codigo or len(codigo) != 6:
        return jsonify({"mensaje": "Datos inválidos", "success": False}), 400
 
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, cuenta_origen_id, cuenta_destino_id, monto, estado_movimiento,
                    codigo_autorizacion, codigo_expira_en
                FROM movimientos WHERE id = %s FOR UPDATE
            """,
                (tx_id,),
            )
            mov = cur.fetchone()
            if not mov:
                return jsonify(
                    {"mensaje": "Transacción no encontrada", "success": False}
                ), 404
 
            if mov[4] != "PENDIENTE_AUTORIZACION":
                return jsonify(
                    {"mensaje": "La transacción ya fue procesada", "success": False}
                ), 400
 
            # NUEVO: chequeo de expiración antes de validar el código
            expira_en = mov[6]
            if expira_en is not None and datetime.now() > expira_en:
                cur.execute(
                    """
                    UPDATE movimientos SET estado_movimiento = 'EXPIRADO'
                    WHERE id = %s
                """,
                    (tx_id,),
                )
                conn.commit()
                return jsonify(
                    {"mensaje": "El código de autorización expiró. Solicitá una nueva transferencia.", "success": False}
                ), 400
 
            if mov[5] != codigo:
                return jsonify(
                    {"mensaje": "Código de autorización inválido", "success": False}
                ), 400
 
            monto = Decimal(str(mov[3]))
            now = datetime.now()
 
            cur.execute("SELECT saldo FROM cuentas WHERE id = %s FOR UPDATE", (mov[1],))
            saldo_origen = Decimal(str(cur.fetchone()[0]))
            if saldo_origen < monto:
                cur.execute(
                    """
                    UPDATE movimientos SET estado_movimiento = 'FALLIDO',
                    fecha_autorizacion = %s WHERE id = %s
                """,
                    (now, tx_id),
                )
                conn.commit()
                return jsonify({"mensaje": "Saldo insuficiente", "success": False}), 400
 
            cur.execute(
                "UPDATE cuentas SET saldo = saldo - %s WHERE id = %s",
                (str(monto), mov[1]),
            )
            cur.execute(
                "UPDATE cuentas SET saldo = saldo + %s WHERE id = %s",
                (str(monto), mov[2]),
            )
            cur.execute(
                """
                UPDATE movimientos SET estado_movimiento = 'COMPLETADO',
                fecha_autorizacion = %s, codigo_autorizacion = %s WHERE id = %s
            """,
                (now, codigo, tx_id),
            )
            conn.commit()
 
            return jsonify(
                {
                    "mensaje": "Transferencia confirmada exitosamente",
                    "success": True,
                    "id_transaccion": tx_id,
                }
            )
    finally:
        conn.close()
 
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
 