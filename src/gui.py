import customtkinter as ctk
import os
import json
import threading
import time
from datetime import datetime
from tkinter import BooleanVar, filedialog
from tkdial import Dial  # <--- New widget!
from .tool import BossIR2Manager, PARAMETERS

# Appearance configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class BossIR2App(ctk.CTk):
    AUTO_SYNC_INTERVAL_MS = 10000
    LOCAL_DIRTY_GRACE_MS = 2500

    def __init__(self):
        super().__init__()

        # Setup GUI Window
        self.title("BOSS IR-2 Control Center")
        self.geometry("900x750")  # Increased height to show everything
        self.resizable(True, True)  # Enable resizing if needed
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initialize Manager (Backend)
        self.manager = None
        self.connected = False

        # Sync / dirty-awareness state
        self.sync_in_progress = False
        self.sending_preset = False
        self.updating_ui_from_code = False
        self.local_dirty = False
        self.local_dirty_clear_job = None
        self.change_generation = 0
        self.closed = False

        # Start connection immediately (blocking briefly is ok on startup)
        self.after(100, self.connect_pedal)

        # Layout Main Container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ================= HEADER =================
        self.header_frame = ctk.CTkFrame(self, height=70, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")

        self.lbl_title = ctk.CTkLabel(
            self.header_frame,
            text="🎸 BOSS IR-2 CONTROLLER",
            font=("Arial", 22, "bold")
        )
        self.lbl_title.pack(side="left", padx=25, pady=15)

        self.lbl_status = ctk.CTkLabel(
            self.header_frame,
            text="● Connecting...",
            text_color="gray",
            font=("Arial", 14),
            height=36
        )
        self.lbl_status.pack(side="right", padx=25, pady=15)

        # ================= CONTROLS AREA =================
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.controls_frame.grid_columnconfigure((0, 1, 2), weight=1)  # Center columns

        # --- AMP MODEL SELECTION ---
        self.lbl_model = ctk.CTkLabel(self.controls_frame, text="AMP TYPE", font=("Arial", 16, "bold"))
        self.lbl_model.grid(row=0, column=0, columnspan=3, pady=(20, 5))

        self.combo_model = ctk.CTkOptionMenu(
            self.controls_frame,
            values=PARAMETERS["MODEL"]["values"],
            command=self.on_model_change,
            width=220,
            height=40,
            font=("Arial", 14)
        )
        self.combo_model.grid(row=1, column=0, columnspan=3, pady=10)

        # --- KNOBS DICTIONARY ---
        self.knobs = {}

        # Row 2: MAIN Params (Gain, Level, Ambience)
        self.create_knob("GAIN", row=2, col=0, color="#e74c3c")
        self.create_knob("LEVEL", row=2, col=1, color="#f1c40f")
        self.create_knob("AMBIENCE", row=2, col=2, color="#9b59b6")

        # Separator (Visual)
        self.sep = ctk.CTkFrame(self.controls_frame, height=2, fg_color="#444")
        self.sep.grid(row=3, column=0, columnspan=3, sticky="ew", padx=40, pady=25)

        # Row 4: EQ Params
        self.create_knob("BASS", row=4, col=0, color="#3498db")
        self.create_knob("MIDDLE", row=4, col=1, color="#3498db")
        self.create_knob("TREBLE", row=4, col=2, color="#3498db")

        # ================= FOOTER (Preset Management) =================
        self.footer_frame = ctk.CTkFrame(self, height=100, corner_radius=0)
        self.footer_frame.grid(row=2, column=0, sticky="ew")

        # Sync Button
        self.btn_sync = ctk.CTkButton(
            self.footer_frame,
            text="🔄 SYNC FROM PEDAL",
            command=self.sync_from_pedal,
            fg_color="#e67e22",
            hover_color="#d35400",
            text_color="white",
            text_color_disabled="white",
            width=160,
            height=40,
            font=("Arial", 12, "bold")
        )
        self.btn_sync.pack(side="left", padx=(25, 10), pady=25)

        # Optional slow auto-sync. Disabled by default to avoid unexpected pedal reads.
        self.auto_sync_enabled = BooleanVar(value=False)
        self.switch_auto_sync = ctk.CTkSwitch(
            self.footer_frame,
            text="Auto-sync",
            variable=self.auto_sync_enabled,
            command=self.on_auto_sync_toggle
        )
        self.switch_auto_sync.pack(side="left", padx=10, pady=25)

        # Load Button
        self.btn_load = ctk.CTkButton(
            self.footer_frame,
            text="📂 LOAD",
            command=self.load_preset_file,
            width=100,
            height=40
        )
        self.btn_load.pack(side="right", padx=10, pady=25)

        # Save Section
        self.btn_save = ctk.CTkButton(
            self.footer_frame,
            text="💾 SAVE",
            command=self.save_preset_file,
            fg_color="#27ae60",
            hover_color="#2ecc71",
            width=100,
            height=40
        )
        self.btn_save.pack(side="right", padx=10, pady=25)

        # Start the auto-sync scheduler. It only performs work when the switch is enabled.
        self.after(self.AUTO_SYNC_INTERVAL_MS, self._auto_sync_tick)

    def create_knob(self, param_name, row, col, color):
        """Helper to create a dial/knob block using tkdial."""
        frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        frame.grid(row=row, column=col, padx=10, pady=10)

        lbl = ctk.CTkLabel(frame, text=param_name, font=("Arial", 14, "bold"))
        lbl.pack(pady=(0, 5))

        # Value Label
        val_lbl = ctk.CTkLabel(frame, text="0", font=("Arial", 13))

        # Dial Widget
        # radius=35 means 70px size (smaller to fit better)
        # Note: This version of tkdial does not support a custom start_angle in the Dial constructor.
        # We use the default, which is still optimized for knobs.
        dial = Dial(
            frame,
            radius=35,
            start=0,
            end=127,
            color_gradient=(color, color),
            text_color="white",
            bg="#2b2b2b",  # Match customtk dark
            command=lambda: self.on_knob_change(param_name, dial, val_lbl)
        )

        dial.set(0)
        dial.pack()
        val_lbl.pack(pady=(5, 0))

        # Store refs
        self.knobs[param_name] = {"dial": dial, "label": val_lbl, "last_sent": -1}

    def connect_pedal(self):
        try:
            self.manager = BossIR2Manager()
            self.connected = True
            self.lbl_status.configure(text="● Connected", text_color="#2ecc71")

            # One startup sync gives the UI an accurate initial state without requiring auto-sync.
            self.after(300, lambda: self._request_sync(manual=False, reason="startup"))
        except Exception as e:
            error_msg = str(e)
            self.connected = False
            self.lbl_status.configure(text=f"● {error_msg}", text_color="#e74c3c")

    def on_auto_sync_toggle(self):
        if self.auto_sync_enabled.get():
            self.lbl_status.configure(text="● Auto-sync enabled", text_color="#f1c40f")
            # Try one soon, but the normal dirty/sync guards still apply.
            self.after(250, lambda: self._request_sync(manual=False, reason="auto"))
        else:
            if self.connected:
                self.lbl_status.configure(text="● Connected", text_color="#2ecc71")
            else:
                self.lbl_status.configure(text="● Not connected", text_color="gray")

    def _auto_sync_tick(self):
        if self.closed:
            return

        if self.auto_sync_enabled.get():
            self._request_sync(manual=False, reason="auto")

        self.after(self.AUTO_SYNC_INTERVAL_MS, self._auto_sync_tick)

    def mark_local_dirty(self):
        """Mark that the UI was changed locally and temporarily block auto-sync."""
        if self.updating_ui_from_code:
            return

        self.local_dirty = True
        self.change_generation += 1

        if self.local_dirty_clear_job is not None:
            try:
                self.after_cancel(self.local_dirty_clear_job)
            except Exception:
                pass

        self.local_dirty_clear_job = self.after(self.LOCAL_DIRTY_GRACE_MS, self.clear_local_dirty)

    def clear_local_dirty(self):
        self.local_dirty = False

        if self.local_dirty_clear_job is not None:
            job = self.local_dirty_clear_job
            self.local_dirty_clear_job = None
            try:
                self.after_cancel(job)
            except Exception:
                pass

    def is_locally_dirty(self):
        return self.local_dirty

    def on_model_change(self, value):
        if self.updating_ui_from_code:
            return

        self.mark_local_dirty()

        if self.connected:
            self.manager.set_param("MODEL", value)

    def on_knob_change(self, param, dial, label):
        # Avoid crashing during init if the dictionary is not populated yet.
        if param not in self.knobs:
            return

        val_int = int(dial.get())
        label.configure(text=str(val_int))

        if self.updating_ui_from_code:
            self.knobs[param]["last_sent"] = val_int
            return

        # Simple rate limiting: send only if changed.
        # tkdial calls the command very often while dragging.
        prev = self.knobs[param]["last_sent"]
        if val_int != prev:
            self.knobs[param]["last_sent"] = val_int
            self.mark_local_dirty()

            if self.connected:
                try:
                    self.manager.set_param(param, val_int)
                except Exception as e:
                    print(f"Error sending {param}: {e}")

    def sync_from_pedal(self):
        self._request_sync(manual=True, reason="manual")

    def _request_sync(self, manual=False, reason="manual"):
        if not self.connected or self.manager is None:
            return False

        if self.sync_in_progress:
            if manual:
                self.lbl_status.configure(text="● Sync already running", text_color="#f1c40f")
            return False

        if self.sending_preset:
            if manual:
                self.lbl_status.configure(text="● Preset send in progress", text_color="#f1c40f")
            return False

        # Auto-sync is deliberately conservative. It will not read from the pedal while
        # the user has recently changed values in the app. Startup sync is allowed.
        if not manual and reason == "auto" and self.is_locally_dirty():
            return False

        self.sync_in_progress = True
        generation_at_start = self.change_generation

        if manual:
            self.btn_sync.configure(text="Reading... (Wait)", state="disabled")
            self.lbl_status.configure(text="↻ Reading from pedal...", text_color="#f1c40f")
        elif reason == "auto":
            self.btn_sync.configure(text="AUTO-SYNCING...", state="disabled")
        else:
            self.btn_sync.configure(state="disabled")

        thread = threading.Thread(
            target=self._sync_worker,
            args=(manual, generation_at_start, reason),
            daemon=True
        )
        thread.start()
        return True

    def _sync_worker(self, manual, generation_at_start, reason):
        try:
            # Manual sync remains verbose. Startup/auto sync is quiet.
            data = self.manager.dump_preset(verbose=manual)
            if not self.closed:
                self.after(0, self._finish_sync_success, data, manual, generation_at_start, reason)
        except Exception as e:
            if not self.closed:
                self.after(0, self._finish_sync_error, str(e), manual)

    def _finish_sync_success(self, preset, manual, generation_at_start, reason):
        try:
            # If the user changed a knob while an automatic sync was reading, ignore the
            # stale auto-sync result so it does not stomp local edits.
            if not manual and reason == "auto" and generation_at_start != self.change_generation:
                print("Auto-sync result ignored because local controls changed during the read.")
                return

            self._apply_preset_to_ui(preset)
            self.clear_local_dirty()

            if manual:
                self.lbl_status.configure(text="✓ Synced", text_color="#2ecc71")
            elif reason == "startup":
                self.lbl_status.configure(text="✓ Connected + Synced", text_color="#2ecc71")
            else:
                # If auto-sync was disabled while this sync was still running,
                # do not leave the status stuck on "Auto-synced".
                if self.auto_sync_enabled.get():
                    self.lbl_status.configure(text="✓ Auto-synced", text_color="#2ecc71")
                elif self.connected:
                    self.lbl_status.configure(text="● Connected", text_color="#2ecc71")
        finally:
            self.sync_in_progress = False
            self.btn_sync.configure(text="🔄 SYNC FROM PEDAL", state="normal")

    def _finish_sync_error(self, error_msg, manual):
        print(f"Sync error: {error_msg}")
        self.sync_in_progress = False
        self.btn_sync.configure(text="🔄 SYNC FROM PEDAL", state="normal")

        if manual:
            self.lbl_status.configure(text="● Sync Error", text_color="#e74c3c")
        elif self.connected:
            self.lbl_status.configure(text="● Auto-sync failed", text_color="#f1c40f")

    def _apply_preset_to_ui(self, preset):
        data = preset["data"]

        self.updating_ui_from_code = True
        try:
            if "MODEL" in data:
                self.combo_model.set(data["MODEL"])

            for name, info in self.knobs.items():
                if name in data:
                    val = data[name]
                    info["dial"].set(val)
                    info["label"].configure(text=str(val))
                    info["last_sent"] = val
                else:
                    # If the key is missing from the preset, do not crash.
                    print(f"⚠️ Warning: Missing key {name} in preset")
        finally:
            self.updating_ui_from_code = False

    def save_preset_file(self):
        # Use an explicit dialog to ask for the name - reliable!
        dialog = ctk.CTkInputDialog(text="Enter Preset Name:", title="Save Preset")
        name = dialog.get_input()

        if not name or not name.strip():
            print("Save cancelled or empty name")
            return

        name = name.strip()
        print(f"DEBUG: Saving preset with name: '{name}'")

        # Read from UI state
        preset_data = {
            "device": "BOSS IR-2",
            "timestamp": datetime.now().isoformat(),
            "name": name,
            "data": {
                "MODEL": self.combo_model.get()
            }
        }

        for param_name, info in self.knobs.items():
            preset_data["data"][param_name] = int(info["dial"].get())

        os.makedirs("presets", exist_ok=True)
        filename = f"presets/{name}.json"

        with open(filename, 'w') as f:
            json.dump(preset_data, f, indent=2)

        self.lbl_status.configure(text=f"✓ Saved {name}", text_color="white")

    def load_preset_file(self):
        filepath = filedialog.askopenfilename(initialdir="presets", filetypes=[("JSON Files", "*.json")])
        if not filepath:
            return

        with open(filepath, 'r') as f:
            preset = json.load(f)

        self._apply_preset_to_ui(preset)
        self.mark_local_dirty()

        if self.connected:
            # Send to pedal.
            self.sending_preset = True
            self.btn_load.configure(state="disabled")
            self.lbl_status.configure(text="→ Sending...", text_color="yellow")
            # Update UI to prevent blocking, then send.
            self.after(100, lambda: self._send_loaded_preset(preset))

    def _send_loaded_preset(self, preset):
        try:
            for name, val in preset["data"].items():
                self.manager.set_param(name, val)
                time.sleep(0.05)
            self.lbl_status.configure(text="✓ Loaded", text_color="#2ecc71")
        except Exception as e:
            print(f"Load error: {e}")
            self.lbl_status.configure(text="● Load Error", text_color="#e74c3c")
        finally:
            self.sending_preset = False
            self.btn_load.configure(state="normal")

    def on_close(self):
        self.closed = True
        self.destroy()


if __name__ == "__main__":
    app = BossIR2App()
    app.mainloop()
