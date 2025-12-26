import psutil
import platform
import socket

def ejecutar_diagnostico():
    print("========================================")
    print("   REPORTE DE SOPORTE TÉCNICO IT")
    print("========================================")
    
    # 1. Información Básica
    print(f"[+] Equipo: {platform.node()}")
    print(f"[+] Sistema: {platform.system()} {platform.release()}")
    
    # 2. Estado del Hardware
    ram = psutil.virtual_memory()
    disco = psutil.disk_usage('C:')
    print(f"[+] RAM en uso: {ram.percent}%")
    print(f"[+] Espacio libre en C: {disco.free // (2**30)} GB")
    
    # 3. Verificación de Red (Una de tus funciones clave)
    try:
        # Intentamos conectar a Google para ver si hay internet
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        print("[+] Conectividad Internet: OK")
    except OSError:
        print("[!] Conectividad Internet: SIN ACCESO")

    print("========================================")

if __name__ == "__main__":
    ejecutar_diagnostico()