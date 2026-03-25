import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN DE BASE DE DATOS ---
DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar_db():
    # Conexión segura a PostgreSQL (Supabase)
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def iniciar_db():
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        # Crear la tabla de reportes si no existe
        cursor.execute('''CREATE TABLE IF NOT EXISTS reportes 
                          (id SERIAL PRIMARY KEY, 
                           cedula_vecino TEXT, 
                           gps TEXT, 
                           direccion TEXT, 
                           fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Base de datos sincronizada con Supabase")
    except Exception as e:
        print(f"❌ Error al sincronizar DB: {e}")

# Iniciar tablas al arrancar el servidor
if DATABASE_URL:
    iniciar_db()

@app.route('/')
def home():
    return "Servidor SafeQuito: Activo y Conectado a Supabase 🚀", 200

@app.route('/api/v1/reportar', methods=['POST', 'OPTIONS'])
@cross_origin()
def reportar():
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200
    
    datos = request.json
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO reportes (cedula_vecino, gps, direccion) VALUES (%s, %s, %s)",
                       (datos.get('cedula_vecino', '1700000000'), 
                        datos.get('gps', '0,0'), 
                        datos.get('direccion', 'Sin dirección')))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": "Alerta guardada en Supabase"}), 200
    except Exception as e:
        print(f"Error en reporte: {e}")
        return jsonify({"error": "No se pudo guardar el reporte"}), 500

if __name__ == "__main__":
    # Render usa el puerto 10000 por defecto
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
