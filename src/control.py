"""
BOSS IR-2 Control Library
"""
import mido
import time

# Costanti Protocollo
ROLAND_ID = 0x41
DEVICE_ID = 0x10
MODEL_ID = [0x00, 0x00, 0x09, 0x05]  # Scoperto dall'Identity Response originale
# Nota: La cattura ha mostrato 01 05 09, ma l'header standard Roland usa una struttura specifica.
# Dalle catture: F0 41 10 01 05 09 12 ...
# Header catturato: 41 10 01 05 09
# Quindi Model ID per SysEx è: 01 05 09

CMD_DT1 = 0x12  # Data Set (Write)
CMD_RQ1 = 0x11  # Data Request (Read)

# Mappa Parametri (dagli indirizzi scoperti)
PARAMETERS = {
    "BASS":     {"addr": [0x20, 0x00, 0x00, 0x00], "type": "range", "min": 0, "max": 127},
    "MIDDLE":   {"addr": [0x20, 0x00, 0x00, 0x01], "type": "range", "min": 0, "max": 127},
    "TREBLE":   {"addr": [0x20, 0x00, 0x00, 0x02], "type": "range", "min": 0, "max": 127},
    "GAIN":     {"addr": [0x20, 0x00, 0x00, 0x04], "type": "range", "min": 0, "max": 127},
    "AMBIENCE": {"addr": [0x20, 0x00, 0x00, 0x05], "type": "range", "min": 0, "max": 127},
    "LEVEL":    {"addr": [0x20, 0x00, 0x00, 0x03], "type": "range", "min": 0, "max": 127}, # Corretto!
    
    # Parametro Discreto
    "MODEL":    {"addr": [0x20, 0x00, 0x00, 0x06], "type": "enum", "values": [
        "CLEAN", "TWIN", "TWEED", "DIAMOND", "CRUNCH", 
        "BRIT", "HI-GAIN", "SLDN", "BROWN", "MODDED", "RFIER"
    ]}
}

class BossIR2:
    def __init__(self, port_name=None):
        self.input_name = port_name
        self.output_name = port_name
        
        # Auto-detect se non specificato
        if not port_name:
            for name in mido.get_input_names():
                if 'BOSS' in name.upper() or 'IR-2' in name.upper():
                    self.input_name = name
                    break
            for name in mido.get_output_names():
                if 'BOSS' in name.upper() or 'IR-2' in name.upper():
                    self.output_name = name
                    break
        
        if not self.input_name or not self.output_name:
            raise Exception("BOSS IR-2 non trovato!")
            
        print(f"🎸 BOSS IR-2 connesso su: {self.input_name}")

    def _checksum(self, data):
        return (128 - (sum(data) % 128)) & 0x7F

    def send_sysex(self, addr, value):
        """Invia comando DT1 (Write)"""
        # Header: F0 41 10 01 05 09 12
        msg = [0x41, 0x10, 0x01, 0x05, 0x09, 0x12]
        
        # Address + Value
        payload = addr + [value]
        msg.extend(payload)
        
        # Checksum
        msg.append(self._checksum(payload))
        
        # Invia
        with mido.open_output(self.output_name) as out:
            out.send(mido.Message('sysex', data=msg))
            
    def set_param(self, name, value):
        if name not in PARAMETERS:
            raise ValueError(f"Parametro '{name}' sconosciuto")
            
        info = PARAMETERS[name]
        
        # Gestione Enum (MODEL)
        if info['type'] == 'enum':
            if isinstance(value, str):
                value = value.upper()
                if value not in info['values']:
                    raise ValueError(f"Valore '{value}' non valido per {name}. Permessi: {info['values']}")
                val_int = info['values'].index(value)
            else:
                val_int = int(value)
        else:
            # Gestione Range
            val_int = int(value)
            if not (info['min'] <= val_int <= info['max']):
                raise ValueError(f"Valore {val_int} fuori range per {name} ({info['min']}-{info['max']})")
                
        print(f"🎛️ SET {name} -> {value} ({val_int})")
        self.send_sysex(info['addr'], val_int)

    def get_models_list(self):
        return PARAMETERS["MODEL"]["values"]
