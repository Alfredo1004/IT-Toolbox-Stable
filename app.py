from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, send_from_directory, flash
from werkzeug.security import check_password_hash
import sqlite3, json, os, pandas as pd
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'it_toolbox_secure_key_2025'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'descargas')

SOFTWARE_PROHIBIDO = ["Torrent", "Steam", "Spotify", "Netflix", "AnyDesk", "TeamViewer"]

def conectar_db():
    # Esto asegura que busque la DB en la misma carpeta donde está app.py
    db_path = os.path.join(BASE_DIR, 'soporte.db') 
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTA DEL AGENTE (HARDWARE + SOFTWARE) ---
@app.route('/reporte_agente', methods=['POST'])
def reporte_agente():
    data = request.get_json()
    if not data: return jsonify({"status": "error"}), 400
    
    hostname = data.get('equipo'); usuario = data.get('usuario')
    ip = data.get('ip_v4', '0.0.0.0'); mac = data.get('mac', 'N/A')
    specs = f"RAM: {data.get('ram_total')} | Disco: {data.get('disco_total')}"
    serie = data.get('n_serie', 'N/A'); marca = data.get('marca', 'N/A'); modelo = data.get('modelo', 'N/A')
    software_recibido = data.get('software', [])

    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. BÚSQUEDA ROBUSTA DEL EQUIPO
    existe = None
    if mac and mac != "N/A":
        cursor.execute("SELECT id FROM inventario WHERE mac_address = ?", (mac,))
        existe = cursor.fetchone()
    
    if not existe:
        cursor.execute("SELECT id FROM inventario WHERE nombre_equipo = ?", (hostname,))
        existe = cursor.fetchone()
    
    # 2. ACTUALIZAR O INSERTAR
    if existe:
        cursor.execute("""UPDATE inventario SET ip_address=?, especificaciones=?, usuario=?, n_serie=?, marca=?, modelo=?, mac_address=? WHERE id=?""", 
                       (ip, specs, usuario, serie, marca, modelo, mac, existe['id']))
    else:
        cursor.execute("""INSERT INTO inventario (nombre_equipo, usuario, especificaciones, ip_address, n_serie, marca, modelo, mac_address, tipo_red, ubicacion, fecha_asignacion) 
                          VALUES (?,?,?,?,?,?,?,?,?,?,?)""", 
                       (hostname, usuario, specs, ip, serie, marca, modelo, mac, 'Ethernet', 'Monterrey', datetime.now().strftime('%Y-%m-%d')))
    
    # 3. ACTUALIZACIÓN DE SOFTWARE Y DETECCIÓN DE PROHIBIDOS
    cursor.execute("DELETE FROM software_inventario WHERE nombre_equipo = ?", (hostname,))
    prohibidos_hallados = []

    for s in software_recibido:
        n_sw = s['nombre']; v_sw = s['version']
        cursor.execute("INSERT INTO software_inventario (nombre_equipo, nombre_software, version, fecha_escaneo) VALUES (?,?,?,?)",
                       (hostname, n_sw, v_sw, datetime.now().strftime('%Y-%m-%d')))
        
        if any(p.lower() in n_sw.lower() for p in SOFTWARE_PROHIBIDO):
            prohibidos_hallados.append(n_sw)

    # --- 4. NUEVA LÓGICA DE TELEMETRÍA (HARDWARE CRÍTICO) ---
    alertas_hw = []
    info_recursos = f"🧠{data.get('ram_uso')} | 💾{data.get('disco_libre')}"
    
    try:
        # 1. Procesar RAM: Usamos float() porque viene con decimales '81.3'
        ram_str = data.get('ram_uso', '0').replace('%', '').strip()
        uso_ram_num = float(ram_str)  # Ahora acepta '81.3'
        
        # 2. Procesar Disco: Limpieza más profunda
        disco_libre_str = data.get('disco_libre', '100GB').upper()
        # Quitamos 'GB' y 'LIBRES' para dejar solo el número
        disco_limpio = disco_libre_str.replace('GB', '').replace('LIBRES', '').strip()
        disco_num = float(disco_limpio)

        # Evaluación de límites (Usando tu prueba de < 500)
        if uso_ram_num > 90:
            alertas_hw.append(f"RAM SATURADA ({uso_ram_num}%)")
        if disco_num < 20:
            alertas_hw.append(f"DISCO CRÍTICO ({disco_num}GB Libres)")
            
    except Exception as e:
        print(f"Error procesando hardware de {hostname}: {e}")

    # --- 5. CONSOLIDACIÓN DE INCIDENCIA MEJORADA ---
    falla_texto = ""
    estado_ticket = "Pendiente"

    # 1. Verificamos Software Prohibido
    if prohibidos_hallados:
        falla_texto = f"⚠️ PROHIBIDO: {', '.join(prohibidos_hallados)}"
        estado_ticket = "Prohibido"

    # 2. Verificamos Alertas de Hardware (AQUÍ ESTÁ EL TRUCO)
    if alertas_hw:
        # Si ya había texto de software, añadimos un separador, si no, empezamos el texto
        prefijo = " | " if falla_texto else ""
        falla_texto += f"{prefijo}🚨 HW: {', '.join(alertas_hw)}"
        # Si no hay software prohibido pero sí falla de hardware, lo marcamos como Pendiente
        if not prohibidos_hallados:
            estado_ticket = "Pendiente"

    # 3. Resultado Final
    if not falla_texto:
        problema_final = f"Auditoría OK | {info_recursos}"
    else:
        # Aquí unimos las alertas encontradas con la info de recursos al final
        problema_final = f"{falla_texto} | {info_recursos}"

    # Importante: Asegúrate de que el orden de las columnas coincida con tu tabla SQL
    print(f"DEBUG: Guardando incidencia -> {problema_final}") # AÑADE ESTA LÍNEA
    cursor.execute("INSERT INTO incidencias (equipo, usuario, problema, solucion, fecha) VALUES (?,?,?,?,?)", 
                    (hostname, usuario, problema_final, estado_ticket, datetime.now().strftime('%Y-%m-%d %H:%M')))
    
    conn.commit(); conn.close()
    return jsonify({"status": "success"}), 200

