import sqlite3
conn = sqlite3.connect('soporte.db')
cursor = conn.cursor()

# Borra registros basura que tengan la fecha vacía o no tengan ID de equipo
cursor.execute("DELETE FROM mantenimiento WHERE proxima_fecha IS NULL OR proxima_fecha = '' OR equipo_id IS NULL")

print(f"Registros limpiados: {cursor.rowcount}")
conn.commit()
conn.close()