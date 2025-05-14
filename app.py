from flask import Flask, request, jsonify
import openai
import os

app = Flask(__name__)

# Configura tu clave de OpenAI aquí (usa variables de entorno en producción)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.form
    user_message = data.get("Body")
    user_number = data.get("From")

    # Llamar al GPT para obtener respuesta
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres el asistente comercial de Eshkol Premium, especializado en tomar y rastrear pedidos de productos frescos."},
                {"role": "user", "content": user_message}
            ]
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = "Hubo un error procesando tu mensaje. Intentaremos nuevamente."

    # Respuesta para Twilio
    twilio_response = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{reply}</Message></Response>"
    return twilio_response, 200, {'Content-Type': 'application/xml'}

@app.route("/", methods=["GET"])
def home():
    return "Servidor Flask para Eshkol Premium activo."

if __name__ == "__main__":
    app.run(debug=True)
