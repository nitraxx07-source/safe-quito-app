import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def get_db_connection():
    # Conexión robusta usando las variables individuales
    return psycopg2.connect(
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT'),
        database=os.environ.get('DB_NAME'),
        sslmode='require'
    )

@app.route('/')
def home():
    return "Servidor SafeQuito: ¡Conexión Estable! 🛡️", 200

@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    datos = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Crea la tabla si no existe (doble seguridad)
        cursor.execute('''CREATE TABLE IF NOT EXISTS reportes 
                          (id SERIAL PRIMARY KEY, cedula_vecino TEXT, gps TEXT, direccion TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute("INSERT INTO reportes (cedula_vecino, gps, direccion) VALUES (%s, %s, %s)",
                       (datos.get('cedula_vecino'), datos.get('gps'), datos.get('direccion')))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": "¡Alerta guardada exitosamente!"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
