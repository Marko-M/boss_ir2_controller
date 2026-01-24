import sys
import os

# Aggiungi la directory corrente al path per permettere l'importazione di 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.gui import BossIR2App

if __name__ == "__main__":
    print("🎸 Avvio BOSS IR-2 Controller...")
    app = BossIR2App()
    app.mainloop()
