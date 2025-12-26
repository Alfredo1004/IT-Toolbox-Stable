import sqlite3

def migrar():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    # Tabla Inventario
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_activo TEXT,
        nombre_equipo TEXT,
        usuario TEXT,
        especificaciones TEXT,
        estado TEXT DEFAULT 'Operativo'
    )''')
    # Tabla Bóveda (Contraseñas)
    cursor.execute('''CREATE TABLE IF NOT EXISTS boveda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        servicio TEXT,
        usuario_acceso TEXT,
        password_acceso TEXT,
        link_url TEXT
    )''')
    conn.commit()
    conn.close()
    print("✅ Base de datos actualizada a modo Toolbox.")

if __name__ == "__main__":
    migrar()