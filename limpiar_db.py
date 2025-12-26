import sqlite3

def limpiar_mantenimientos():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    
    print("--- Iniciando limpieza de registros de mantenimiento ---")
    
    # 1. Ver cuántos registros hay actualmente
    cursor.execute("SELECT COUNT(*) FROM mantenimiento")
    total_antes = cursor.fetchone()[0]
    print(f"Registros totales encontrados: {total_antes}")

    # 2. Eliminar registros que tengan fechas vacías, guiones o nulos 
    # que estén causando el error del contador
    cursor.execute("""
        DELETE FROM mantenimiento 
        WHERE proxima_fecha IS NULL 
        OR proxima_fecha = '' 
        OR proxima_fecha = '-'
        OR proxima_fecha = 'None'
    """)
    
    # 3. Eliminar mantenimientos muy antiguos si lo deseas (opcional)
    # Por ahora solo eliminaremos los que tienen formato incorrecto
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM mantenimiento")
    total_despues = cursor.fetchone()[0]
    
    print(f"Limpieza completada.")
    print(f"Registros eliminados por formato incorrecto: {total_antes - total_despues}")
    print(f"Registros válidos restantes: {total_despues}")
    
    conn.close()
    print("--- Base de datos lista. Reinicia app.py y verifica la tarjeta ---")

if __name__ == "__main__":
    limpiar_mantenimientos()