from flask import Flask, request
from openai import OpenAI
import os
import json

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Lista de productos y formatos
productos = [
    "albahaca", "menta", "tomillo", "romero", "oregano", "estragon",
    "eneldo", "cebollín", "laurel", "perejil", "cilantro", "culantro"
]

keywords_retail = ["clamshell", "supermercado", "retail", "presentación pequeña"]

# Archivo para almacenar pedidos
PEDIDOS_FILE = "pedidos.json"

def cargar_consecutivo():
    if os.path.exists(PEDIDOS_FILE):
        with open(PEDIDOS_FILE, "r") as f:
            data = json.load(f)
            return data.get("ultimo_consecutivo", 50468)
    return 50468

def guardar_pedido(consecutivo, numero, mensaje):
    if os.path.exists(PEDIDOS_FILE):
        with open(PEDIDOS_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {"ultimo_consecutivo": 50468, "pedidos": []}

    data["ultimo_consecutivo"] = consecutivo
    data["pedidos"].append({"consecutivo": consecutivo, "numero": numero, "mensaje": mensaje})

    with open(PEDIDOS_FILE, "w") as f:
        json.dump(data, f, indent=2)

consecutivo = cargar_consecutivo()

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    global consecutivo

    data = request.form
    user_message = data.get("Body", "").lower()
    user_number = data.get("From")

    try:
        producto_mencionado = next((p for p in productos if p in user_message), None)
        cliente_retail = any(k in user_message for k in keywords_retail)

        if "quiero hacer un pedido" in user_message or "realizar un pedido" in user_message:
            reply = (
                "¡Claro! Para procesar tu pedido, por favor confírmame los siguientes datos:\n"
                "- Nombre del cliente\n"
                "- Número de pre-orden\n"
                "- Fecha de entrega deseada\n"
                "- Nombre del comprador\n"
                "- Hora estimada de entrega"
            )

        elif all(kw in user_message for kw in ["nombre", "pre-orden", "fecha", "comprador", "hora"]):
            consecutivo += 1
            guardar_pedido(consecutivo, user_number, user_message)
            reply = f"¡Gracias! Tu orden ha sido confirmada con el consecutivo #{consecutivo}. Te notificaremos cualquier novedad."

        elif producto_mencionado:
            if cliente_retail:
                reply = f"¡Sí! Tenemos {producto_mencionado} en bolsas de 1 libra y también en presentación clamshell para supermercados. ¿Cuál prefieres?"
            else:
                reply = f"¡Sí! Tenemos {producto_mencionado} fresca en bolsas de 1 libra. ¿Te gustaría hacer un pedido?"
        else:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres el asistente comercial de Eshkol Premium, especializado en tomar y rastrear pedidos de productos frescos."},
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
    return "Servidor Flask para Eshkol Premium activo (personalizado)."

if __name__ == "__main__":
    app.run(debug=True)
