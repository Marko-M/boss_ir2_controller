"""
BOSS IR-2 Manager Tool
Allows saving and loading complete presets to/from JSON files.
"""
import json
import time
import mido
from datetime import datetime
from .control import BossIR2, PARAMETERS

class BossIR2Manager(BossIR2):
    def send_rq1(self, addr, size=1):
        """Send Data Request (RQ1)"""
        # Header: F0 41 10 01 05 09 11
        msg = [0x41, 0x10, 0x01, 0x05, 0x09, 0x11]
        
        # Address + Size
        # Size uses 4 bytes
        # Assume a small size (<128) for now
        payload = addr + [0, 0, 0, size]
        msg.extend(payload)
        
        # Checksum
        msg.append(self._checksum(payload))
        
        with mido.open_output(self.output_name) as out:
            out.send(mido.Message('sysex', data=msg))

    def read_param(self, name, timeout=1.0):
        if name not in PARAMETERS:
            raise ValueError(f"Unknown parameter: {name}")
            
        addr = PARAMETERS[name]['addr']
        self.send_rq1(addr)
        
        start = time.time()
        with mido.open_input(self.input_name) as inp:
            while time.time() - start < timeout:
                msg = inp.poll()
                if msg and msg.type == 'sysex' and len(msg.data) > 10:
                    # Verify this is DT1 (0x12) and the address matches
                    if msg.data[5] == 0x12:
                        recv_addr = list(msg.data[6:10])
                        if recv_addr == addr:
                            val = msg.data[10]
                            return val
                time.sleep(0.01)
        return None

    def dump_preset(self):
        """Read ALL known parameters"""
        print("💾 Starting preset backup...")
        preset = {
            "device": "BOSS IR-2",
            "timestamp": datetime.now().isoformat(),
            "data": {}
        }
        
        for name in PARAMETERS:
            # Retry logic: try up to 3 times per parameter
            val = None
            for attempt in range(3):
                val = self.read_param(name, timeout=1.5)
                if val is not None:
                    break
                print(f"  ⚠️ Retry {attempt+1} for {name}...")
                time.sleep(0.2)
            
            if val is not None:
                # Convert enum to string if needed
                if PARAMETERS[name]['type'] == 'enum':
                    val_str = PARAMETERS[name]['values'][val]
                    print(f"  • {name}: {val_str} ({val})")
                    preset["data"][name] = val_str
                else:
                    print(f"  • {name}: {val}")
                    preset["data"][name] = val
            else:
                print(f"  ❌ Error reading {name} after 3 attempts")
            
            time.sleep(0.15) # Increased delay between commands (was 0.05)
            
        return preset

    def load_preset(self, filepath):
        """Load preset from file"""
        with open(filepath, 'r') as f:
            preset = json.load(f)
            
        print(f"📂 Loading preset from {preset['timestamp']}...")
        
        for name, value in preset["data"].items():
            try:
                self.set_param(name, value)
                time.sleep(0.05) # Pause between commands
            except Exception as e:
                print(f"  ❌ Error setting {name}: {e}")
                
        print("✅ Loading completed!")

if __name__ == "__main__":
    import mido
    
    try:
        manager = BossIR2Manager()
        
        while True:
            print("\nBOSS IR-2 MANAGER")
            print("1. 💾 Back up current preset (Dump)")
            print("2. 📂 Load preset")
            print("3. ❌ Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == "1":
                preset = manager.dump_preset()
                filename = f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(preset, f, indent=2)
                print(f"\n✅ Saved to: {filename}")
                
            elif choice == "2":
                import glob
                files = glob.glob("preset_*.json")
                if not files:
                    print("⚠️ No presets found!")
                    continue
                    
                print("\nAvailable presets:")
                for i, f in enumerate(files):
                    print(f"  {i+1}. {f}")
                
                try:
                    idx = int(input("\nWhich file should be loaded? (number): ")) - 1
                    if 0 <= idx < len(files):
                        manager.load_preset(files[idx])
                except ValueError:
                    pass
                    
            elif choice == "3":
                break
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        input("Press Enter to exit...")
