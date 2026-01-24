"""
BOSS IR-2 Manager Tool
Permette di salvare e caricare preset completi su file JSON.
"""
import json
import time
import mido
from datetime import datetime
from .control import BossIR2, PARAMETERS

class BossIR2Manager(BossIR2):
    def send_rq1(self, addr, size=1):
        """Invia Data Request (RQ1)"""
        # Header: F0 41 10 01 05 09 11
        msg = [0x41, 0x10, 0x01, 0x05, 0x09, 0x11]
        
        # Address + Size
        # Size è su 4 bytes
        # Assumiamo size piccolo (<128) per ora
        payload = addr + [0, 0, 0, size]
        msg.extend(payload)
        
        # Checksum
        msg.append(self._checksum(payload))
        
        with mido.open_output(self.output_name) as out:
            out.send(mido.Message('sysex', data=msg))

    def read_param(self, name, timeout=1.0):
        if name not in PARAMETERS:
            raise ValueError(f"Parametro sconosciuto: {name}")
            
        addr = PARAMETERS[name]['addr']
        self.send_rq1(addr)
        
        start = time.time()
        with mido.open_input(self.input_name) as inp:
            while time.time() - start < timeout:
                msg = inp.poll()
                if msg and msg.type == 'sysex' and len(msg.data) > 10:
                    # Verifica che sia DT1 (0x12) e indirizzo corrisponda
                    if msg.data[5] == 0x12:
                        recv_addr = list(msg.data[6:10])
                        if recv_addr == addr:
                            val = msg.data[10]
                            return val
                time.sleep(0.01)
        return None

    def dump_preset(self):
        """Legge TUTTI i parametri noti"""
        print("💾 Inizio backup preset...")
        preset = {
            "device": "BOSS IR-2",
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        for name in PARAMETERS:
            # Retry logic: prova fino a 3 volte per parametro
            val = None
            for attempt in range(3):
                val = self.read_param(name, timeout=1.5)
                if val is not None:
                    break
                print(f"  ⚠️ Retry {attempt+1} per {name}...")
                time.sleep(0.2)
            
            if val is not None:
                # Converti enum in stringa se necessario
                if PARAMETERS[name]['type'] == 'enum':
                    val_str = PARAMETERS[name]['values'][val]
                    print(f"  • {name}: {val_str} ({val})")
                    preset["data"][name] = val_str
                else:
                    print(f"  • {name}: {val}")
                    preset["data"][name] = val
            else:
                print(f"  ❌ Errore lettura {name} dopo 3 tentativi")
            
            time.sleep(0.15) # Aumentato delay tra comandi (era 0.05)
            
        return preset

    def load_preset(self, filepath):
        """Carica preset da file"""
        with open(filepath, 'r') as f:
            preset = json.load(f)
            
        print(f"📂 Caricamento preset del {preset['timestamp']}...")
        
        for name, value in preset["data"].items():
            try:
                self.set_param(name, value)
                time.sleep(0.05) # Pausa tra comandi
            except Exception as e:
                print(f"  ❌ Errore impostando {name}: {e}")
                
        print("✅ Caricamento completato!")

if __name__ == "__main__":
    import mido
    
    try:
        manager = BossIR2Manager()
        
        while True:
            print("\nBOSS IR-2 MANAGER")
            print("1. 💾 Backup preset corrente (Dump)")
            print("2. 📂 Carica preset (Load)")
            print("3. ❌ Esci")
            
            choice = input("\nScelta: ").strip()
            
            if choice == "1":
                preset = manager.dump_preset()
                filename = f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(preset, f, indent=2)
                print(f"\n✅ Salvato in: {filename}")
                
            elif choice == "2":
                import glob
                files = glob.glob("preset_*.json")
                if not files:
                    print("⚠️ Nessun preset trovato!")
                    continue
                    
                print("\nPreset disponibili:")
                for i, f in enumerate(files):
                    print(f"  {i+1}. {f}")
                
                try:
                    idx = int(input("\nQuale file caricare? (numero): ")) - 1
                    if 0 <= idx < len(files):
                        manager.load_preset(files[idx])
                except ValueError:
                    pass
                    
            elif choice == "3":
                break
                
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        input("Premi Invio per uscire...")
