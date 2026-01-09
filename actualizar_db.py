import sqlite3

def actualizar_base():
    # USANDO TU NOMBRE DE ARCHIVO LOCAL: soporte.db
    conn = sqlite3.connect('soporte.db')
    cursor = conn.cursor()

    print(f"Conectado a {conn}... Iniciando actualización.")

    # Crear la tabla de celulares con las columnas que pediste
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS celulares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            marca_modelo TEXT NOT NULL,
            imei TEXT UNIQUE,
            numero_tel TEXT,
            fecha_asignacion DATE,
            comentarios TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Tabla 'celulares' creada con éxito en soporte.db")

if __name__ == "__main__":
    actualizar_base()