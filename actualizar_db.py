import sqlite3

def actualizar_db():
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()
    # Crear tabla de Wiki
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wiki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            contenido TEXT NOT NULL,
            fecha_actualizacion TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Tabla Wiki creada con éxito.")

if __name__ == "__main__":
    actualizar_db()