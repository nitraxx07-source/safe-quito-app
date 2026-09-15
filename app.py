import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from pywebpush import webpush, WebPushException
import urllib.parse

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {"sub": "mailto:NITRAXX07@GMAIL.COM"}

@app.route('/')
def home():
    return "Servidor SafeQuito - Sistema Activo en Neon Postgres", 200

def disparar_notificaciones_push(tipo, barrio):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM suscripciones;")
        subs = cur.fetchall()
        cur.close()
        conn.close()
        
        payload = {
            "title": f"🚨 AUXILIO EN {str(barrio).upper()}",
            "body": f"Alerta de: {tipo}. ¡Revisa el mapa ahora!",
            "icon": "https://tu-usuario.github.io/tu-repo/icon-100.png"
        }

        for s in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": s['endpoint'],
                        "keys": {"p256dh": s['p256dh'], "auth": s['auth']}
                    },
                    data=json.dumps(payload),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
            except WebPushException as ex:
                if ex.response and ex.response.status_code == 410:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM suscripciones WHERE endpoint = %s;", (s['endpoint'],))
                    conn.commit()
                    cur.close()
                    conn.close()
    except Exception as e:
        print(f"Error enviando push: {e}")

# 1. LOGIN
@app.route('/api/v1/login', methods=['POST'])
def login():
    datos = request.json
    cedula = str(datos.get('cedula', '')).strip()
    password = datos.get('password')

    if not cedula or not password:
        return jsonify({"status": "error", "msj": "Faltan datos"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE TRIM(cedula::text) = %s;", (cedula,))
        usuario = cur.fetchone()
        cur.close()
        conn.close()

        if usuario and bcrypt.check_password_hash(usuario['password'], password):
            return jsonify({
                "status": "ok", 
                "nombre": f"{usuario['nombres']} {usuario['apellidos']}".strip(),
                "barrio": usuario['barrio'],
                "rol": usuario.get('rol', 'vecino')
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

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO usuarios (cedula, nombres, apellidos, correo, celular, password, barrio, calle_principal, calle_secundaria, numero_casa, rol)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            str(datos.get('cedula', '')).strip(), datos.get('nombres'), datos.get('apellidos'),
            datos.get('correo'), datos.get('celular'), pw_hash,
            datos.get('barrio'), datos.get('calle_principal'), datos.get('calle_secundaria'),
            datos.get('numero_casa'), 'vecino'
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "msj": "Registro exitoso"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": "Error al registrar"}), 500

# 3. REPORTAR ALERTA CON ENLACE DIRECTO A WHATSAPP
@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    datos = request.json
    cedula = str(datos.get('cedula', '')).strip()
    tipo_alerta = datos.get('tipo')
    gps = datos.get('gps')

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM usuarios WHERE TRIM(cedula::text) = %s;", (cedula,))
        u = cur.fetchone() or {}

        nombre_completo = f"{u.get('nombres', '')} {u.get('apellidos', '')}".strip() or "Vecino"
        
        calle_p = u.get('calle_principal', '')
        calle_s = u.get('calle_secundaria', '')
        num_c = u.get('numero_casa', '')
        celular = u.get('celular', 'Sin número')
        
        if calle_p or calle_s:
            dir_exacta = f"{calle_p} y {calle_s} - Casa: {num_c}"
        else:
            dir_exacta = "Dirección registrada según mapa"
            
        barrio = u.get('barrio', 'Sin Barrio')

        # Guardar en base de datos
        cur.execute("""
            INSERT INTO reportes (cedula_vecino, nombre_completo, tipo_alerta, gps, barrio, direccion_exacta, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (cedula, nombre_completo, tipo_alerta, gps, barrio, dir_exacta, "Pendiente"))
        
        alerta_creada = cur.fetchone()
        alerta_id = alerta_creada['id'] if alerta_creada else None

        conn.commit()
        cur.close()
        conn.close()

        # Enviar notificación Push existente
        disparar_notificaciones_push(tipo_alerta, barrio)

        # Crear mensaje estructurado para WhatsApp
        mapa_url = f"https://www.google.com/maps?q={gps}"
        mensaje_wa = (
            f"🚨 *ALERTA DE SEGURIDAD - SAFEQUITO* 🚨\n\n"
            f"⚠️ *Tipo:* {tipo_alerta}\n"
            f"👤 *Vecino:* {nombre_completo}\n"
            f"📞 *Contacto:* {celular}\n"
            f"📍 *Barrio:* {barrio}\n"
            f"🏠 *Dirección:* {dir_exacta}\n"
            f"🗺️ *Ubicación GPS:* {mapa_url}"
        )

        wa_link = f"https://api.whatsapp.com/send?text={urllib.parse.quote(mensaje_wa)}"

        return jsonify({
            "status": "ok",
            "id": alerta_id,
            "msj": "Alerta enviada",
            "whatsapp_url": wa_link
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 4. ELIMINAR USUARIO
@app.route('/api/v1/usuarios/<cedula_objetivo>', methods=['DELETE'])
def eliminar_usuario(cedula_objetivo):
    admin_cedula = str(request.headers.get('X-Admin-Cedula') or request.headers.get('X-Usuario-Cedula', '')).strip()

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT rol FROM usuarios WHERE TRIM(cedula::text) = %s;", (admin_cedula,))
        check = cur.fetchone()
        
        if not check or check['rol'] != 'admin':
            cur.close()
            conn.close()
            return jsonify({"status": "error", "msj": "No autorizado"}), 403

        cur.execute("DELETE FROM usuarios WHERE TRIM(cedula::text) = %s;", (str(cedula_objetivo).strip(),))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "msj": "Usuario eliminado"}), 200
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 5. OBTENER REPORTES (SOLO ACTIVOS: Pendiente o En transcurso)
@app.route('/api/v1/reportes', methods=['GET'])
def obtener_reportes():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                r.id,
                r.tipo_alerta,
                r.estado,
                r.gps,
                COALESCE(r.barrio, u.barrio) AS barrio,
                COALESCE(NULLIF(r.nombre_completo, ''), u.nombres || ' ' || u.apellidos, 'Vecino') AS nombre_completo,
                TRIM(r.cedula_vecino::text) AS cedula_vecino,
                TRIM(r.cedula_vecino::text) AS cedula,
                COALESCE(
                    NULLIF(r.direccion_exacta, ''), 
                    CONCAT(u.calle_principal, ' y ', u.calle_secundaria, ' - Casa: ', u.numero_casa)
                ) AS direccion_exacta,
                COALESCE(u.celular, 'Sin número') AS celular,
                COALESCE(u.calle_principal, 'S/N') AS calle_principal,
                COALESCE(u.calle_secundaria, 'S/N') AS calle_secundaria,
                COALESCE(u.numero_casa, 'S/N') AS numero_casa
            FROM reportes r
            LEFT JOIN usuarios u ON TRIM(r.cedula_vecino::text) = TRIM(u.cedula::text)
            WHERE r.estado IN ('Pendiente', 'En transcurso')
            ORDER BY r.id DESC;
        """)
        reportes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(reportes), 200

    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 6. ACTUALIZAR ESTADO (PERMITIDO A ADMIN, DIRIGENTE, POLICIA O AL DUEÑO DE LA ALERTA)
@app.route('/api/v1/reportes/<int:id_reporte>', methods=['PUT'])
def actualizar_estado(id_reporte):
    datos = request.json or {}
    nuevo_estado = datos.get('estado')
    user_cedula = str(request.headers.get('X-Usuario-Cedula', '')).strip()

    if not nuevo_estado:
        return jsonify({"status": "error", "msj": "Estado no proporcionado"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Obtener la alerta para saber quién es el creador
        cur.execute("SELECT TRIM(cedula_vecino::text) AS cedula_vecino FROM reportes WHERE id = %s;", (id_reporte,))
        reporte = cur.fetchone()

        if not reporte:
            cur.close()
            conn.close()
            return jsonify({"status": "error", "msj": "Alerta no encontrada"}), 404

        # 2. Obtener el rol del usuario que realiza la petición
        cur.execute("SELECT rol FROM usuarios WHERE TRIM(cedula::text) = %s;", (user_cedula,))
        user_info = cur.fetchone()
        rol = user_info['rol'] if user_info else 'vecino'

        es_dueno = (reporte['cedula_vecino'] == user_cedula)
        es_autorizado = rol in ['admin', 'dirigente', 'policia', 'superadmin']

        # 3. Validar permisos (Dueño de la alerta O un Admin/Dirigente)
        if es_dueno or es_autorizado:
            cur.execute("UPDATE reportes SET estado = %s WHERE id = %s;", (nuevo_estado, id_reporte))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"status": "ok", "msj": "Estado actualizado correctamente"}), 200

        cur.close()
        conn.close()
        return jsonify({"status": "error", "msj": "No autorizado para modificar esta alerta"}), 403

    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 7. SUSCRIBIR NOTIFICACIONES PUSH
@app.route('/api/v1/suscribir', methods=['POST'])
def suscribir():
    datos = request.json
    cedula = str(datos.get('cedula', '')).strip()
    sub = datos.get('subscription')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO suscripciones (cedula, endpoint, p256dh, auth)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (endpoint) DO UPDATE 
            SET cedula = EXCLUDED.cedula, p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth;
        """, (cedula, sub['endpoint'], sub['keys']['p256dh'], sub['keys']['auth']))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500

# 8. RUTAS PARA RUTA SEGURA / TRAYECTOS ACTIVOS
trayectos_activos = {}

@app.route('/api/v1/trayecto/iniciar', methods=['POST'])
def iniciar_trayecto():
    data = request.get_json()
    cedula = data.get('cedula')
    destino = data.get('destino')
    salida = data.get('salida', '')
    trayectos_activos[cedula] = {'salida': salida, 'destino': destino, 'lat': None, 'lng': None, 'estado': 'en_camino'}
    return jsonify({'status': 'ok'})

@app.route('/api/v1/trayecto/actualizar', methods=['POST'])
def actualizar_trayecto():
    data = request.get_json()
    cedula = data.get('cedula')
    lat = data.get('lat')
    lng = data.get('lng')
    if cedula in trayectos_activos:
        trayectos_activos[cedula]['lat'] = lat
        trayectos_activos[cedula]['lng'] = lng
    return jsonify({'status': 'ok'})

@app.route('/api/v1/trayecto/finalizar', methods=['POST'])
def finalizar_trayecto():
    data = request.get_json()
    cedula = data.get('cedula')
    trayectos_activos.pop(cedula, None)
    return jsonify({'status': 'ok'})

# 9. RUTAS PARA EL CHAT DE TEXTO POR ALERTA CON ROL Y NOMBRE REAL
chats_alertas = {}

@app.route('/api/v1/alerta/<alerta_id>/chat', methods=['GET'])
def obtener_chat(alerta_id):
    mensajes = chats_alertas.get(str(alerta_id), [])
    return jsonify(mensajes)

@app.route('/api/v1/alerta/<alerta_id>/chat', methods=['POST'])
def enviar_mensaje_chat(alerta_id):
    data = request.get_json()
    cedula = data.get('cedula')
    texto = data.get('texto')
    nombre_usuario = data.get('nombre')
    rol_usuario = data.get('rol')

    alerta_id_str = str(alerta_id)
    if alerta_id_str not in chats_alertas:
        chats_alertas[alerta_id_str] = []

    if not nombre_usuario or not rol_usuario:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT nombres, apellidos, rol FROM usuarios WHERE TRIM(cedula::text) = %s;", (str(cedula).strip(),))
            u = cur.fetchone()
            if u:
                nombre_usuario = f"{u['nombres']} {u['apellidos']}".strip()
                rol_usuario = u['rol']
            cur.close()
            conn.close()
        except:
            pass

    remitente_final = nombre_usuario if nombre_usuario else (f"Vecino ({cedula[-4:]})" if cedula and len(cedula) >= 4 else "Vecino")
    rol_final = rol_usuario if rol_usuario else "vecino"
    
    chats_alertas[alerta_id_str].append({
        'remitente': remitente_final,
        'rol': rol_final,
        'texto': texto
    })
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
