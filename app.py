from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, send_from_directory, flash
from werkzeug.security import check_password_hash
import sqlite3, json, os, pandas as pd
from functools import wraps
from datetime import datetime
from fpdf import FPDF
from flask import make_response
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
    cursor.execute("SELECT * FROM celulares ORDER BY id DESC"); celulares = cursor.fetchall()

    gastos_ordenados = {}

    # --- DENTRO DE @app.route('/') ---
# Consulta de gastos calculando el total por fila
    cursor.execute("SELECT *, (cantidad * precio_unitario) as precio_total FROM gastos ORDER BY fecha DESC")
    gastos_raw = cursor.fetchall()

# Lógica para agrupar por mes (Enero, Febrero, etc.)
    gastos_por_mes = {}
    nombres_meses = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", 
                 "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

    for g in gastos_raw:
        # Extraemos el mes de la fecha (formato YYYY-MM-DD)
        mes_num = int(g['fecha'].split('-')[1]) 
        mes_nombre = nombres_meses[mes_num]
        
        if mes_nombre not in gastos_por_mes:
           # CAMBIAMOS 'items' por 'lista'
           gastos_por_mes[mes_nombre] = {'lista': [], 'total_mes': 0}
    
        # CAMBIAMOS 'items' por 'lista'
        gastos_por_mes[mes_nombre]['lista'].append(g)
        gastos_por_mes[mes_nombre]['total_mes'] += g['precio_total']

        gastos_ordenados = dict(sorted(gastos_por_mes.items(), 
                                      key=lambda x: nombres_meses.index(x[0])))
        
        # 1. Nueva consulta para la gráfica de gastos por categoría
    cursor.execute("SELECT categoria, SUM(cantidad * precio_unitario) FROM gastos GROUP BY categoria")
    gastos_grafica_raw = cursor.fetchall()

        # 2. Preparamos las listas para Chart.js (si no hay gastos, enviamos listas vacías para evitar errores)
    labels_gastos = [row[0] for row in gastos_grafica_raw] if gastos_grafica_raw else []
    data_gastos = [row[1] for row in gastos_grafica_raw] if gastos_grafica_raw else []

        # RECUERDA: Añade 'gastos_por_mes=gastos_por_mes' al render_template de esta función 
    cursor.execute("SELECT COUNT(*) FROM incidencias WHERE solucion = 'Solucionado'"); sol = cursor.fetchone()[0]
    stats_tickets = [sol, pend]; stats_manto = [len(manto)]
    conn.close()
    return render_template('toolbox.html', resumen={'equipos': total_eq, 'pendientes': pend, 'vencidos': venc},
                           tickets=t_procesados, equipos=equipos, celulares=celulares, gastos_por_mes=gastos_ordenados, labels_gastos=labels_gastos, data_gastos=data_gastos, claves=claves, mantenimientos=manto, 
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
    # Capturamos la pestaña actual enviada desde el campo oculto del HTML
    tab_destino = request.form.get('tab_actual', 'tickets') 
    conn = conectar_db()
    conn.execute("INSERT INTO notas (contenido, fecha) VALUES (?,?)", 
                 (request.form['contenido'], datetime.now().strftime('%d/%m %H:%M')))
    conn.commit()
    conn.close()
    # Redirigimos al dashboard pasando el parámetro de la pestaña para que el JS la abra
    return redirect(url_for('dashboard', tab=tab_destino))

@app.route('/eliminar_nota/<int:id>')
@login_required
def eliminar_nota(id):
    # Capturamos la pestaña desde la URL (?tab=...)
    tab_destino = request.args.get('tab', 'tickets')
    conn = conectar_db()
    conn.execute("DELETE FROM notas WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard', tab=tab_destino))

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
    conn = conectar_db()
    
    # Consultas simplificadas para evitar errores de nombres de columnas
    df_tickets = pd.read_sql_query("SELECT id as Folio, equipo as Equipo, usuario as Usuario, problema as Falla, fecha as Fecha FROM incidencias", conn)
    
    # En Inventario usamos '*' para traer todo y evitar el error 'no such column'
    df_inv = pd.read_sql_query("SELECT * FROM inventario", conn)
    
    df_cel = pd.read_sql_query("SELECT * FROM celulares", conn)
    
    # Para gastos, calculamos el total directamente
    df_gastos = pd.read_sql_query("SELECT fecha as Fecha, proveedor as Proveedor, categoria as Categoria, descripcion as Articulo, cantidad as Cant, precio_unitario as Unitario, (cantidad * precio_unitario) as Total FROM gastos", conn)
    
    conn.close()

    # Añadir fila de TOTAL al final de Gastos
    if not df_gastos.empty:
        total_suma = df_gastos['Total'].sum()
        fila_total = pd.DataFrame([['', '', '', 'TOTAL GENERAL:', '', '', total_suma]], columns=df_gastos.columns)
        df_gastos = pd.concat([df_gastos, fila_total], ignore_index=True)

    f = "Reporte_TI_Master.xlsx"
    
    with pd.ExcelWriter(f, engine='openpyxl') as writer:
        df_tickets.to_excel(writer, index=False, sheet_name='Tickets')
        df_inv.to_excel(writer, index=False, sheet_name='Inventario_Hardware')
        df_cel.to_excel(writer, index=False, sheet_name='Inventario_Celulares')
        df_gastos.to_excel(writer, index=False, sheet_name='Reporte_Gastos')
        
        # Auto-ajuste de columnas profesional
        for sheetname in writer.sheets:
            worksheet = writer.sheets[sheetname]
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                worksheet.column_dimensions[column].width = max_length + 2

    return send_file(f, as_attachment=True)

@app.route('/agregar_celular', methods=['POST'])
@login_required
def agregar_celular():
    usuario = request.form.get('usuario')
    marca_modelo = request.form.get('marca_modelo')
    imei = request.form.get('imei')
    numero_tel = request.form.get('numero_tel')
    fecha_asig = request.form.get('fecha_asig')
    comentarios = request.form.get('comentarios')
    ubicacion = request.form.get('ubicacion')

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("""INSERT INTO celulares 
                   (usuario, marca_modelo, imei, numero_tel, fecha_asignacion, ubicacion, comentarios) 
                   VALUES (?, ?, ?, ?, ?, ?)""", 
                   (usuario, marca_modelo, imei, numero_tel, fecha_asig, comentarios))
    conn.commit(); conn.close()
    return redirect(url_for('dashboard', tab='celulares'))

@app.route('/actualizar_celular/<int:id>', methods=['POST'])
@login_required
def actualizar_celular(id):
    # Asegúrate de usar los 'name' que pusiste en los inputs del HTML
    usuario = request.form.get('usuario')
    marca_modelo = request.form.get('marca_modelo')
    imei = request.form.get('imei')
    numero_tel = request.form.get('numero_tel')
    fecha_asignacion = request.form.get('fecha_asig') # Este viene del input name="fecha_asig"
    ubicacion = request.form.get('ubicacion')
    comentarios = request.form.get('comentarios')
    

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("""UPDATE celulares SET 
                   usuario=?, marca_modelo=?, imei=?, numero_tel=?, fecha_asignacion=?, ubicacion=?, comentarios=? 
                   WHERE id=?""", 
                   (usuario, marca_modelo, imei, numero_tel, fecha_asignacion, ubicacion, comentarios, id))
    conn.commit(); conn.close()
    return redirect(url_for('dashboard', tab='celulares'))

@app.route('/eliminar_celular/<int:id>')
@login_required
def eliminar_celular(id):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("DELETE FROM celulares WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('dashboard', tab='celulares'))

@app.route('/agregar_gasto', methods=['POST'])
@login_required
def agregar_gasto():
    fecha = request.form.get('fecha')
    proveedor = request.form.get('proveedor')
    categoria = request.form.get('categoria')
    descripcion = request.form.get('descripcion')
    sku = request.form.get('sku')
    cantidad = int(request.form.get('cantidad', 1))
    precio_unitario = float(request.form.get('precio_unitario', 0))

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("""INSERT INTO gastos 
        (fecha, proveedor, categoria, descripcion, sku, cantidad, precio_unitario) 
        VALUES (?, ?, ?, ?, ?, ?, ?)""", 
        (fecha, proveedor, categoria, descripcion, sku, cantidad, precio_unitario))
    conn.commit(); conn.close()
    
    # Redirigimos y mantenemos la pestaña de gastos abierta
    return redirect(url_for('dashboard', tab='gastos'))

@app.route('/eliminar_gasto/<int:id>')
@login_required
def eliminar_gasto(id):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos WHERE id=?", (id,))
    conn.commit(); conn.close()
    
    # Redirigimos de vuelta a la pestaña de gastos
    return redirect(url_for('dashboard', tab='gastos'))

@app.route('/actualizar_gasto/<int:id>', methods=['POST'])
@login_required
def actualizar_gasto(id):
    fecha = request.form.get('fecha')
    proveedor = request.form.get('proveedor')
    categoria = request.form.get('categoria')
    descripcion = request.form.get('descripcion')
    cantidad = int(request.form.get('cantidad'))
    precio_unitario = float(request.form.get('precio_unitario'))

    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("""UPDATE gastos SET 
                   fecha=?, proveedor=?, categoria=?, descripcion=?, cantidad=?, precio_unitario=? 
                   WHERE id=?""", 
                   (fecha, proveedor, categoria, descripcion, cantidad, precio_unitario, id))
    conn.commit(); conn.close()
    
    return redirect(url_for('dashboard', tab='gastos'))

@app.route('/generar_responsiva_equipo/<int:id>', methods=['POST'])
@login_required
def generar_responsiva_equipo(id):
    # Recibimos los datos editados del modal
    usuario = request.form.get('usuario')
    marca = request.form.get('marca')
    modelo = request.form.get('modelo')
    serie = request.form.get('serie')
    specs = request.form.get('specs')
    comentarios_extra = request.form.get('comentarios', '')
    fecha_actual = datetime.now().strftime("%d/%m/%Y")

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Fecha: {fecha_actual}", 0, 1, 'R')
    
    # Encabezado con formato institucional
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, "RESGUARDO DE EQUIPO TECNOLOGICO", 0, 1, 'C')
    pdf.ln(5)

    # Cuerpo del texto basado en tu archivo Word
    pdf.set_font("Arial", '', 10)
    texto_legal = (
        "Por medio de la presente, hago constar que he recibido el siguiente equipo tecnológico para el "
        "desarrollo de mis funciones y actividades laborales en la empresa Standard Logistics S.A. de C.V.\n\n"
        "Yo como receptor asumo la responsabilidad y el cuidado de dicho equipo, el cual me comprometo a "
        "cuidarlo y mantenerlo en buen estado, siendo utilizado únicamente dentro del ámbito laboral. "
        "No podré hacer uso personal ni abusar de las condiciones del contrato.\n\n"
        "He recibido el equipo de trabajo que se menciona a continuación:"
    )
    pdf.multi_cell(0, 5, texto_legal)
    pdf.ln(5)

    # Tabla de especificaciones
    pdf.set_font("Arial", 'B', 9)
    columnas = [
        {'titulo': 'EQUIPO', 'ancho': 35},
        {'titulo': 'MARCA', 'ancho': 35},
        {'titulo': 'MODELO', 'ancho': 55}, # Más ancho para el modelo
        {'titulo': 'SERIE', 'ancho': 65}
    ]
    
    # Dibujar encabezados
    pdf.set_fill_color(230, 230, 230)
    for col in columnas:
        pdf.cell(col['ancho'], 7, col['titulo'], 1, 0, 'C', True)
    pdf.ln(7)

    # Lógica para fila de datos con ajuste automático (MultiCell)
    pdf.set_font("Arial", '', 8)
    
    # Guardamos la posición actual
    x = pdf.get_x()
    y = pdf.get_y()
    
    # Calculamos la altura necesaria basada en el campo más largo (Modelo o Marca)
    # 5 es la altura base de una línea de texto
    lineas_modelo = len(pdf.multi_cell(55, 5, modelo, split_only=True))
    lineas_marca = len(pdf.multi_cell(35, 5, marca, split_only=True))
    max_lineas = max(lineas_modelo, lineas_marca, 1)
    altura_fila = max_lineas * 5 

    # Dibujamos cada celda usando el alto calculado
    pdf.cell(35, altura_fila, "LAPTOP", 1, 0, 'C')
    
    # Celda con posible multilínea para MARCA
    pos_x = pdf.get_x()
    pdf.multi_cell(35, 5, marca, 1, 'C')
    pdf.set_xy(pos_x + 35, y) # Regresamos a la línea para la siguiente celda
    
    # Celda con posible multilínea para MODELO
    pos_x = pdf.get_x()
    pdf.multi_cell(55, 5, modelo, 1, 'C')
    pdf.set_xy(pos_x + 55, y)
    
    # Celda de SERIE
    pdf.cell(65, altura_fila, serie, 1, 1, 'C')

    # Sección de DETALLES y COMENTARIOS (También con MultiCell)
    y_detalles = pdf.get_y()
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(100, 7, "DETALLES TECNICOS / ESPECIFICACIONES", 1, 0, 'C', True)
    pdf.cell(90, 7, "COMENTARIOS ADICIONALES", 1, 1, 'C', True)

    pdf.set_font("Arial", '', 8)
    # Dibujamos Specs
    x_temp = pdf.get_x()
    pdf.multi_cell(100, 5, specs, 1, 'L')
    y_final_specs = pdf.get_y()
    
    # Dibujamos Comentarios al lado
    pdf.set_xy(x_temp + 100, y_detalles + 7)
    pdf.multi_cell(90, 5, comentarios_extra, 1, 'L')
    y_final_comentarios = pdf.get_y()
    
    # Ajustamos la posición final al punto más bajo para las firmas
    pdf.set_y(max(y_final_specs, y_final_comentarios) + 10)

    # Firmas
    pdf.set_font("Arial", '', 10)
    pdf.ln(10)
    pdf.cell(95, 10, "__________________________", 0, 0, 'C')
    pdf.cell(95, 10, "__________________________", 0, 1, 'C')
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 5, usuario, 0, 0, 'C')
    pdf.cell(95, 5, "Alfredo Valadez", 0, 1, 'C')
    pdf.set_font("Arial", '', 9)
    pdf.cell(95, 5, "Receptor", 0, 0, 'C')
    pdf.cell(95, 5, "IT", 0, 1, 'C')

    response = make_response(pdf.output(dest='S').encode('latin-1', 'replace'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Responsiva_{usuario}.pdf'
    return response

@app.route('/generar_responsiva_celular/<int:id>', methods=['POST'])
@login_required
def generar_responsiva_celular(id):
    # 1. Captura de datos
    usuario = request.form.get('usuario')
    marca_modelo = request.form.get('marca_modelo')
    imei = request.form.get('imei')
    numero = request.form.get('numero')
    ubicacion = request.form.get('ubicacion', 'N/A')
    comentarios_extra = request.form.get('comentarios', '')
    fecha_actual = datetime.now().strftime("%d/%m/%Y")

    pdf = FPDF()
    pdf.add_page()
    
    # Fecha arriba a la derecha
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Monterrey, N.L. a {fecha_actual}", 0, 1, 'R')
    
    # Título Principal [cite: 1]
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, "RESGUARDO DE EQUIPO TECNOLOGICO", 0, 1, 'C')
    pdf.ln(5)

    # 2. Texto Legal unificado (Laptop y Celular) 
    pdf.set_font("Arial", '', 10)
    texto_legal = (
        "Por medio de la presente, hago constar que he recibido el siguiente equipo tecnológico para el "
        "desarrollo de mis funciones y actividades laborales en la empresa Standard Logistics S.A. de C.V.\n\n"
        "Yo como receptor asumo la responsabilidad y el cuidado de dicho equipo, el cual me comprometo a "
        "cuidarlo y mantenerlo en buen estado, siendo utilizado únicamente dentro del ámbito laboral. "
        "No podré hacer uso personal ni abusar de las condiciones del contrato.\n\n"
        "He recibido el equipo de trabajo que se menciona a continuación:"
    )
    pdf.multi_cell(0, 5, texto_legal)
    pdf.ln(5)

    # 3. Tabla de Datos con celdas separadas y alineación perfecta
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 8)
    
    # Encabezados
    pdf.cell(50, 7, "MARCA / MODELO", 1, 0, 'C', True)
    pdf.cell(50, 7, "IMEI", 1, 0, 'C', True)
    pdf.cell(45, 7, "NUMERO", 1, 0, 'C', True)
    pdf.cell(45, 7, "UBICACION", 1, 1, 'C', True)

    pdf.set_font("Arial", '', 8)
    
    # --- LÓGICA ANTI-ESCALÓN ---
    # Guardamos la posición inicial de la fila
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    
    # 1. Calculamos la altura necesaria analizando el texto del modelo
    # Esto simula el texto para saber cuántas líneas ocupará
    lineas_modelo = len(pdf.multi_cell(50, 5, marca_modelo, split_only=True))
    altura_fila = max(lineas_modelo * 5, 10) # Mínimo 10mm para que se vea bien

    # 2. Dibujamos primero los rectángulos vacíos (los bordes) para que queden alineados
    pdf.cell(50, altura_fila, "", 1, 0)
    pdf.cell(50, altura_fila, "", 1, 0)
    pdf.cell(45, altura_fila, "", 1, 0)
    pdf.cell(45, altura_fila, "", 1, 1) 

    # 3. Regresamos el cursor al inicio de la fila para rellenar el texto
    # Usamos multi_cell para el modelo pero sin bordes (border=0) porque ya los dibujamos
    pdf.set_xy(x_start, y_start)
    pdf.multi_cell(50, 5, marca_modelo, 0, 'C')

    # 4. Rellenamos las demás celdas con set_xy exacto
    # Usamos y_start + (altura_fila/2 - 2) para centrar verticalmente el texto simple
    valign = y_start + (altura_fila / 2) - 2

    pdf.set_xy(x_start + 50, valign)
    pdf.cell(50, 0, imei, 0, 0, 'C')
    
    pdf.set_xy(x_start + 100, valign)
    pdf.cell(45, 0, numero, 0, 0, 'C')
    
    pdf.set_xy(x_start + 145, valign)
    pdf.cell(45, 0, ubicacion, 0, 1, 'C')

    # 5. Movemos el cursor al final de la fila para continuar con el documento
    pdf.set_y(y_start + altura_fila)
  
    # 5. Texto de responsabilidad final [cite: 6, 7]
    pdf.ln(5)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(0, 5, "En caso de pérdida o robo, correrán a mi cargo los costos de reparación o reposición. "
                        "Asimismo, aquellos daños que sean causa del mal manejo o imprudencia por mi parte serán "
                        "responsabilidad mía.")

    # 6. Firmas [cite: 8]
    pdf.ln(20)
    pdf.set_font("Arial", '', 10)
    pdf.cell(95, 10, "__________________________", 0, 0, 'C')
    pdf.cell(95, 10, "__________________________", 0, 1, 'C')
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 5, usuario, 0, 0, 'C')
    pdf.cell(95, 5, "Alfredo Valadez", 0, 1, 'C')
    pdf.set_font("Arial", '', 9)
    pdf.cell(95, 5, "Receptor", 0, 0, 'C')
    pdf.cell(95, 5, "IT Department", 0, 1, 'C')

    # Retorno del archivo
    response = make_response(pdf.output(dest='S').encode('latin-1', 'replace'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Responsiva_Celular_{usuario}.pdf'
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)