import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Permitimos CORS para que tu GitHub Pages pueda enviar datos aquí
CORS(app)

def get_db_connection():
    # Usamos las 5 variables que configuraste en Render
    # Añadimos 'options' para forzar al Pooler a encontrar tu proyecto
    return psycopg2.connect(
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT'),
        database=os.environ.get('DB_NAME'),
        sslmode='require',
        options="-c search_path=public"
    )

@app.route('/')
def home():
    return "Servidor SafeQuito: ¡Sistema de Seguridad Activo! 🛡️", 200

@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    datos = request.json
    # Si no llegan datos, evitamos que el servidor se caiga
    if not datos:
        return jsonify({"error": "No se recibieron datos"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Doble seguridad: Crea la tabla si por alguna razón no existe
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reportes (
                id SERIAL PRIMARY KEY,
                cedula_vecino TEXT,
                gps TEXT,
                direccion TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insertamos la alerta del vecino
        cursor.execute(
            "INSERT INTO reportes (cedula_vecino, gps, direccion) VALUES (%s, %s, %s)",
            (datos.get('cedula_vecino', 'Anónimo'), 
             datos.get('gps', '0,0'), 
             datos.get('direccion', 'Ubicación desconocida'))
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Alerta guardada con éxito en Supabase")
        return jsonify({"mensaje": "¡Alerta enviada correctamente al centro de monitoreo!"}), 200

    except Exception as e:
        print(f"❌ Error crítico de conexión: {e}")
        return jsonify({"error": "Error al conectar con la base de datos", "detalle": str(e)}), 500

if __name__ == "__main__":
    # Render usa el puerto 10000 por defecto
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
