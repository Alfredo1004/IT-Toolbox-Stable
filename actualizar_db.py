import sqlite3

conn = sqlite3.connect('soporte.db')
cursor = conn.cursor()
try:
    # Añadimos la columna para el diagnóstico humano
    cursor.execute("ALTER TABLE incidencias ADD COLUMN falla_humana TEXT DEFAULT '-'")
    print("✅ Columna falla_humana añadida.")
except:
    print("⚠️ La columna ya existe.")
conn.commit()
conn.close()