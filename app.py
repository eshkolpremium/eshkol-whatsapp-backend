from flask import Flask, request
from openai import OpenAI
import os
import json
import re
from datetime import datetime

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

productos = [
    "albahaca", "menta", "tomillo", "romero", "oregano", "estragon",
    "eneldo", "cebollín", "laurel", "perejil", "cilantro", "culantro"
]

presentaciones = ["kilo", "kilos", "libra", "libras", "media libra", "clamshell"]
PEDIDOS_FILE = "pedidos.json"
consecutivo = 50468
ordenes_temporales = {}
historial_pedidos = {}

empresas_direccion = {
    "goodness gardens": "377 County Route 12, New Hampton, NY 10958",
    "green sun one corp": "1475 NW 23rd St, Miami, FL 33142",
    "freshpoint florida": "2300 NW 19th St, Pompano Beach, FL 33069",
    "tropical sales of florida llc": "1305 W Dr Martin Luther King Jr Blvd Ste 7, Plant City, FL 33563",
    "harvest sensations": "8303 NW 27th St, Unit 11, Miami, FL 33122",
    "natural forest inc.": "2255 NW 110th Ave Ste 202, Miami, FL 33172",
    "coastal sunbelt produce": "9001 Whiskey Bottom Rd, Laurel, MD 20723",
    "produce experience": "601 Drake St, Bronx, NY 10474"
}

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    global consecutivo

    data = request.form
    user_message = data.get("Body", "").lower()
    user_number = data.get("From")

    def guardar_pedido_final(datos):
        global consecutivo
        consecutivo += 1
        codigo = f"SO-2025-{consecutivo:04d}"
        pedido = {
            "codigo": codigo,
            "numero": user_number,
            "datos": datos,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        historial_pedidos[user_number] = pedido
        if os.path.exists(PEDIDOS_FILE):
            with open(PEDIDOS_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {"ultimo_consecutivo": 50468, "pedidos": []}
        data["ultimo_consecutivo"] = consecutivo
        data["pedidos"].append(pedido)
        with open(PEDIDOS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return codigo

    try:
        if "repite" in user_message or "lo mismo" in user_message:
            ultimo = historial_pedidos.get(user_number)
            if ultimo:
                ordenes_temporales[user_number] = ultimo["datos"]
                reply = f"Repetí tu último pedido: {ultimo['datos']['productos']}\n¿Deseas confirmar o agregar algo más?"
            else:
                reply = "No encontré un pedido anterior para repetir."

        elif any(p in user_message for p in productos):
            productos_pedidos = []
            for producto in productos:
                pattern = rf"(\d+(\.\d+)?)(\s*(kilo|kilos|libra|libras|media libra|clamshell|clamshells))?\s+de\s+{producto}"
                matches = re.findall(pattern, user_message)
                for m in matches:
                    cantidad = m[0]
                    unidad = m[3] if m[3] else "unidad"
                    productos_pedidos.append(f"{cantidad} {unidad} de {producto}")

            if productos_pedidos:
                productos_lista = "\n- " + "\n- ".join(productos_pedidos)
                ordenes_temporales[user_number] = {"productos": productos_lista}
                reply = f"Tu pedido es:{productos_lista}\n¿Deseas confirmar este pedido o agregar más productos?"
            else:
                reply = "No entendí bien tu pedido. ¿Puedes escribir cantidades y productos como '2 kilos de cilantro'?"

        elif "confirmar" in user_message and user_number in ordenes_temporales:
            reply = (
                "Perfecto, ahora por favor indícame:\n"
                "- Nombre de la empresa\n- Fecha estimada de entrega\n- Número de pre-orden (si aplica)"
            )

        elif any(k in user_message for k in ["empresa", "fecha", "pre-orden"]):
            datos = ordenes_temporales.get(user_number, {})
            datos.update({"detalles": user_message})
            for nombre, direccion in empresas_direccion.items():
                if nombre in user_message:
                    datos["direccion"] = direccion
                    datos["empresa"] = nombre.title()
                    if "miami" not in direccion.lower():
                        reply = (
                            "¿El envío será aéreo o terrestre?\n"
                            "Indícanos también la aerolínea o transportadora."
                        )
                        ordenes_temporales[user_number] = datos
                        return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{reply}</Message></Response>", 200, {'Content-Type': 'application/xml'}
                    else:
                        codigo = guardar_pedido_final(datos)
                        ordenes_temporales.pop(user_number, None)
                        reply = f"✅ Pedido Confirmado - {codigo}\nProductos:{datos['productos']}\nGracias por tu orden."
                        return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{reply}</Message></Response>", 200, {'Content-Type': 'application/xml'}
            reply = "No identifiqué la empresa. Por favor verifica el nombre."

        elif "aérea" in user_message or "terrestre" in user_message:
            datos = ordenes_temporales.get(user_number, {})
            datos["envio"] = user_message
            codigo = guardar_pedido_final(datos)
            ordenes_temporales.pop(user_number, None)
            reply = f"✅ Pedido Confirmado - {codigo}\nProductos:{datos['productos']}\nGracias por tu orden."

        elif "último pedido" in user_message or "historial" in user_message:
            ultimo = historial_pedidos.get(user_number)
            if ultimo:
                reply = (
                    f"📅 Fecha: {ultimo['fecha']}\n"
                    f"📦 Productos:{ultimo['datos']['productos']}\n"
                    f"🔢 Código: {ultimo['codigo']}"
                )
            else:
                reply = "No encontré historial de pedidos para tu número."

        else:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres el asistente de pedidos de Eshkol Premium. Extrae productos y cantidades. Pregunta por nombre de empresa, fecha, pre-orden. Si detectas ciudad fuera de Miami, solicita tipo de envío."
                    },
                    {"role": "user", "content": user_message}
                ]
            )
            reply = response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error: {e}")
        reply = "Hubo un error procesando tu mensaje. Intentaremos nuevamente."

    twilio_response = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{reply}</Message></Response>"
    return twilio_response, 200, {'Content-Type': 'application/xml'}

@app.route("/", methods=["GET"])
def home():
    return "Servidor Flask para Eshkol Premium activo."

if __name__ == "__main__":
    app.run(debug=True)
