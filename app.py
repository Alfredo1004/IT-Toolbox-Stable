from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, send_from_directory, flash
from werkzeug.security import check_password_hash
import sqlite3, json, os, pandas as pd
from functools import wraps
from datetime import datetime
from fpdf import FPDF
from flask import make_response
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz
from datetime import datetime
from werkzeug.utils import secure_filename
import os

# Configuración de carpetas
UPLOAD_FOLDER = 'static/uploads/facturas'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

# Configura la zona horaria de México
zona_mx = pytz.timezone('America/Monterrey')

# Configuración de servidor (Gmail ejemplo)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "soporte@strd.com.mx"
EMAIL_PASS = "votzjkyrdotybcsk"  # Tu contraseña de aplicación de 16 letras

def enviar_notificacion(destinatarios, asunto, cuerpo):
    try:
        # Aseguramos que los destinatarios sean una lista única sin duplicados
        lista_final = list(set(destinatarios))
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ", ".join(lista_final)
        msg['Subject'] = asunto

        msg.attach(MIMEText(cuerpo, 'plain'))

        # Usamos un bloque "with" para asegurar que la conexión se cierre SIEMPRE
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS.replace(" ", ""))
            server.sendmail(EMAIL_USER, lista_final, msg.as_string())
            
        print(f"✅ Notificación enviada correctamente a: {lista_final}")
        return True
    except Exception as e:
        print(f"⚠️ Error crítico de correo: {str(e)}")
        return False

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
    data = request.json
    hostname = data.get('equipo')
    usuario = data.get('usuario')
    fecha_hoy = datetime.now(pytz.utc).astimezone(zona_mx).strftime("%Y-%m-%d")
    ahora_full = datetime.now(pytz.utc).astimezone(zona_mx).strftime("%Y-%m-%d %H:%M:%S")
    
    # Formato de diagnóstico para la tabla de Incidencias
    diagnostico_tecnico = f"🧠 {data.get('ram_uso')} | 💾 {data.get('disco_libre')}"
    
    # Lógica de Software Prohibido
    software_instalado = data.get('software', [])
    prohibidos = ["TeamViewer", "AnyDesk", "AeroAdmin", "Torrent", "Steam", "Spotify"]
    hallazgos = [s['nombre'] for s in software_instalado if any(p in s['nombre'] for p in prohibidos)]
    
    if hallazgos:
        diagnostico_tecnico = f"🚨 PROHIBIDO: {', '.join(hallazgos)} | " + diagnostico_tecnico

    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("SELECT correo FROM inventario WHERE nombre_equipo = ?", (hostname,))
    equipo_existente = cursor.fetchone()

    # Combinamos RAM, Disco y Procesador para las Especificaciones
    specs = f"RAM: {data.get('ram_total')} | Disco: {data.get('disco_total')} | CPU: {data.get('procesador')}"

    if not equipo_existente:
        # INSERT con los nombres de campos que envía el nuevo agente
        cursor.execute("""
            INSERT INTO inventario 
            (nombre_equipo, usuario, especificaciones, fecha_asignacion, ip_address, mac_address, n_serie, modelo, marca, correo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hostname, usuario, specs, 
            fecha_hoy, data.get('ip'), data.get('mac'), data.get('serie'), data.get('modelo'), data.get('marca'), ""
        ))
        conn.commit()
        correo_destino = ""
    else:
        # UPDATE: Si ya existe, actualizamos los datos técnicos por si hubo un upgrade (RAM, IP, etc)
        cursor.execute("""
            UPDATE inventario SET 
            ip_address=?, mac_address=?, especificaciones=?, usuario=? 
            WHERE nombre_equipo=?
        """, (data.get('ip'), data.get('mac'), specs, usuario, hostname))
        correo_destino = equipo_existente[0]

    # Crear la Incidencia
    cursor.execute("""
        INSERT INTO incidencias 
        (usuario, equipo, problema, solucion, falla_humana, fecha_registro, correo_usuario)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (usuario, hostname, diagnostico_tecnico, 'Pendiente', '-', ahora_full, correo_destino))
    
    conn.commit()
    conn.close()
    return {"status": "success"}, 200

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
    
    # --- NUEVAS CONSULTAS DE STOCK ---
    # Contar Laptops en Stock (que el usuario sea 'STOCK' o 'DISPONIBLE')
    cursor.execute("SELECT COUNT(*) FROM inventario WHERE usuario LIKE '%STOCK%' OR usuario LIKE '%DISPONIBLE%'")
    stock_laptops = cursor.fetchone()[0]

    # Contar Celulares en Stock
    cursor.execute("SELECT COUNT(*) FROM celulares WHERE usuario LIKE '%STOCK%' OR usuario LIKE '%DISPONIBLE%'")
    stock_celulares = cursor.fetchone()[0]

    # Consulta para agrupar laptops por ubicación
    cursor.execute("SELECT ubicacion, COUNT(*) FROM inventario GROUP BY ubicacion")
    loc_laptops = dict(cursor.fetchall())

    # Consulta para agrupar celulares por ubicación
    cursor.execute("SELECT ubicacion, COUNT(*) FROM celulares GROUP BY ubicacion")
    loc_celulares = dict(cursor.fetchall())

    # Unificamos todas las ubicaciones únicas encontradas
    todas_ubicaciones = list(set(list(loc_laptops.keys()) + list(loc_celulares.keys())))
    
    # Preparamos las listas para la gráfica
    labels_loc = [u if u else "Sin Asignar" for u in todas_ubicaciones]
    data_laptops = [loc_laptops.get(u, 0) for u in todas_ubicaciones]
    data_celulares = [loc_celulares.get(u, 0) for u in todas_ubicaciones]

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

   # 1. CONSULTAR EL HISTORIAL (Debe estar antes de conn.close())
    cursor.execute("SELECT * FROM historial_asignaciones ORDER BY fecha_cambio DESC")
    historial_raw = cursor.fetchall()
    historial = [dict(row) for row in historial_raw] 

    # 2. CONTEOS PARA GRÁFICAS (Debe estar antes de conn.close())
    cursor.execute("SELECT COUNT(*) FROM incidencias WHERE solucion = 'Solucionado'")
    sol = cursor.fetchone()[0]
    stats_tickets = [sol, pend]
    stats_manto = [len(manto)]

    # 3. AHORA SÍ, CERRAR LA CONEXIÓN
    conn.close() 

    # 4. RETORNAR EL TEMPLATE
    return render_template('toolbox.html', 
                           resumen={'equipos': total_eq, 'pendientes': pend, 'vencidos': venc},
                           tickets=t_procesados, equipos=equipos, celulares=celulares, 
                           gastos_por_mes=gastos_ordenados, labels_gastos=labels_gastos, 
                           data_gastos=data_gastos, claves=claves, mantenimientos=manto, 
                           notas=notas, prestamos=prestamos, wiki=wiki, fecha_actual=hoy, 
                           stats_tickets=stats_tickets, stats_manto=stats_manto, 
                           pendientes_count=pend, labels_loc=labels_loc, 
                           data_laptops=data_laptops, data_celulares=data_celulares, 
                           historial=historial, stock_laptops=stock_laptops, 
                           stock_celulares=stock_celulares,)
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
    estado = request.form.get('estado')
    falla_manual = request.form.get('falla_humana')
    solucion = request.form.get('comentario')
    
    ahora = datetime.now(pytz.utc).astimezone(zona_mx).strftime("%Y-%m-%d %H:%M:%S")

    conn = conectar_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Guardar cambios en BD
    cursor.execute("""
        UPDATE incidencias 
        SET solucion=?, falla_humana=?, comentarios=? 
        WHERE id=?
    """, (estado, falla_manual, solucion, id))
    conn.commit()

    # 2. Buscar correo actualizado en Inventario
    cursor.execute("""
        SELECT i.usuario, i.equipo, inv.correo 
        FROM incidencias i
        LEFT JOIN inventario inv ON i.equipo = inv.nombre_equipo
        WHERE i.id = ?
    """, (id,))
    t = cursor.fetchone()
    conn.close()

    if t:
        nombre_usuario = t['usuario']
        equipo_usuario = t['equipo']
        correo_destino = t['correo']
        
        asunto = f"Actualización de Ticket #{id} - {equipo_usuario} [{estado}]"
        
        cuerpo = f"""Hola {nombre_usuario},

Se ha registrado una actualización en tu reporte técnico:

DETALLES DEL TICKET:
--------------------------------------------------
Folio: #{id}
Equipo: {equipo_usuario}
Estado: {estado}
Fecha: {ahora}

DIAGNÓSTICO TÉCNICO: {falla_manual}
NOTAS DE TI: {solucion}
--------------------------------------------------

Atentamente,
Departamento de Soporte TI
"""

        # Gerente siempre recibe copia
        lista_destinatarios = ["alfredo.valadez@strd.com.mx"]
        
        # Validar si el usuario tiene correo en el inventario
        if correo_destino and "@" in str(correo_destino):
            lista_destinatarios.append(correo_destino.strip())
        
        # Disparar envío
        enviar_notificacion(lista_destinatarios, asunto, cuerpo)

    flash(f"Ticket #{id} actualizado con éxito.", "success")
    return redirect(url_for('dashboard'))

