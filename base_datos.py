import sqlite3

def crear_base():
    # Se conecta (o crea) el archivo soporte.db
    conexion = sqlite3.connect('soporte.db')
    cursor = conexion.cursor()
    
    # Creamos la tabla de incidencias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo TEXT,
            usuario TEXT,
            problema TEXT,
            solucion TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conexion.commit()
    conexion.close()
    print("¡Base de datos y tabla preparadas con éxito!")

if __name__ == "__main__":
    crear_base()