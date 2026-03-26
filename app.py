import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar_db():
    # Añadimos un tiempo de espera (timeout) para que no se rinda rápido
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

@app.route('/')
def home():
    return "Servidor SafeQuito: ¡Conexión Estable! 🛡️", 200

@app.route('/api/v1/reportar', methods=['POST', 'OPTIONS'])
@cross_origin()
def reportar():
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200
    
    datos = request.json
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS reportes 
                          (id SERIAL PRIMARY KEY, 
                           cedula_vecino TEXT, 
                           gps TEXT, 
                           direccion TEXT, 
                           fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute("INSERT INTO reportes (cedula_vecino, gps, direccion) VALUES (%s, %s, %s)",
                       (datos.get('cedula_vecino', '1700000000'), 
                        datos.get('gps', '0,0'), 
                        datos.get('direccion', 'Reporte Móvil')))
        
        conn.commit()
        cursor.close()
        return jsonify({"mensaje": "Alerta guardada en Supabase"}), 200
    except Exception as e:
        print(f"Error de conexión: {e}")
        return jsonify({"error": "Error de conexión a la base de datos"}), 500
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
