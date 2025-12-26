import sqlite3
conn = sqlite3.connect('soporte.db')
cursor = conn.cursor()

# 1. Eliminar mantenimientos que NO tienen un equipo asociado en el inventario (Registros huérfanos)
cursor.execute("""
    DELETE FROM mantenimiento 
    WHERE equipo_id NOT IN (SELECT id FROM inventario)
""")
huerfanos = cursor.rowcount

# 2. Eliminar registros con fechas inválidas o vacías
cursor.execute("DELETE FROM mantenimiento WHERE proxima_fecha IS NULL OR proxima_fecha = ''")
invalidos = cursor.rowcount

print(f"Limpieza completada:")
print(f"- Registros huérfanos eliminados: {huerfanos}")
print(f"- Registros con fecha inválida eliminados: {invalidos}")

conn.commit()
conn.close()