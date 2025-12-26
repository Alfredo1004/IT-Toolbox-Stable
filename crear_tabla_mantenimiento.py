import sqlite3

def agregar_tabla_mantenimiento():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    # Tabla para registrar los mantenimientos
    cursor.execute('''CREATE TABLE IF NOT EXISTS mantenimiento (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        equipo_id INTEGER,
                        fecha_realizado DATE,
                        tecnico TEXT,
                        descripcion TEXT,
                        proxima_fecha DATE,
                        FOREIGN KEY(equipo_id) REFERENCES inventario(id))''')
    conn.commit()
    conn.close()
    print("✅ Tabla de Mantenimiento creada exitosamente.")

if __name__ == "__main__":
    agregar_tabla_mantenimiento()