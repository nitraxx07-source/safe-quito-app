import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN DE BASE DE DATOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "alertas_quito.db")

def iniciar_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Tabla de Usuarios (Materia 1: Relaciones)
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                      (cedula TEXT PRIMARY KEY, nombre TEXT, apellido TEXT, 
                       email TEXT, clave_hash TEXT, estado TEXT)''')
    
    # Tabla de Reportes (Materia 1: Clave Foránea)
    cursor.execute('''CREATE TABLE IF NOT EXISTS reportes 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       cedula_vecino TEXT, gps TEXT, hora TEXT, direccion TEXT,
                       FOREIGN KEY(cedula_vecino) REFERENCES usuarios(cedula))''')
    conn.commit()
    conn.close()

# Ejecutar creación de tablas al arrancar
iniciar_db()

# --- MATERIA 2: LIMPIEZA Y VALIDACIÓN ---
def validar_cedula_ec(cedula):
    if not cedula.isdigit() or len(cedula) != 10: return False
    prov = int(cedula[:2])
    if not (1 <= prov <= 24): return False
    coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = sum([ (int(cedula[i])*coef[i] - 9 if int(cedula[i])*coef[i] >= 10 else int(cedula[i])*coef[i]) for i in range(9)])
    verificador = 10 - (suma % 10)
    if verificador == 10: verificador = 0
    return verificador == int(cedula[9])

# --- RUTAS DE LA API ---

@app.route('/')
def home():
    return "Servidor SafeQuito Operacional 24/7", 200

@app.route('/api/v1/registrar', methods=['POST', 'OPTIONS'])
@cross_origin()
def registrar():
    if request.method == 'OPTIONS': return jsonify({"ok": True}), 200
    datos = request.json
    cedula = datos.get('cedula')
    
    if not validar_cedula_ec(cedula):
        return jsonify({"error": "Cédula no válida"}), 400

    hash_clave = generate_password_hash(datos.get('clave'))
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (cedula, nombre, apellido, email, clave_hash, estado) VALUES (?,?,?,?,?,?)",
                       (cedula, datos.get('nombre'), datos.get('apellido'), datos.get('email'), hash_clave, 'ACTIVO'))
        conn.commit()
        conn.close()
        return jsonify({"mensaje": "Usuario registrado con éxito"}), 201
    except:
        return jsonify({"error": "La cédula ya existe"}), 400

@app.route('/api/v1/login', methods=['POST', 'OPTIONS'])
@cross_origin()
def login():
    if request.method == 'OPTIONS': return jsonify({"ok": True}), 200
    datos = request.json
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT clave_hash, nombre FROM usuarios WHERE cedula = ?", (datos.get('cedula'),))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[0], datos.get('clave')):
        return jsonify({"autenticado": True, "nombre": user[1]}), 200
    return jsonify({"autenticado": False, "error": "Datos incorrectos"}), 401

@app.route('/api/v1/reportar', methods=['POST', 'OPTIONS'])
@cross_origin()
def reportar():
    if request.method == 'OPTIONS': return jsonify({"ok": True}), 200
    datos = request.json
    hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reportes (cedula_vecino, gps, hora, direccion) VALUES (?,?,?,?)",
                   (datos.get('cedula'), datos.get('gps'), hora_actual, datos.get('barrio')))
    conn.commit()
    conn.close()
    return jsonify({"mensaje": "Alerta enviada"}), 200

# IMPORTANTE: No usamos app.run() para que Render use Gunicorn