@app.route('/eliminar_ticket/<int:id>')
@login_required
def eliminar_ticket(id):
    conn = conectar_db(); conn.execute("DELETE FROM incidencias WHERE id=?", (id,)); conn.commit(); conn.close(); return redirect('/#tickets')

@app.route('/actualizar_equipo/<int:id>', methods=['POST'])
@login_required
def actualizar_equipo(id):
    nuevo_usuario = request.form['usuario']
    correo = request.form.get('correo', '') # 1. Recibimos el correo
    
    conn = conectar_db(); cursor = conn.cursor()
    
    cursor.execute("SELECT usuario FROM inventario WHERE id=?", (id,))
    fila = cursor.fetchone()
    usuario_anterior = fila[0] if fila else "N/A"

    if usuario_anterior != nuevo_usuario:
        cursor.execute("""INSERT INTO historial_asignaciones 
            (tipo_activo, id_activo, usuario_anterior, usuario_nuevo, detalles) 
            VALUES (?, ?, ?, ?, ?)""", 
            ('Laptop', id, usuario_anterior, nuevo_usuario, 'Cambio de usuario en Inventario'))

    # 2. SE AGREGÓ correo=? y la variable correo al final
    cursor.execute("""UPDATE inventario SET nombre_equipo=?, usuario=?, n_serie=?, marca=?, 
                      modelo=?, ubicacion=?, fecha_asignacion=?, ip_address=?, tipo_red=?, 
                      especificaciones=?, correo=? WHERE id=?""", 
                   (request.form['nombre'], nuevo_usuario, request.form['serie'], request.form['marca'], 
                    request.form['modelo'], request.form['ubicacion'], request.form['fecha_asig'], 
                    request.form['ip'], request.form['red'], request.form['specs'], correo, id))
    
    conn.commit(); conn.close()
    return redirect('/#inventario')

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
    equipo = request.form['equipo_nombre']
    conn = conectar_db(); cursor = conn.cursor()
    
    # Buscar correo en inventario
    cursor.execute("SELECT correo FROM inventario WHERE nombre_equipo = ?", (equipo,))
    res = cursor.fetchone()
    correo_destino = res['correo'] if res else ""
    
    # Insertar el ticket manual con el correo encontrado
    cursor.execute("""INSERT INTO incidencias 
        (equipo, usuario, problema, solucion, fecha_registro, correo_usuario) 
        VALUES (?,?,?,?,?,?)""", 
        (equipo, request.form['usuario'], request.form['problema'], 'Pendiente', datetime.now().strftime('%Y-%m-%d %H:%M'), correo_destino))
    
    conn.commit(); conn.close()
    return redirect('/#tickets')

