import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# CONFIGURACIÓN DE SUPABASE
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return "Servidor SafeQuito 2026 - Sistema de Seguridad Activo", 200

# 1. LOGIN (AHORA DEVUELVE EL ROL)
@app.route('/api/v1/login', methods=['POST'])
def login():
    datos = request.json
    cedula = datos.get('cedula')
    password = datos.get('password')

    if not cedula or not password:
        return jsonify({"status": "error", "msj": "Faltan datos"}), 400

    try:
        respuesta = supabase.table("usuarios").select("*").eq("cedula", cedula).execute()
        usuario = respuesta.data[0] if respuesta.data else None

        if usuario and bcrypt.check_password_hash(usuario['password'], password):
            return jsonify({
                "status": "ok", 
                "nombre": usuario['nombres'],
                "barrio": usuario['barrio'],
                "rol": usuario.get('rol', 'vecino') # <--- IMPORTANTE PARA EL HTML
            }), 200
        else:
            return jsonify({"status": "error", "msj": "Cédula o clave incorrecta"}), 401
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 2. REGISTRO
@app.route('/api/v1/registrar', methods=['POST'])
def registrar():
    datos = request.json
    pw_raw = datos.get('password')
    pw_hash = bcrypt.generate_password_hash(pw_raw).decode('utf-8') if pw_raw else None

    nuevo_usuario = {
        "cedula": datos.get('cedula'),
        "nombres": datos.get('nombres'),
        "apellidos": datos.get('apellidos'),
        "correo": datos.get('correo'),
        "celular": datos.get('celular'),
        "password": pw_hash,
        "barrio": datos.get('barrio'),
        "calle_principal": datos.get('calle_principal'),
        "calle_secundaria": datos.get('calle_secundaria'),
        "numero_casa": datos.get('numero_casa'),
        "rol": "vecino" # Por defecto todos entran como vecinos
    }

    try:
        supabase.table("usuarios").insert(nuevo_usuario).execute()
        return jsonify({"status": "ok", "msj": "Registro exitoso"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": "Error al registrar"}), 500

# 3. REPORTAR ALERTA (CON ESTADO)
@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    datos = request.json
    cedula = datos.get('cedula')
    tipo_alerta = datos.get('tipo')
    gps = datos.get('gps')

    try:
        res_user = supabase.table("usuarios").select("*").eq("cedula", cedula).execute()
        u = res_user.data[0] if res_user.data else {}

        nuevo_reporte = {
            "cedula_vecino": cedula,
            "nombre_completo": f"{u.get('nombres')} {u.get('apellidos')}",
            "tipo_alerta": tipo_alerta,
            "gps": gps,
            "barrio": u.get('barrio'),
            "direccion_exacta": f"{u.get('calle_principal')} y {u.get('calle_secundaria')} - Casa: {u.get('numero_casa')}",
            "estado": "Pendiente" # <--- ESTADO INICIAL
        }

        supabase.table("reportes").insert(nuevo_reporte).execute()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# ==========================================
# RUTAS DE ADMINISTRACIÓN Y GESTIÓN
# ==========================================

# 4. ELIMINAR USUARIO (SOLO ADMIN)
@app.route('/api/v1/usuarios/<cedula_objetivo>', methods=['DELETE'])
def eliminar_usuario(cedula_objetivo):
    admin_cedula = request.headers.get('X-Admin-Cedula') 

    try:
        # Verificamos si es Admin (Tú: 1756560001)
        check = supabase.table("usuarios").select("rol").eq("cedula", admin_cedula).execute()
        
        if not check.data or check.data[0]['rol'] != 'admin':
            return jsonify({"status": "error", "msj": "No autorizado"}), 403

        supabase.table("usuarios").delete().eq("cedula", cedula_objetivo).execute()
        return jsonify({"status": "ok", "msj": "Usuario eliminado"}), 200
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 5. VER REPORTES (ADMIN, POLICIA, DIRIGENTE)
@app.route('/api/v1/reportes', methods=['GET'])
def obtener_reportes():
    user_cedula = request.headers.get('X-Usuario-Cedula')

    try:
        user_info = supabase.table("usuarios").select("rol").eq("cedula", user_cedula).execute()
        rol = user_info.data[0]['rol'] if user_info.data else 'vecino'

        if rol in ['admin', 'dirigente', 'policia']:
            res = supabase.table("reportes").select("*").order("id", desc=True).execute()
            return jsonify(res.data), 200
        
        return jsonify({"status": "error", "msj": "No autorizado"}), 403
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 6. ACTUALIZAR ESTADO DE REPORTE (POLICIA / DIRIGENTE)
@app.route('/api/v1/reportes/<int:id_reporte>', methods=['PUT'])
def actualizar_estado(id_reporte):
    datos = request.json
    nuevo_estado = datos.get('estado')
    user_cedula = request.headers.get('X-Usuario-Cedula')

    try:
        user_info = supabase.table("usuarios").select("rol").eq("cedula", user_cedula).execute()
        rol = user_info.data[0]['rol'] if user_info.data else 'vecino'

        if rol in ['admin', 'dirigente', 'policia']:
            supabase.table("reportes").update({"estado": nuevo_estado}).eq("id", id_reporte).execute()
            return jsonify({"status": "ok"}), 200
        
        return jsonify({"status": "error"}), 403
    except Exception as e:
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
