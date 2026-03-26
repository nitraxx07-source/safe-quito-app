import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app)

# Obtener la URL de Supabase desde las variables de Render
DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/')
def home():
    return "Servidor SafeQuito: Funcionando 🚀", 200

@app.route('/api/v1/reportar', methods=['POST', 'OPTIONS'])
@cross_origin()
def reportar():
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200
    
    datos = request.json
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        
        # Crear la tabla por si acaso no existe aún
        cursor.execute('''CREATE TABLE IF NOT EXISTS reportes 
                          (id SERIAL PRIMARY KEY, 
                           cedula_vecino TEXT, 
                           gps TEXT, 
                           direccion TEXT, 
                           fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Insertar el reporte
        cursor.execute("INSERT INTO reportes (cedula_vecino, gps, direccion) VALUES (%s, %s, %s)",
                       (datos.get('cedula_vecino', '1700000000'), 
                        datos.get('gps', '0,0'), 
                        datos.get('direccion', 'Reporte Móvil')))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": "Alerta guardada"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
