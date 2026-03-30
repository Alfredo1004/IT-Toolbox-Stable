import requests, psutil, socket, os, subprocess, sys, ctypes, winreg, time
from datetime import datetime

URL_DESTINO = "https://AlfredoV.pythonanywhere.com/reporte_agente"

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def clean_text(text):
    # EL ESCUDO: Remueve emojis, marcas registradas y caracteres raros que rompen las bases de datos
    if not text: return "N/A"
    try:
        # Codifica a ASCII (ignora lo raro) y decodifica a texto limpio
        return str(text).encode('ascii', 'ignore').decode('ascii').strip()
    except:
        return "N/A"

def get_hw_info(tipo):
    cmds_cim = {
        "serial": "(Get-CimInstance Win32_BIOS).SerialNumber",
        "modelo": "(Get-CimInstance Win32_ComputerSystem).Model",
        "marca": "(Get-CimInstance Win32_ComputerSystem).Manufacturer",
        "cpu": "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"
    }
    try:
        cmd = f'powershell -NoProfile -Command "{cmds_cim[tipo]}"'
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, creationflags=0x08000000).decode(errors='ignore').strip()
        if res and res.lower() not in ["", "to be filled by o.e.m.", "default string", "n/a"]:
            return clean_text(res)
    except: pass
    return "N/A"

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "0.0.0.0"

def get_mac_address():
    try:
        import uuid
        return ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8*6, 8)][::-1]).upper()
    except: return "N/A"

def get_installed_software():
    software_list = []
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    # Llaves maestras
    access_modes = [winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY]
    
    for root, path in paths:
        for access in access_modes:
            try:
                key = winreg.OpenKey(root, path, 0, access)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name, 0, access)
                        try:
                            name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                            name_str = clean_text(name)
                            # Filtro: más de 2 letras y que no sea una actualización de Windows
                            if name_str and len(name_str) > 2 and "Update" not in name_str and "KB" not in name_str:
                                try: 
                                    version, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                                    ver_str = clean_text(version)
                                except: ver_str = "N/A"
                                software_list.append({"nombre": name_str[:100], "version": ver_str[:50]})
                        except: pass
                        finally: winreg.CloseKey(subkey)
                    except: continue
                winreg.CloseKey(key)
            except: continue

    unique_sw = {f"{s['nombre']}-{s['version']}": s for s in software_list}
    return list(unique_sw.values())

def enviar_reporte():
    try:
        time.sleep(1)
        hostname = socket.gethostname()
        lista_sw = get_installed_software()
        
        # 🚨 LA PRUEBA DEFINITIVA: Te avisará localmente cuántos programas leyó 🚨
        ctypes.windll.user32.MessageBoxW(0, f"Diagnóstico Interno:\n\nSe encontraron {len(lista_sw)} programas en la PC.\n\nEnviando al servidor...", "Depuración IT Toolbox", 0x40)

        payload = {
            "equipo": hostname,
            "usuario": os.getlogin(),
            "ip": get_ip_address(),
            "mac": get_mac_address(),
            "serie": get_hw_info("serial"),
            "modelo": get_hw_info("modelo"),
            "marca": get_hw_info("marca"),
            "procesador": get_hw_info("cpu"),
            "ram_total": f"{round(psutil.virtual_memory().total / (1024**3))}GB",
            "disco_total": f"{round(psutil.disk_usage('C:').total / (1024**3))}GB",
            "ram_uso": f"{psutil.virtual_memory().percent}%",
            "disco_libre": f"{psutil.disk_usage('C:').free // (1024**3)}GB Libres",
            "software": lista_sw
        }
        
        # Hacemos el envío
        resp = requests.post(URL_DESTINO, json=payload, timeout=20)
        
        # Analizamos la respuesta de PythonAnywhere
        if resp.status_code == 200:
            ctypes.windll.user32.MessageBoxW(0, f"✅ Auditoría completada con éxito.\nEl servidor aceptó los datos correctamente.", "IT Toolbox Pro", 0x40)
        else:
            ctypes.windll.user32.MessageBoxW(0, f"⚠️ Error del Servidor: {resp.status_code}\n\nEl Agente hizo su trabajo, pero el Servidor Web (PythonAnywhere) se estrelló y no quiso guardar los datos.", "IT Toolbox Pro", 0x10)
            
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"⚠️ Error de Conexión o Python: {str(e)}", "IT Toolbox Pro", 0x10)

if __name__ == "__main__":
    if is_admin():
        enviar_reporte()
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)