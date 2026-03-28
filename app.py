import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)  # Permite que GitHub Pages se conecte a Render
bcrypt = Bcrypt(app)

# CONFIGURACIÓN DE SUPABASE (Usa tus variables de entorno en Render)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return "Servidor SafeQuito 2026 - Activo y Protegiendo el Barrio", 200

# 1. LOGIN DE VECINOS
@app.route('/api/v1/login', methods=['POST'])
def login():
    datos = request.json
    cedula = datos.get('cedula')
    password = datos.get('password')

    if not cedula or not password:
        return jsonify({"status": "error", "msj": "Faltan datos"}), 400

    try:
        # Buscamos al usuario por cédula
        respuesta = supabase.table("usuarios").select("*").eq("cedula", cedula).execute()
        usuario = respuesta.data[0] if respuesta.data else None

        if usuario and bcrypt.check_password_hash(usuario['password'], password):
            return jsonify({
                "status": "ok", 
                "nombre": usuario['nombres'],
                "barrio": usuario['barrio'] # Enviamos el barrio para reportes más exactos
            }), 200
        else:
            return jsonify({"status": "error", "msj": "Credenciales inválidas"}), 401
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 2. REGISTRO DE NUEVOS VECINOS (CON DIRECCIÓN DETALLADA)
@app.route('/api/v1/registrar', methods=['POST'])
def registrar():
    datos = request.json
    
    # Datos básicos
    cedula = datos.get('cedula')
    nombres = datos.get('nombres')
    apellidos = datos.get('apellidos')
    celular = datos.get('celular')
    password = datos.get('password')
    
    # Datos de ubicación solicitados
    barrio = datos.get('barrio')
    calle_p = datos.get('calle_principal')
    calle_s = datos.get('calle_secundaria')
    n_casa = datos.get('numero_casa')

    if not cedula or not password or not barrio:
        return jsonify({"status": "error", "msj": "Cédula, clave y barrio son obligatorios"}), 400

    try:
        # Ciframos la contraseña antes de guardar
        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        nuevo_usuario = {
            "cedula": cedula,
            "nombres": nombres,
            "apellidos": apellidos,
            "celular": celular,
            "password": pw_hash,
            "barrio": barrio,
            "calle_principal": calle_p,
            "calle_secundaria": calle_s,
            "numero_casa": n_casa
        }

        supabase.table("usuarios").insert(nuevo_usuario).execute()
        return jsonify({"status": "ok", "msj": "Vecino registrado correctamente"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": "Error o cédula ya registrada"}), 500

# 3. REPORTE DE ALERTAS (AHORA INCLUYE DATOS DE QUIÉN REPORTA)
@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    datos = request.json
    cedula = datos.get('cedula')
    tipo_alerta = datos.get('tipo')
    ubicacion_gps = datos.get('gps')

    try:
        # Buscamos los datos del vecino para que el reporte sea completo
        res_user = supabase.table("usuarios").select("nombres, apellidos, barrio, calle_principal, numero_casa").eq("cedula", cedula).execute()
        user_info = res_user.data[0] if res_user.data else {}

        reporte = {
            "cedula_vecino": cedula,
            "nombre_completo": f"{user_info.get('nombres')} {user_info.get('apellidos')}",
            "tipo_alerta": tipo_alerta,
            "gps": ubicacion_gps,
            "barrio": user_info.get('barrio'),
            "direccion_exacta": f"{user_info.get('calle_principal')} y {user_info.get('numero_casa')}"
        }

        supabase.table("reportes").insert(reporte).execute()
        return jsonify({"status": "ok", "msj": "Alerta procesada"}), 200
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
