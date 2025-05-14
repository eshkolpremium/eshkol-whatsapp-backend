from flask import Flask, request
from openai import OpenAI
import os
import json
import re

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

productos = [
    "albahaca", "menta", "tomillo", "romero", "oregano", "estragon",
    "eneldo", "cebollín", "laurel", "perejil", "cilantro", "culantro"
]

keywords_retail = ["clamshell", "supermercado", "retail", "presentación pequeña"]
PEDIDOS_FILE = "pedidos.json"
consecutivo = 50468
ordenes_temporales = {}

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    global consecutivo

    data = request.form
    user_message = data.get("Body", "").lower()
    user_number = data.get("From")

    def guardar_pedido_final(datos):
        global consecutivo
        consecutivo += 1
        pedido = {
            "consecutivo": consecutivo,
            "numero": user_number,
            "datos": datos
        }
        if os.path.exists(PEDIDOS_FILE):
            with open(PEDIDOS_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {"ultimo_consecutivo": 50468, "pedidos": []}
        data["ultimo_consecutivo"] = consecutivo
        data["pedidos"].append(pedido)
        with open(PEDIDOS_FILE, "w") as f:
            json.dump(data, f, indent=2)

        # Aquí se puede insertar integración con Google Sheets
        print(f"Pedido confirmado #{consecutivo} para hoja de cálculo: {pedido}")

    try:
        productos_pedidos = []
        for producto in productos:
            match = re.search(rf"(\\d+\\s*(libras|libra|kg|kilo|kilos)?\\s*de\\s+)?{producto}", user_message)
            if match:
                cantidad = match.group(1).strip() if match.group(1) else "una unidad"
                productos_pedidos.append(f"{cantidad} de {producto}")

        if productos_pedidos:
            productos_lista = ", ".join(productos_pedidos)
            ordenes_temporales[user_number] = {"productos": productos_lista}
            reply = (
                f"Perfecto, anoté {productos_lista}. ¿Deseas agregar algo más o confirmar tu pedido?\n"
                f"Responde con: CONFIRMAR o AGREGAR."
            )

        elif "confirmar" in user_message and user_number in ordenes_temporales:
            reply = (
                "Por favor confírmame estos datos para finalizar tu pedido:\n"
                "- Nombre del cliente\n"
                "- Número de pre-orden\n"
                "- Fecha de entrega\n"
                "- Hora estimada de entrega\n"
                "- Ciudad de destino (si aplica)"
            )

        elif all(k in user_message for k in ["nombre", "pre-orden", "fecha", "hora"]):
            datos = ordenes_temporales.get(user_number, {})
            datos.update({"detalles": user_message})
            if any(ciudad in user_message for ciudad in [
                "miami", "new york", "atlanta", "los angeles", "houston", "dallas", "chicago"
            ]):
                reply = (
                    "¿Deseas enviar el pedido por vía aérea o terrestre?\n"
                    "Indícanos también la aerolínea o transportadora y la ciudad destino."
                )
                ordenes_temporales[user_number] = datos
            else:
                guardar_pedido_final(datos)
                ordenes_temporales.pop(user_number, None)
                reply = f"Tu pedido ha sido confirmado con el consecutivo #{consecutivo}. ¡Gracias por tu orden!"

        elif any(modo in user_message for modo in ["aérea", "terrestre"]):
            datos = ordenes_temporales.get(user_number, {})
            datos["envio"] = user_message
            guardar_pedido_final(datos)
            ordenes_temporales.pop(user_number, None)
            reply = f"Tu pedido ha sido confirmado con el consecutivo #{consecutivo}. ¡Gracias por tu orden!"

        else:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres el asistente comercial de Eshkol Premium. Si detectas que el usuario escribe varios productos juntos, extrae y agrúpalos. Si el cliente confirma, pide nombre, pre-orden, fecha y hora de entrega. Si detectas una ciudad de EE.UU., pregunta si desea envío aéreo o terrestre y qué empresa usará."
                    },
                    {"role": "user", "content": user_message}
                ]
            )
            reply = response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error GPT (nuevo SDK): {e}")
        reply = "Hubo un error procesando tu mensaje. Intentaremos nuevamente."

    twilio_response = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{reply}</Message></Response>"
    return twilio_response, 200, {'Content-Type': 'application/xml'}

@app.route("/", methods=["GET"])
def home():
    return "Servidor Flask para Eshkol Premium activo (confirmación avanzada)."

if __name__ == "__main__":
    app.run(debug=True)
