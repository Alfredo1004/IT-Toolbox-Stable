import sqlite3
conn = sqlite3.connect('soporte.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS notas 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   contenido TEXT, 
                   fecha TEXT)''')
conn.commit()
conn.close()
print("Tabla de Notas creada con éxito.")