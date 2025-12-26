import sqlite3

def crear_tabla():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    # Creamos la tabla vinculada al nombre del equipo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS software_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_equipo TEXT NOT NULL,
            nombre_software TEXT NOT NULL,
            version TEXT,
            fecha_escaneo TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Tabla software_inventario creada exitosamente.")

if __name__ == "__main__":
    crear_tabla()