@app.route('/agregar_equipo', methods=['POST'])
@login_required
def agregar_equipo():
    correo = request.form.get('correo', '')
    conn = conectar_db()
    
    # Asegúrate de que hay 11 columnas y 11 signos de interrogación
    conn.execute("""INSERT INTO inventario 
        (nombre_equipo, usuario, especificaciones, ip_address, tipo_red, n_serie, marca, modelo, ubicacion, fecha_asignacion, correo) 
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", 
        (request.form['nombre'], request.form['usuario'], request.form['specs'], request.form['ip'], request.form['red'], request.form['serie'], request.form['marca'], request.form['modelo'], request.form['ubicacion'], request.form['fecha_asig'], correo))
    
    conn.commit(); conn.close()
    return redirect('/#inventario')

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
    
    # 1. Consultas base
    df_tickets = pd.read_sql_query("""
        SELECT 
            id as Folio, 
            equipo as Equipo, 
            usuario as Usuario, 
            falla_humana as Falla, 
            comentarios as Solucion,
            solucion as Estado,
            fecha_registro as Fecha 
        FROM incidencias
    """, conn)
    df_inv = pd.read_sql_query("SELECT nombre_equipo, usuario, marca, modelo, n_serie, ubicacion, especificaciones FROM inventario", conn)
    df_cel = pd.read_sql_query("SELECT usuario, marca_modelo, imei, numero_tel, ubicacion FROM celulares", conn)
    df_gastos = pd.read_sql_query("SELECT fecha, proveedor, categoria, descripcion, cantidad, precio_unitario, (cantidad * precio_unitario) as Total FROM gastos", conn)
    
    # --- 2. LÓGICA DE LA QUINTA HOJA (RESUMEN EJECUTIVO) ---
    # Conteos por ubicación
    resumen_loc = df_inv.groupby('ubicacion').size().reset_index(name='Cant_Laptops')
    resumen_cel = df_cel.groupby('ubicacion').size().reset_index(name='Cant_Celulares')
    
    # Unir ambos conteos en una sola tabla de resumen
    df_resumen = pd.merge(resumen_loc, resumen_cel, on='ubicacion', how='outer').fillna(0)
    
    # Añadir métricas rápidas
    metricas = pd.DataFrame({
        'Concepto': ['Total Equipos Laptop/PC', 'Total Celulares', 'Tickets Pendientes', 'Inversion Total Gastos'],
        'Valor': [len(df_inv), len(df_cel), len(df_tickets), df_gastos['Total'].sum()]
    })
    
    conn.close()

    f = "Reporte_TI_Master.xlsx"
    with pd.ExcelWriter(f, engine='openpyxl') as writer:
        # Pestaña Nueva (La ponemos primero para que sea lo primero que vean)
        df_resumen.to_excel(writer, index=False, sheet_name='Resumen_Ubicaciones')
        metricas.to_excel(writer, index=False, sheet_name='Metricas_Generales', startrow=len(df_resumen) + 3)
        
        # Pestañas existentes
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
                    if cell.value: max_length = max(max_length, len(str(cell.value)))
                worksheet.column_dimensions[column].width = max_length + 2

    return send_file(f, as_attachment=True)

@app.route('/agregar_celular', methods=['POST'])
def agregar_celular():
    # 1. Recibimos los 7 campos exactamente como se llaman en el HTML
    usuario = request.form.get('usuario') or 'STOCK'
    marca_modelo = request.form.get('marca_modelo')
    numero_tel = request.form.get('numero_tel')
    imei = request.form.get('imei')
    fecha_asig = request.form.get('fecha_asig')
    ubicacion = request.form.get('ubicacion')
    comentarios = request.form.get('comentarios')

    conn = conectar_db()
    cursor = conn.cursor()
    
    # 2. Insertamos los 7 valores con 7 signos de interrogación (?, ?, ?, ?, ?, ?, ?)
    cursor.execute("""
        INSERT INTO celulares 
        (usuario, marca_modelo, numero_tel, imei, fecha_asignacion, ubicacion, comentarios) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (usuario, marca_modelo, numero_tel, imei, fecha_asig, ubicacion, comentarios))
    
    # 3. Opcional pero recomendado: Registrar en el historial que se ingresó un equipo nuevo
    id_nuevo = cursor.lastrowid
    cursor.execute("""
        INSERT INTO historial_asignaciones 
        (tipo_activo, id_activo, usuario_anterior, usuario_nuevo, detalles) 
        VALUES (?, ?, ?, ?, ?)
    """, ('Celular', id_nuevo, 'NUEVO INGRESO', usuario, 'Alta de equipo móvil en sistema'))

    conn.commit()
    conn.close()
    
    # Retornamos a la pestaña de celulares
    return redirect(url_for('dashboard', tab='celulares'))

