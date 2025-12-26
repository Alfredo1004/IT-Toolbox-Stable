import sqlite3

def reset_tabla_mantenimiento():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    
    print("--- Reseteando tabla de mantenimiento ---")
    
    # Esto borra TODO el contenido de la tabla mantenimiento
    cursor.execute("DELETE FROM mantenimiento")
    
    # Reinicia el contador de ID para que el próximo registro empiece en 1
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='mantenimiento'")
    
    conn.commit()
    conn.close()
    print("ÉXITO: La tabla está vacía. Reinicia app.py y el contador será 0.")

if __name__ == "__main__":
    reset_tabla_mantenimiento()