# --- CONSULTA SOFTWARE ---
@app.route('/ver_software/<hostname>')
@login_required
def ver_software(hostname):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM software_inventario WHERE nombre_equipo = ? ORDER BY nombre_software ASC", (hostname,))
    sw = [dict(ix) for ix in cursor.fetchall()]; conn.close(); return jsonify(sw)

# --- DASHBOARD PRINCIPAL ---
@app.route('/')
@login_required
def dashboard():
    conn = conectar_db(); cursor = conn.cursor(); hoy = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM inventario"); total_eq = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM incidencias WHERE solucion = 'Pendiente'"); pend = cursor.fetchone()[0]
    cursor.execute("""SELECT COUNT(*) FROM mantenimiento m JOIN inventario e ON m.equipo_id = e.id WHERE m.proxima_fecha < ? AND m.proxima_fecha != '' AND m.proxima_fecha IS NOT NULL""", (hoy,))
    venc = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM incidencias ORDER BY id DESC")
    t_procesados = []
    for t in cursor.fetchall():
        info = t['equipo']
        if info and info.startswith('{'):
            try:
                d = json.loads(info); info = f"💻 {d.get('equipo')} | 🧠 {d.get('ram')} | 💾 {d.get('disco')}"
            except: pass
        t_procesados.append(dict(t, info_web=info))

    cursor.execute("SELECT * FROM inventario ORDER BY id ASC"); equipos = cursor.fetchall()
    cursor.execute("SELECT * FROM boveda ORDER BY id DESC"); claves = cursor.fetchall()
    cursor.execute("SELECT m.*, e.nombre_equipo FROM mantenimiento m JOIN inventario e ON m.equipo_id = e.id ORDER BY m.fecha_realizado DESC"); manto = cursor.fetchall()
    cursor.execute("SELECT * FROM notas ORDER BY id DESC"); notas = cursor.fetchall()
    cursor.execute("SELECT * FROM prestamos ORDER BY id DESC"); prestamos = cursor.fetchall()
    cursor.execute("SELECT * FROM wiki ORDER BY categoria ASC, titulo ASC"); wiki = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM incidencias WHERE solucion = 'Solucionado'"); sol = cursor.fetchone()[0]
    stats_tickets = [sol, pend]; stats_manto = [len(manto)]
    conn.close()
    return render_template('toolbox.html', resumen={'equipos': total_eq, 'pendientes': pend, 'vencidos': venc},
                           tickets=t_procesados, equipos=equipos, claves=claves, mantenimientos=manto, 
                           notas=notas, prestamos=prestamos, wiki=wiki, fecha_actual=hoy, 
                           stats_tickets=stats_tickets, stats_manto=stats_manto, pendientes_count=pend)

