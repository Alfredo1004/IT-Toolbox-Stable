import sqlite3

def actualizar_base():
    # Conexión a tu base local
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()

    print("Actualizando base de datos para el módulo de gastos...")

    # Creamos la tabla de gastos con los campos de tu Excel
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            proveedor TEXT,
            categoria TEXT,
            descripcion TEXT NOT NULL,
            sku TEXT,
            cantidad INTEGER DEFAULT 1,
            precio_unitario REAL DEFAULT 0,
            comentarios TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Tabla 'gastos' creada exitosamente.")

if __name__ == "__main__":
    actualizar_base()