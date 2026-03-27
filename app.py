from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# 1. RUTA PARA REGISTRAR VECINOS
@app.route('/api/v1/registrar', methods=['POST'])
def registrar():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usuarios (cedula, nombres, apellidos, correo, celular, password) VALUES (%s, %s, %s, %s, %s, %s)",
            (data['cedula'], data['nombres'], data['apellidos'], data['correo'], data['celular'], data['password'])
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "msj": "Registro exitoso"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 400

# 2. RUTA PARA INICIO DE SESIÓN
@app.route('/api/v1/login', methods=['POST'])
def login():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT nombres FROM usuarios WHERE cedula = %s AND password = %s", 
                    (data['cedula'], data['password']))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return jsonify({"status": "ok", "nombre": user[0]}), 200
        else:
            return jsonify({"status": "error", "msj": "Cédula o clave incorrecta"}), 401
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 3. RUTA PARA REPORTAR ALERTAS
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
        return jsonify({"status": "error", "msj": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
