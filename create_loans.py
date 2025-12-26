import sqlite3
conn = sqlite3.connect('soporte.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS prestamos 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   articulo TEXT, 
                   usuario_prestamo TEXT, 
                   fecha_salida TEXT, 
                   fecha_retorno_estimada TEXT,
                   estado TEXT DEFAULT 'Activo')''')
conn.commit()
conn.close()
print("Tabla de Préstamos creada con éxito.")