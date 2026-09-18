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
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {"sub": "mailto:NITRAXX07@GMAIL.COM"}

# Memoria temporal para trayectos y chat
trayectos_activos = {}
chats_alertas = {}

@app.route('/')
def home():
    return "Servidor SafeQuito - Sistema Activo en Neon Postgres", 200

def disparar_notificaciones_push(tipo, barrio):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM suscripciones;")
        subs = cur.fetchall()
        cur.close()
        
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
                    cur_del = conn.cursor()
                    cur_del.execute("DELETE FROM suscripciones WHERE endpoint = %s;", (s['endpoint'],))
                    conn.commit()
                    cur_del.close()
    except Exception as e:
        print(f"Error enviando push: {e}")
    finally:
        if conn:
            conn.close()

# 1. LOGIN
@app.route('/api/v1/login', methods=['POST'])
def login():
    datos = request.json or {}
    cedula = str(datos.get('cedula', '')).strip()
    password = datos.get('password')

    if not cedula or not password:
        return jsonify({"status": "error", "msj": "Faltan datos"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE TRIM(cedula::text) = %s;", (cedula,))
        usuario = cur.fetchone()

        if usuario and bcrypt.check_password_hash(usuario['password'], password):
            cur.execute("""
                SELECT id FROM reportes 
                WHERE TRIM(cedula_vecino::text) = %s AND tipo_alerta = 'Ruta Segura' AND estado = 'En transcurso'
                ORDER BY id DESC LIMIT 1;
            """, (cedula,))
            trayecto_activo = cur.fetchone()
            alerta_id_activo = trayecto_activo['id'] if trayecto_activo else None

            cur.close()

            return jsonify({
                "status": "ok", 
                "nombre": f"{usuario['nombres']} {usuario['apellidos']}".strip(),
                "barrio": usuario['barrio'],
                "rol": usuario.get('rol', 'vecino'),
                "alerta_id_activo": alerta_id_activo
            }), 200
        else:
            if cur:
                cur.close()
            return jsonify({"status": "error", "msj": "Cédula o clave incorrecta"}), 401
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500
    finally:
        if conn:
            conn.close()

# 2. REGISTRO
@app.route('/api/v1/registrar', methods=['POST'])
def registrar():
    datos = request.json or {}
    
    acepto_terminos = datos.get('acepto_terminos', False)
    if not acepto_terminos:
        return jsonify({
            "status": "error", 
            "msj": "Debe aceptar la Política de Privacidad conforme a la LOPDP de Ecuador para registrarse."
        }), 400

    pw_raw = datos.get('password')
    pw_hash = bcrypt.generate_password_hash(pw_raw).decode('utf-8') if pw_raw else None

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO usuarios (
                cedula, nombres, apellidos, correo, celular, password, 
                barrio, calle_principal, calle_secundaria, numero_casa, rol, acepto_terminos
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            str(datos.get('cedula', '')).strip(), datos.get('nombres'), datos.get('apellidos'),
            datos.get('correo'), datos.get('celular'), pw_hash,
            datos.get('barrio'), datos.get('calle_principal'), datos.get('calle_secundaria'),
            datos.get('numero_casa'), 'vecino', True
        ))
        conn.commit()
        cur.close()
        return jsonify({"status": "ok", "msj": "Registro exitoso y consentimiento registrado"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": "Error al registrar: " + str(e)}), 500
    finally:
        if conn:
            conn.close()

# 3. REPORTAR ALERTA
@app.route('/api/v1/reportar', methods=['POST'])
def reportar():
    datos = request.json or {}
    cedula = str(datos.get('cedula', '')).strip()
    tipo_alerta = datos.get('tipo')
    gps = datos.get('gps')

    conn = None
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
        
        dir_exacta = f"{calle_p} y {calle_s} - Casa: {num_c}" if (calle_p or calle_s) else "Dirección registrada según mapa"
        barrio = u.get('barrio', 'Sin Barrio')

        cur.execute("""
            INSERT INTO reportes (cedula_vecino, nombre_completo, tipo_alerta, gps, barrio, direccion_exacta, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (cedula, nombre_completo, tipo_alerta, gps, barrio, dir_exacta, "Pendiente"))
        
        alerta_creada = cur.fetchone()
        alerta_id = alerta_creada['id'] if alerta_creada else None

        conn.commit()
        cur.close()

        disparar_notificaciones_push(tipo_alerta, barrio)

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
    finally:
        if conn:
            conn.close()

# 4. ELIMINAR USUARIO
@app.route('/api/v1/usuarios/<cedula_objetivo>', methods=['DELETE'])
def eliminar_usuario(cedula_objetivo):
    admin_cedula = str(request.headers.get('X-Admin-Cedula') or request.headers.get('X-Usuario-Cedula', '')).strip()
    target = str(cedula_objetivo).strip()

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT rol FROM usuarios WHERE TRIM(cedula::text) = %s;", (admin_cedula,))
        check = cur.fetchone()
        
        if not check or check['rol'] != 'admin':
            cur.close()
            return jsonify({"status": "error", "msj": "No autorizado"}), 403

        cur.execute("DELETE FROM suscripciones WHERE TRIM(cedula::text) = %s;", (target,))
        cur.execute("DELETE FROM usuarios WHERE TRIM(cedula::text) = %s;", (target,))
        
        conn.commit()
        cur.close()

        trayectos_activos.pop(target, None)

        return jsonify({"status": "ok", "msj": "Usuario y suscripciones eliminados correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500
    finally:
        if conn:
            conn.close()

# 5. OBTENER REPORTES
@app.route('/api/v1/reportes', methods=['GET'])
def obtener_reportes():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                r.id,
                r.tipo_alerta,
                r.estado,
                r.gps,
                r.created_at::text AS created_at,
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
        return jsonify(reportes), 200
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500
    finally:
        if conn:
            conn.close()

# 6. ACTUALIZAR ESTADO
@app.route('/api/v1/reportes/<int:id_reporte>', methods=['PUT'])
def actualizar_estado(id_reporte):
    datos = request.json or {}
    nuevo_estado = datos.get('estado')
    user_cedula = str(request.headers.get('X-Usuario-Cedula') or datos.get('cedula', '')).strip()

    if not nuevo_estado:
        return jsonify({"status": "error", "msj": "Estado no proporcionado"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT TRIM(cedula_vecino::text) AS cedula_vecino FROM reportes WHERE id = %s;", (id_reporte,))
        reporte = cur.fetchone()

        if not reporte:
            cur.close()
            return jsonify({"status": "error", "msj": "Alerta no encontrada"}), 404

        cur.execute("SELECT rol FROM usuarios WHERE TRIM(cedula::text) = %s;", (user_cedula,))
        user_info = cur.fetchone()
        rol = user_info['rol'] if user_info else 'vecino'

        es_dueno = (reporte['cedula_vecino'] == user_cedula)
        es_autorizado = rol in ['admin', 'dirigente', 'policia']

        if es_dueno or es_autorizado:
            cur.execute("UPDATE reportes SET estado = %s WHERE id = %s;", (nuevo_estado, id_reporte))
            conn.commit()

            if reporte['cedula_vecino'] in trayectos_activos:
                trayectos_activos.pop(reporte['cedula_vecino'], None)

            cur.close()
            return jsonify({"status": "ok", "msj": "Estado actualizado correctamente"}), 200

        cur.close()
        return jsonify({"status": "error", "msj": "No autorizado para modificar esta alerta"}), 403
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500
    finally:
        if conn:
            conn.close()

# 7. SUSCRIBIR NOTIFICACIONES PUSH
@app.route('/api/v1/suscribir', methods=['POST'])
def suscribir():
    datos = request.json or {}
    cedula = str(datos.get('cedula', '')).strip()
    sub = datos.get('subscription', {})
    
    conn = None
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
        return jsonify({"status": "ok"}), 201
    except Exception as e:
        return jsonify({"status": "error", "msj": str(e)}), 500
    finally:
        if conn:
            conn.close()

# 8. TRAYECTOS ACTIVOS
@app.route('/api/v1/trayecto/iniciar', methods=['POST'])
def iniciar_trayecto():
    data = request.get_json() or {}
    cedula = str(data.get('cedula', '')).strip()
    destino = data.get('destino')
    salida = data.get('salida', '')
    gps = data.get('gps', '0,0')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM usuarios WHERE TRIM(cedula::text) = %s;", (cedula,))
        u = cur.fetchone() or {}
        nombre_completo = f"{u.get('nombres', '')} {u.get('apellidos', '')}".strip() or "Vecino"
        barrio = u.get('barrio', 'Sin Barrio')

        cur.execute("""
            INSERT INTO reportes (cedula_vecino, nombre_completo, tipo_alerta, gps, barrio, direccion_exacta, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (cedula, nombre_completo, 'Ruta Segura', gps, barrio, f"Hacia: {destino}", 'En transcurso'))
        
        alerta_creada = cur.fetchone()
        alerta_id = alerta_creada['id'] if alerta_creada else None

        if alerta_id and gps and ',' in gps:
            lat, lng = gps.split(',')
            cur.execute("""
                INSERT INTO puntos_trayecto (alerta_id, cedula, latitud, longitud)
                VALUES (%s, %s, %s, %s);
            """, (alerta_id, cedula, float(lat), float(lng)))

        conn.commit()
        cur.close()

        trayectos_activos[cedula] = {
            'id_reporte': alerta_id,
            'salida': salida, 
            'destino': destino, 
            'lat': None, 
            'lng': None, 
            'estado': 'en_camino'
        }
        return jsonify({'status': 'ok', 'id': alerta_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msj': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/v1/trayecto/actualizar', methods=['POST'])
def actualizar_trayecto():
    data = request.get_json() or {}
    cedula = str(data.get('cedula', '')).strip()
    lat = data.get('lat')
    lng = data.get('lng')
    alerta_id = data.get('alerta_id')

    if not lat or not lng:
        return jsonify({'status': 'error', 'msj': 'Faltan coordenadas'}), 400

    if cedula in trayectos_activos:
        trayectos_activos[cedula]['lat'] = lat
        trayectos_activos[cedula]['lng'] = lng

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if alerta_id:
            cur.execute("""
                UPDATE reportes 
                SET gps = %s 
                WHERE id = %s;
            """, (f"{lat},{lng}", alerta_id))

            cur.execute("""
                INSERT INTO puntos_trayecto (alerta_id, cedula, latitud, longitud)
                VALUES (%s, %s, %s, %s);
            """, (alerta_id, cedula, float(lat), float(lng)))
        else:
            cur.execute("""
                UPDATE reportes 
                SET gps = %s 
                WHERE TRIM(cedula_vecino::text) = %s AND tipo_alerta = 'Ruta Segura' AND estado = 'En transcurso';
            """, (f"{lat},{lng}", cedula))

        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error actualizando trayecto: {e}")
    finally:
        if conn:
            conn.close()

    return jsonify({'status': 'ok'}), 200

@app.route('/api/v1/trayecto/<int:alerta_id>/puntos', methods=['GET'])
def obtener_puntos_trayecto(alerta_id):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT latitud, longitud 
            FROM puntos_trayecto 
            WHERE alerta_id = %s 
            ORDER BY id ASC;
        """, (alerta_id,))
        filas = cur.fetchall()
        cur.close()

        puntos = [[float(f['latitud']), float(f['longitud'])] for f in filas]
        return jsonify(puntos), 200
    except Exception as e:
        return jsonify([]), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/v1/trayecto/finalizar', methods=['POST'])
def finalizar_trayecto():
    data = request.get_json() or {}
    cedula = str(data.get('cedula', '')).strip()
    alerta_id = data.get('alerta_id')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if alerta_id:
            cur.execute("UPDATE reportes SET estado = 'Atendido' WHERE id = %s;", (alerta_id,))
        else:
            cur.execute("""
                UPDATE reportes 
                SET estado = 'Atendido' 
                WHERE TRIM(cedula_vecino::text) = %s AND tipo_alerta = 'Ruta Segura' AND estado = 'En transcurso';
            """, (cedula,))
        
        conn.commit()
        cur.close()

        trayectos_activos.pop(cedula, None)
        return jsonify({'status': 'ok', 'msj': 'Trayecto finalizado'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msj': str(e)}), 500
    finally:
        if conn:
            conn.close()

# 9. CHAT
@app.route('/api/v1/alerta/<alerta_id>/chat', methods=['GET'])
def obtener_chat(alerta_id):
    mensajes = chats_alertas.get(str(alerta_id), [])
    return jsonify(mensajes)

@app.route('/api/v1/alerta/<alerta_id>/chat', methods=['POST'])
def enviar_mensaje_chat(alerta_id):
    data = request.get_json() or {}
    cedula = str(data.get('cedula', '')).strip()
    texto = data.get('texto')
    nombre_usuario = data.get('nombre')
    rol_usuario = data.get('rol')

    alerta_id_str = str(alerta_id)
    if alerta_id_str not in chats_alertas:
        chats_alertas[alerta_id_str] = []

    if not nombre_usuario or not rol_usuario:
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT nombres, apellidos, rol FROM usuarios WHERE TRIM(cedula::text) = %s;", (cedula,))
            u = cur.fetchone()
            if u:
                nombre_usuario = f"{u['nombres']} {u['apellidos']}".strip()
                rol_usuario = u['rol']
            cur.close()
        except Exception as e:
            print(f"Error recuperando usuario para chat: {e}")
        finally:
            if conn:
                conn.close()

    remitente_final = nombre_usuario if nombre_usuario else (f"Vecino ({cedula[-4:]})" if len(cedula) >= 4 else "Vecino")
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