@app.route('/actualizar_celular/<int:id>', methods=['POST'])
@login_required
def actualizar_celular(id):
    nuevo_usuario = request.form.get('usuario')
    marca_modelo = request.form.get('marca_modelo')
    imei = request.form.get('imei')
    numero_tel = request.form.get('numero_tel')
    fecha_asignacion = request.form.get('fecha_asig')
    ubicacion = request.form.get('ubicacion')
    comentarios = request.form.get('comentarios')
    
    conn = conectar_db(); cursor = conn.cursor()
    
    # 1. Consultar el antiguo dueño
    cursor.execute("SELECT usuario FROM celulares WHERE id=?", (id,))
    res = cursor.fetchone()
    antiguo = res[0] if res else "Desconocido"

    # 2. Registrar historial si hay cambio
    if antiguo != nuevo_usuario:
        cursor.execute("""INSERT INTO historial_asignaciones 
            (tipo_activo, id_activo, usuario_anterior, usuario_nuevo, detalles) 
            VALUES (?, ?, ?, ?, ?)""", 
            ('Celular', id, antiguo, nuevo_usuario, 'Cambio de equipo móvil'))

    # 3. Actualizar datos del celular
    cursor.execute("""UPDATE celulares SET 
                    usuario=?, marca_modelo=?, imei=?, numero_tel=?, fecha_asignacion=?, ubicacion=?, comentarios=? 
                    WHERE id=?""", 
                    (nuevo_usuario, marca_modelo, imei, numero_tel, fecha_asignacion, ubicacion, comentarios, id))
    
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

    # Manejo del archivo PDF/Imagen
    factura_file = request.files.get('factura')
    nombre_archivo = "" # Por defecto vacío si no suben nada

    if factura_file and factura_file.filename != '':
        extension = factura_file.filename.rsplit('.', 1)[1].lower()
        nuevo_nombre = f"factura_{fecha}_{proveedor.replace(' ', '_')}.{extension}"
        nombre_archivo = secure_filename(nuevo_nombre)
        factura_file.save(os.path.join(UPLOAD_FOLDER, nombre_archivo))

    conn = conectar_db(); cursor = conn.cursor()
    # IMPORTANTE: Asegúrate de que el INSERT incluya 'factura_pdf'
    cursor.execute("""INSERT INTO gastos 
        (fecha, proveedor, categoria, descripcion, sku, cantidad, precio_unitario, factura_pdf) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
        (fecha, proveedor, categoria, descripcion, sku, cantidad, precio_unitario, nombre_archivo)) # <--- Aquí faltaba 'nombre_archivo'
    conn.commit(); conn.close()
    flash("✅ Gasto registrado con éxito.", "success")
    return redirect(url_for('dashboard', tab='gastos'))

@app.route('/eliminar_gasto/<int:id>')
@login_required
def eliminar_gasto(id):
    conn = conectar_db(); cursor = conn.cursor()
    
    # Buscamos si el gasto tiene un archivo asociado para borrarlo del disco
    cursor.execute("SELECT factura_pdf FROM gastos WHERE id=?", (id,))
    res = cursor.fetchone()
    if res and res['factura_pdf']:
        ruta_archivo = os.path.join(UPLOAD_FOLDER, res['factura_pdf'])
        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo) # Borra el archivo físico
            
    cursor.execute("DELETE FROM gastos WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('dashboard', tab='gastos'))

@app.route('/borrar_factura_gasto/<int:id>')
@login_required
def borrar_factura_gasto(id):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT factura_pdf FROM gastos WHERE id=?", (id,))
    res = cursor.fetchone()
    if res and res['factura_pdf']:
        ruta = os.path.join(UPLOAD_FOLDER, res['factura_pdf'])
        if os.path.exists(ruta): 
            os.remove(ruta) # Borrado físico
            flash("🗑️ Archivo de factura eliminado permanentemente.", "warning")
    
    cursor.execute("UPDATE gastos SET factura_pdf='' WHERE id=?", (id,))
    conn.commit(); conn.close()
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
    factura_file = request.files.get('factura') # Lógica para subir nueva factura en edición

    conn = conectar_db(); cursor = conn.cursor()

    if factura_file and factura_file.filename != '':
        # Si suben uno nuevo, lo guardamos y actualizamos la columna
        extension = factura_file.filename.rsplit('.', 1)[1].lower()
        nombre_archivo = secure_filename(f"factura_{fecha}_{proveedor.replace(' ', '_')}.{extension}")
        factura_file.save(os.path.join(UPLOAD_FOLDER, nombre_archivo))
        
        cursor.execute("""UPDATE gastos SET fecha=?, proveedor=?, categoria=?, descripcion=?, 
                       cantidad=?, precio_unitario=?, factura_pdf=? WHERE id=?""", 
                       (fecha, proveedor, categoria, descripcion, cantidad, precio_unitario, nombre_archivo, id))
    else:
        # Si no suben nada, solo actualizamos el texto
        cursor.execute("""UPDATE gastos SET fecha=?, proveedor=?, categoria=?, descripcion=?, 
                       cantidad=?, precio_unitario=? WHERE id=?""", 
                       (fecha, proveedor, categoria, descripcion, cantidad, precio_unitario, id))
    
    conn.commit(); conn.close()
    flash("🔄 Gasto actualizado correctamente.", "info")
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