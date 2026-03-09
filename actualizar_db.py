import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'soporte.db')

def actualizar_estructura():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Agregar correo al Inventario (para vincular equipos con dueños)
    try:
        cursor.execute("ALTER TABLE inventario ADD COLUMN correo TEXT DEFAULT ''")
        print("✅ Columna 'correo' añadida a tabla 'inventario'")
    except sqlite3.OperationalError:
        print("⚠️ La columna 'correo' ya existe en 'inventario'")

    # 2. Agregar correo_usuario a Incidencias (para guardar el destino del mail)
    try:
        cursor.execute("ALTER TABLE incidencias ADD COLUMN correo_usuario TEXT DEFAULT ''")
        print("✅ Columna 'correo_usuario' añadida a tabla 'incidencias'")
    except sqlite3.OperationalError:
        print("⚠️ La columna 'correo_usuario' ya existe en 'incidencias'")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    actualizar_estructura()