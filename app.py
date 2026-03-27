from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# Conexión a la base de datos desde variables de entorno
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/')
def home():
    return "Servidor de SafeQuito Operacional 🛡️", 200

# 1. REGISTRO SEGURO (CON HASH Y SALT AUTOMÁTICO)
@app.route('/api/v1/registrar', methods=['POST'])
def registrar():
    data = request.json
    # Generamos el hash con sal incorporada
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usuarios (cedula, nombres, apellidos, correo, celular, password) VALUES (%s, %s, %s, %s, %s, %s)",
            (data['cedula'], data['nombres'], data['apellidos'], data['correo'], data['celular'], hashed_password)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "msj": "Registro seguro completado"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": "La cédula o correo ya existen"}), 400

# 2. LOGIN CON VERIFICACIÓN DE SEGURIDAD
@app.route('/api/v1/login', methods=['POST'])
def login():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Buscamos al usuario por su cédula
        cur.execute("SELECT nombres, password FROM usuarios WHERE cedula = %s", (data['cedula'],))
        user = cur.fetchone()
        cur.close()
        conn.close()

        # check_password_hash se encarga de comparar la clave plana con el hash salteado
        if user and check_password_hash(user[1], data['password']):
            return jsonify({"status": "ok", "nombre": user[0]}), 200
        else:
            return jsonify({"status": "error", "msj": "Cédula o clave incorrecta"}), 401
    except Exception as e:
        return jsonify({"status": "error", "msj": "Error en el servidor"}), 500

# 3. REPORTES DE ALERTAS (BOTONES DE COLORES)
@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reportes_v2 (cedula_vecino, tipo_alerta, gps) VALUES (%s, %s, %s)",
            (data['cedula'], data['tipo'], data['gps'])
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "msj": "Alerta enviada"}), 200
    except Exception as e:
        return jsonify({"status": "error", "msj": "No se pudo enviar la alerta"}), 500

if __name__ == '__main__':
    # Render usa el puerto 10000 por defecto
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