# --- LOGIN ACTUALIZADO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        conn = conectar_db(); cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM usuarios WHERE username = ?", (u,))
        res = cursor.fetchone(); conn.close()
        if res and check_password_hash(res['password'], p):
            session['user_id'], session['username'] = res['id'], u
            flash("¡Inicio de sesión exitoso! Bienvenido al sistema.", "success")
            return redirect(url_for('dashboard'))
        flash("Usuario o contraseña incorrectos. Intente de nuevo.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

# --- RUTAS DE ACCIONES (ESTABLES) ---
@app.route('/actualizar_ticket/<int:id>', methods=['POST'])
@login_required
def actualizar_ticket(id):
    conn = conectar_db(); conn.execute("UPDATE incidencias SET solucion = ?, comentarios = ? WHERE id = ?", (request.form['estado'], request.form['comentario'], id)); conn.commit(); conn.close(); return redirect('/#tickets')

@app.route('/eliminar_ticket/<int:id>')
@login_required
def eliminar_ticket(id):
    conn = conectar_db(); conn.execute("DELETE FROM incidencias WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#tickets')

@app.route('/actualizar_equipo/<int:id>', methods=['POST'])
@login_required
def actualizar_equipo(id):
    conn = conectar_db(); conn.execute("""UPDATE inventario SET nombre_equipo=?, usuario=?, n_serie=?, marca=?, modelo=?, ubicacion=?, fecha_asignacion=?, ip_address=?, tipo_red=?, especificaciones=? WHERE id=?""", (request.form['nombre'], request.form['usuario'], request.form['serie'], request.form['marca'], request.form['modelo'], request.form['ubicacion'], request.form['fecha_asig'], request.form['ip'], request.form['red'], request.form['specs'], id)); conn.commit(); conn.close(); return redirect('/#inventario')

@app.route('/eliminar_equipo/<int:id>')
@login_required
def eliminar_equipo(id):
    conn = conectar_db(); conn.execute("DELETE FROM inventario WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#inventario')

@app.route('/actualizar_clave/<int:id>', methods=['POST'])
@login_required
def actualizar_clave(id):
    conn = conectar_db(); conn.execute("UPDATE boveda SET servicio=?, usuario_acceso=?, password_acceso=?, link_url=? WHERE id=?", (request.form['servicio'], request.form['usuario'], request.form['password'], request.form['url'], id)); conn.commit(); conn.close(); return redirect('/#boveda')

@app.route('/eliminar_clave/<int:id>')
@login_required
def eliminar_clave(id):
    conn = conectar_db(); conn.execute("DELETE FROM boveda WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#boveda')

@app.route('/agregar_wiki', methods=['POST'])
@login_required
def agregar_wiki():
    conn = conectar_db(); conn.execute("INSERT INTO wiki (titulo, categoria, contenido, fecha_actualizacion) VALUES (?,?,?,?)", (request.form['titulo'], request.form['categoria'], request.form['contenido'], datetime.now().strftime('%Y-%m-%d'))); conn.commit(); conn.close(); return redirect('/#wiki')

@app.route('/editar_wiki/<int:id>', methods=['POST'])
@login_required
def editar_wiki(id):
    conn = conectar_db(); conn.execute("UPDATE wiki SET titulo=?, categoria=?, contenido=?, fecha_actualizacion=? WHERE id=?", (request.form['titulo'], request.form['categoria'], request.form['contenido'], datetime.now().strftime('%Y-%m-%d'), id)); conn.commit(); conn.close(); return redirect('/#wiki')

@app.route('/eliminar_wiki/<int:id>')
@login_required
def eliminar_wiki(id):
    conn = conectar_db(); conn.execute("DELETE FROM wiki WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#wiki')

@app.route('/agregar_mantenimiento', methods=['POST'])
@login_required
def agregar_mantenimiento():
    conn = conectar_db(); conn.execute("INSERT INTO mantenimiento (equipo_id, fecha_realizado, tecnico, descripcion, proxima_fecha) VALUES (?,?,?,?,?)", (request.form['equipo_id'], request.form['fecha'], session['username'], request.form['description'], request.form['proxima_fecha'])); conn.commit(); conn.close(); return redirect('/#mantenimiento')

@app.route('/actualizar_mantenimiento/<int:id>', methods=['POST'])
@login_required
def actualizar_mantenimiento(id):
    conn = conectar_db(); conn.execute("UPDATE mantenimiento SET fecha_realizado=?, proxima_fecha=?, descripcion=? WHERE id=?", (request.form['fecha'], request.form['proxima_fecha'], request.form['description'], id)); conn.commit(); conn.close(); return redirect('/#mantenimiento')

@app.route('/eliminar_mantenimiento/<int:id>')
@login_required
def eliminar_mantenimiento(id):
    conn = conectar_db(); conn.execute("DELETE FROM mantenimiento WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#mantenimiento')

@app.route('/agregar_prestamo', methods=['POST'])
@login_required
def agregar_prestamo():
    conn = conectar_db(); conn.execute("INSERT INTO prestamos (articulo, usuario_prestamo, fecha_salida, fecha_retorno_estimada, estado) VALUES (?,?,?,?,?)", (request.form['articulo'], request.form['usuario'], request.form['salida'], request.form['retorno'], 'Activo')); conn.commit(); conn.close(); return redirect('/#prestamos')

@app.route('/finalizar_prestamo/<int:id>')
@login_required
def finalizar_prestamo(id):
    conn = conectar_db(); conn.execute("UPDATE prestamos SET estado='Devuelto' WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#prestamos')

@app.route('/eliminar_prestamo/<int:id>')
@login_required
def eliminar_prestamo(id):
    conn = conectar_db(); conn.execute("DELETE FROM prestamos WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#prestamos')

@app.route('/agregar_nota', methods=['POST'])
@login_required
def agregar_nota():
    conn = conectar_db(); conn.execute("INSERT INTO notas (contenido, fecha) VALUES (?,?)", (request.form['contenido'], datetime.now().strftime('%d/%m %H:%M'))); conn.commit(); conn.close(); return redirect('/')

@app.route('/eliminar_nota/<int:id>')
@login_required
def eliminar_nota(id):
    conn = conectar_db(); conn.execute("DELETE FROM notas WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/')

@app.route('/crear_incidencia_manual', methods=['POST'])
@login_required
def crear_incidencia_manual():
    conn = conectar_db(); conn.execute("INSERT INTO incidencias (equipo, usuario, problema, solucion, fecha) VALUES (?,?,?,?,?)", (request.form['equipo_nombre'], request.form['usuario'], request.form['problema'], 'Pendiente', datetime.now().strftime('%Y-%m-%d %H:%M'))); conn.commit(); conn.close(); return redirect('/#tickets')

@app.route('/agregar_equipo', methods=['POST'])
@login_required
def agregar_equipo():
    conn = conectar_db(); conn.execute("""INSERT INTO inventario (nombre_equipo, usuario, especificaciones, ip_address, tipo_red, n_serie, marca, modelo, ubicacion, fecha_asignacion) VALUES (?,?,?,?,?,?,?,?,?,?)""", (request.form['nombre'], request.form['usuario'], request.form['specs'], request.form['ip'], request.form['red'], request.form['serie'], request.form['marca'], request.form['modelo'], request.form['ubicacion'], request.form['fecha_asig'])); conn.commit(); conn.close(); return redirect('/#inventario')

@app.route('/agregar_clave', methods=['POST'])
@login_required
def agregar_clave():
    conn = conectar_db(); conn.execute("INSERT INTO boveda (servicio, usuario_acceso, password_acceso, link_url) VALUES (?,?,?,?)", (request.form['servicio'], request.form['usuario'], request.form['password'], request.form['url'])); conn.commit(); conn.close(); return redirect('/#boveda')

@app.route('/descargar_agente')
@login_required
def descargar_agente(): return send_from_directory(DOWNLOAD_FOLDER, 'agente_it.exe', as_attachment=True)

@app.route('/backup_db')
@login_required
def backup_db(): return send_file(os.path.join(BASE_DIR, 'soporte.db'), as_attachment=True)

@app.route('/descargar_reporte_excel')
@login_required
def descargar_reporte_excel():
    conn = conectar_db(); df_tickets = pd.read_sql_query("SELECT id as Folio, equipo, usuario, problema as Falla, comentarios as Solucion, solucion as Estado, fecha FROM incidencias", conn)
    df_inv = pd.read_sql_query("SELECT * FROM inventario", conn); conn.close(); f = "Reporte_TI_Master.xlsx"
    with pd.ExcelWriter(f, engine='openpyxl') as writer:
        df_tickets.to_excel(writer, index=False, sheet_name='Tickets'); df_inv.to_excel(writer, index=False, sheet_name='Inventario')
    return send_file(f, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)