import sqlite3
conn = sqlite3.connect('soporte.db') # Ajusta el nombre de tu db
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE incidencias ADD COLUMN fecha_registro TEXT")
    print("✅ Columna fecha_registro añadida.")
except:
    print("⚠️ La columna ya existe.")
conn.commit()
conn.close()