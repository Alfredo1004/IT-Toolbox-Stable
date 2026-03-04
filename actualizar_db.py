import sqlite3

def crear_tabla_historial():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    # Creamos la tabla de historial
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_asignaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_activo TEXT, -- 'Laptop' o 'Celular'
            id_activo INTEGER,
            usuario_anterior TEXT,
            usuario_nuevo TEXT,
            fecha_cambio DATETIME DEFAULT CURRENT_TIMESTAMP,
            detalles TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Tabla 'historial_asignaciones' lista.")

if __name__ == "__main__":
    crear_tabla_historial()