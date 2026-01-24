"""
BOSS IR2 - MIDI Capture con Salvataggio
Cattura tutti i messaggi e salva su file con descrizione parametro
"""
import mido
import time
import json
from datetime import datetime

# Auto-detect
IR2_INPUT = None
for name in mido.get_input_names():
    if 'BOSS' in name.upper() or 'IR-2' in name.upper() or 'IR2' in name.upper():
        IR2_INPUT = name
        break

if not IR2_INPUT:
    print("❌ BOSS IR-2 non trovato!")
    exit(1)

# Parametro che stai testando
PARAMETER_NAME = input("📝 Nome parametro che stai testando (es: VOLUME, LOW_EQ): ").strip() or "UNKNOWN"
DURATION = 15  # secondi

print(f"\n🎧 Monitoring: {IR2_INPUT}")
print(f"🎛️ Parametro: {PARAMETER_NAME}")
print(f"⏱️ Durata: {DURATION} secondi")
print("="*60)
print("👉 MUOVI SOLO IL PARAMETRO INDICATO!")
print("="*60)
print()

captured = []
start_time = time.time()

try:
    with mido.open_input(IR2_INPUT) as port:
        while time.time() - start_time < DURATION:
            remaining = int(DURATION - (time.time() - start_time))
            
            msg = port.poll()
            
            if msg:
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                count = len(captured) + 1
                
                entry = {
                    "time": ts,
                    "type": msg.type,
                    "parameter": PARAMETER_NAME
                }
                
                if msg.type == 'sysex':
                    hex_str = " ".join(f"{b:02X}" for b in msg.data)
                    entry["data"] = list(msg.data)
                    entry["hex"] = hex_str
                    
                    # Parse Roland format
                    if len(msg.data) >= 8 and msg.data[0] == 0x41:
                        entry["parsed"] = {
                            "device_id": msg.data[1],
                            "model_id": [msg.data[2], msg.data[3], msg.data[4]],
                            "command": "DT1" if msg.data[5] == 0x12 else f"0x{msg.data[5]:02X}",
                            "address": [msg.data[6], msg.data[7], msg.data[8], msg.data[9]],
                            "value": msg.data[10] if len(msg.data) > 10 else None,
                            "checksum": msg.data[-1]
                        }
                    
                    print(f"[{ts}] ({remaining:2d}s) #{count:03d} SysEx: {hex_str}")
                
                else:
                    entry["raw"] = str(msg)
                    print(f"[{ts}] ({remaining:2d}s) #{count:03d} {msg.type}: {msg}")
                
                captured.append(entry)
            
            time.sleep(0.001)
            
except KeyboardInterrupt:
    pass

print(f"\n\n✅ Catturati {len(captured)} messaggi")

# Salva
if captured:
    filename = f"captures/{PARAMETER_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump({
            "parameter": PARAMETER_NAME,
            "duration": DURATION,
            "timestamp": datetime.now().isoformat(),
            "messages": captured
        }, f, indent=2)
    print(f"💾 Salvato: {filename}")
    
    # Analisi rapida
    sysex_only = [m for m in captured if m["type"] == "sysex"]
    if sysex_only:
        print(f"\n📊 Analisi rapida:")
        print(f"   Messaggi SysEx: {len(sysex_only)}")
        
        # Indirizzi unici
        addrs = set()
        for m in sysex_only:
            if "parsed" in m and "address" in m["parsed"]:
                addr = tuple(m["parsed"]["address"])
                addrs.add(addr)
        
        print(f"   Indirizzi unici: {len(addrs)}")
        for addr in sorted(addrs):
            print(f"      {' '.join(f'{b:02X}' for b in addr)}")
        
        # Range valori
        if "parsed" in sysex_only[0]:
            values = [m["parsed"].get("value") for m in sysex_only if "parsed" in m and m["parsed"].get("value") is not None]
            if values:
                print(f"   Range valori: {min(values):02X} → {max(values):02X} ({min(values)} → {max(values)})")
