import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Servidor SafeQuito: ¡Último intento de conexión! 🛡️", 200

@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    datos = request.json
    try:
        # Conexión usando el link directo de la variable DATABASE_URL
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO reportes (cedula_vecino, gps, direccion) VALUES (%s, %s, %s)",
                       (datos.get('cedula_vecino'), datos.get('gps'), datos.get('direccion')))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": "¡ÉXITO! Alerta guardada."}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
