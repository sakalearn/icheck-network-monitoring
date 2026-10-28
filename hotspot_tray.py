#!/usr/bin/env python3
import os
import time
import datetime
import subprocess
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

# Dukungan otomatis untuk System Tray / Panel Atas Linux (Ubuntu 24.04+)
HAS_INDICATOR = False
for ns in ('AyatanaAppIndicator3', 'AppIndicator3'):
    try:
        gi.require_version(ns, '0.1')
        IndicatorMod = getattr(__import__('gi.repository', fromlist=[ns]), ns)
        HAS_INDICATOR = True
        break
    except (ValueError, ImportError):
        continue

CONFIG_DIR = os.path.expanduser("~/.config/icheck_guard/")
os.makedirs(CONFIG_DIR, exist_ok=True)
IFACE_CONFIG_FILE = os.path.join(CONFIG_DIR, "iface.txt")

CSS_STYLE = b"""
window { background-color: #1e1e1e; color: #eeeeec; font-family: "League Spartan", "Ubuntu", "Sans-Serif"; }
notebook header { background-color: #161616; border-bottom: 1px solid #333333; }
notebook tab { background-color: transparent; color: #888888; padding: 10px 18px; font-weight: bold; }
notebook tab:checked { color: #ffffff; border-bottom: 2px solid #3584e4; }
.card { background-color: #262626; border: 1px solid #363636; border-radius: 6px; padding: 14px; }
label { color: #eeeeec; }
button { background-color: #323232; color: #eeeeec; border: 1px solid #484848; border-radius: 4px; padding: 6px 14px; font-weight: bold; }
button:hover { background-color: #424242; border-color: #3584e4; }
button.danger { background-color: #5a1e1e; border-color: #8a2e2e; }
button.danger:hover { background-color: #7a2828; }
entry, spinbutton, combobox button { background-color: #2b2b2b; color: #eeeeec; border: 1px solid #484848; border-radius: 4px; padding: 4px 8px; }
treeview.view { background-color: #222222; color: #eeeeec; }
treeview.view:selected { background-color: #3584e4; color: #ffffff; }
treeview header button { background-color: #1a1a1a; color: #aaaaaa; font-weight: bold; }
progressbar trough { background-color: #141414; border-radius: 4px; min-height: 12px; }
progressbar progress { background-color: #3584e4; border-radius: 4px; min-height: 12px; }
progressbar.warn progress { background-color: #f5c211; }
progressbar.crit progress { background-color: #e01b24; }
"""

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""

def notify_alert(title, msg):
    for cmd in (["aplay", "/usr/share/sounds/freedesktop/stereo/bell.wav"],
                ["notify-send", "-a", "ICheck", "-u", "critical", title, msg]):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def get_interfaces():
    try:
        ifaces = sorted(i for i in os.listdir('/sys/class/net/') if i != 'lo')
        return ifaces or ["wlp2s0"]
    except Exception:
        return ["wlp2s0"]

def detect_default_interface():
    if os.path.exists(IFACE_CONFIG_FILE):
        saved = open(IFACE_CONFIG_FILE).read().strip()
        if saved and os.path.exists(f"/sys/class/net/{saved}"):
            return saved
    for line in run_cmd(["ip", "route", "show"]).splitlines():
        if "default via" in line and "dev" in line.split():
            parts = line.split()
            return parts[parts.index("dev") + 1]
    return get_interfaces()[0]

def detect_active_ssid(iface):
    for line in run_cmd(["nmcli", "-t", "-f", "ACTIVE,DEVICE,SSID", "dev", "wifi"]).splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[0] == "yes" and parts[1] == iface:
            return ":".join(parts[2:]).strip() or f"Network ({iface})"
    return f"Network ({iface})"

def get_total_bytes(iface):
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if f"{iface}:" in line:
                    p = line.split(":")[1].split()
                    return int(p[0]) + int(p[8])
    except Exception:
        pass
    return 0

def fmt_size(b):
    mb = b / 1048576
    if mb < 1.0:
        return f"{b // 1024} KB"
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.2f} MB"


class ICheckWindow(Gtk.Window):
    INTERVAL_SEC = 600  # 10 Menit

    def __init__(self):
        super().__init__(title="ICheck")
        self.set_default_size(620, 440)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", self.on_window_close)

        self.iface = detect_default_interface()
        self.ssid = detect_active_ssid(self.iface)
        self.alert_sent = False
        self.load_state()

        now_bytes = get_total_bytes(self.iface)
        self.last_tick_bytes = now_bytes
        self.cycle_start_bytes = self.get_used_bytes(now_bytes)
        self.cycle_start_time = time.time()

        nb = Gtk.Notebook(tab_pos=Gtk.PositionType.TOP)
        self.add(nb)
        nb.append_page(self.build_monitor_tab(), Gtk.Label(label="Monitor"))
        nb.append_page(self.build_config_tab(), Gtk.Label(label="Configuration"))
        nb.append_page(self.build_logs_tab(), Gtk.Label(label="Usage Logs (10m)"))
        nb.append_page(self.build_system_tab(), Gtk.Label(label="System"))

        self.init_tray_indicator()
        self.load_logs()
        self.tick()
        GLib.timeout_add_seconds(1, self.tick)
        self.show_all()

    # --- INISIALISASI PANEL ATAS (SYSTEM TRAY) ---
    def init_tray_indicator(self):
        self.indicator = None
        if not HAS_INDICATOR:
            return

        self.indicator = IndicatorMod.Indicator.new(
            "icheck-network-monitor",
            "network-transmit-receive-symbolic",
            IndicatorMod.IndicatorCategory.SYSTEM_SERVICES
        )
        self.indicator.set_status(IndicatorMod.IndicatorStatus.ACTIVE)
        self.indicator.set_label(" 0 KB (0%)", " 999.99 MB (100%)")

        menu = Gtk.Menu()

        self.tray_info_item = Gtk.MenuItem(label=f"SSID: {self.ssid}")
        self.tray_info_item.set_sensitive(False)
        menu.append(self.tray_info_item)
        menu.append(Gtk.SeparatorMenuItem())

        item_toggle = Gtk.MenuItem(label="Show / Hide ICheck Window")
        item_toggle.connect("activate", self.on_toggle_window)
        menu.append(item_toggle)

        item_snap = Gtk.MenuItem(label="Record 10m Snapshot Now")
        item_snap.connect("activate", lambda _: self.record_snapshot(manual=True))
        menu.append(item_snap)

        item_reset = Gtk.MenuItem(label="Reset Quota Counter")
        item_reset.connect("activate", self.on_reset_quota)
        menu.append(item_reset)

        menu.append(Gtk.SeparatorMenuItem())

        item_quit = Gtk.MenuItem(label="Save State & Quit")
        item_quit.connect("activate", self.on_quit)
        menu.append(item_quit)

        menu.show_all()
        self.indicator.set_menu(menu)

    def on_toggle_window(self, _):
        if self.get_visible():
            self.hide()
        else:
            self.present()

    def on_window_close(self, widget, event):
        if self.indicator is not None:
            self.hide()
            return True
        self.on_quit()
        return False

    def paths(self):
        safe = "".join(c if c.isalnum() else "_" for c in self.ssid)
        return [os.path.join(CONFIG_DIR, f"{k}_{safe}.txt") for k in ("limit", "base_bytes", "accum", "log10m")]

    def read_int(self, path, default):
        try:
            return int(open(path).read().strip())
        except Exception:
            return default

    def load_state(self):
        f_lim, f_base, f_acc, _ = self.paths()
        sys_b = get_total_bytes(self.iface)
        self.limit_mb = self.read_int(f_lim, 1024)
        self.accum_bytes = self.read_int(f_acc, 0)
        saved_base = self.read_int(f_base, sys_b)
        self.base_bytes = sys_b if sys_b < saved_base else saved_base
        self.save_state(sys_b)

    def get_used_bytes(self, sys_b):
        if sys_b < self.base_bytes:
            self.base_bytes = sys_b
        return self.accum_bytes + (sys_b - self.base_bytes)

    def save_state(self, sys_b=None):
        sys_b = get_total_bytes(self.iface) if sys_b is None else sys_b
        f_lim, f_base, f_acc, _ = self.paths()
        self.accum_bytes = self.get_used_bytes(sys_b)
        self.base_bytes = sys_b
        for path, val in ((f_lim, self.limit_mb), (f_base, self.base_bytes), (f_acc, self.accum_bytes)):
            try:
                open(path, "w").write(str(val))
            except Exception:
                pass

    def make_box(self, spacing=14, is_card=False):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        if is_card:
            b.get_style_context().add_class("card")
        else:
            for m in ("start", "end", "top", "bottom"):
                getattr(b, f"set_margin_{m}")(20)
        return b

    # --- TAB 1: MONITOR ---
    def build_monitor_tab(self):
        root = self.make_box()
        card1 = self.make_box(10, is_card=True)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.lbl_ssid = Gtk.Label(halign=Gtk.Align.START)
        self.lbl_speed = Gtk.Label(halign=Gtk.Align.END)
        hdr.pack_start(self.lbl_ssid, True, True, 0)
        hdr.pack_end(self.lbl_speed, False, False, 0)

        self.pbar = Gtk.ProgressBar()
        self.lbl_usage = Gtk.Label(halign=Gtk.Align.START)
        for w in (hdr, self.pbar, self.lbl_usage):
            card1.pack_start(w, False, False, 2)

        card2 = self.make_box(8, is_card=True)
        lbl_t = Gtk.Label(halign=Gtk.Align.START)
        lbl_t.set_markup("<span font='10' weight='bold' foreground='#999999'>INTERVAL TRACKER (10-MINUTE CYCLE)</span>")
        self.lbl_10m_live = Gtk.Label(halign=Gtk.Align.START)
        self.lbl_10m_last = Gtk.Label(label="Last recorded interval: No snapshot recorded in this session", halign=Gtk.Align.START)
        for w in (lbl_t, self.lbl_10m_live, self.lbl_10m_last):
            card2.pack_start(w, False, False, 0)

        btm = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.combo_filter = Gtk.ComboBoxText()
        for t in ("Active Profile", "All Saved Profiles"):
            self.combo_filter.append_text(t)
        self.combo_filter.set_active(0)
        self.combo_filter.connect("changed", self.on_filter_changed)
        self.lbl_profiles = Gtk.Label()

        btm.pack_start(Gtk.Label(label="View:"), False, False, 0)
        btm.pack_start(self.combo_filter, False, False, 0)
        btm.pack_end(self.lbl_profiles, False, False, 0)

        root.pack_start(card1, False, False, 0)
        root.pack_start(card2, False, False, 0)
        root.pack_end(btm, False, False, 0)
        return root

    # --- TAB 2: CONFIGURATION ---
    def build_config_tab(self):
        root = self.make_box()
        card = self.make_box(14, is_card=True)

        title = Gtk.Label(halign=Gtk.Align.START)
        title.set_markup("<span font='11' weight='bold'>Network &amp; Quota Parameters</span>")
        card.pack_start(title, False, False, 0)

        grid = Gtk.Grid(column_spacing=16, row_spacing=12)
        self.combo_iface = Gtk.ComboBoxText()
        for idx, i in enumerate(get_interfaces()):
            self.combo_iface.append_text(i)
            if i == self.iface:
                self.combo_iface.set_active(idx)

        adj = Gtk.Adjustment(value=self.limit_mb, lower=10, upper=1000000, step_increment=50, page_increment=500)
        self.spin_limit = Gtk.SpinButton(adjustment=adj, numeric=True)

        grid.attach(Gtk.Label(label="Network Interface:", halign=Gtk.Align.START), 0, 0, 1, 1)
        grid.attach(self.combo_iface, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="Quota Threshold (MB):", halign=Gtk.Align.START), 0, 1, 1, 1)
        grid.attach(self.spin_limit, 1, 1, 1, 1)
        card.pack_start(grid, False, False, 0)

        p_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        p_box.pack_start(Gtk.Label(label="Quick Presets:"), False, False, 0)
        for val, txt in ((500, "500 MB"), (1024, "1 GB"), (2048, "2 GB"), (5120, "5 GB")):
            btn = Gtk.Button(label=txt)
            btn.connect("clicked", lambda _, v=val: self.spin_limit.set_value(v))
            p_box.pack_start(btn, False, False, 0)
        card.pack_start(p_box, False, False, 0)

        btn_save = Gtk.Button(label="Apply Configuration")
        btn_save.connect("clicked", self.on_save_config)
        self.lbl_cfg_msg = Gtk.Label(halign=Gtk.Align.START)
        card.pack_start(btn_save, False, False, 4)
        card.pack_start(self.lbl_cfg_msg, False, False, 0)

        root.pack_start(card, False, False, 0)
        return root

    # --- TAB 3: USAGE LOGS (10M) ---
    def build_logs_tab(self):
        root = self.make_box(12)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl = Gtk.Label(halign=Gtk.Align.START)
        lbl.set_markup("<span font='11' weight='bold'>10-Minute Consumption History</span>")
        btn_snap = Gtk.Button(label="Record Snapshot Now")
        btn_snap.connect("clicked", lambda _: self.record_snapshot(manual=True))
        top.pack_start(lbl, True, True, 0)
        top.pack_end(btn_snap, False, False, 0)

        self.log_store = Gtk.ListStore(str, str, str, str)
        tv = Gtk.TreeView(model=self.log_store)
        for idx, (col_name, w) in enumerate((("Time Interval", 150), ("SSID Profile", 140), ("Interval Usage", 120), ("Cumulative", 120))):
            col = Gtk.TreeViewColumn(col_name, Gtk.CellRendererText(), text=idx)
            col.set_min_width(w)
            col.set_resizable(True)
            tv.append_column(col)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.add(tv)
        btn_clr = Gtk.Button(label="Clear Log History")
        btn_clr.connect("clicked", self.on_clear_logs)

        for w in (top, scroll, btn_clr):
            root.pack_start(w, w == scroll, w == scroll, 0)
        return root

    # --- TAB 4: SYSTEM ---
    def build_system_tab(self):
        root = self.make_box()
        card = self.make_box(12, is_card=True)
        lbl = Gtk.Label(halign=Gtk.Align.START)
        lbl.set_markup("<span font='11' weight='bold'>Session &amp; Process Control</span>")
        card.pack_start(lbl, False, False, 0)

        actions = [
            ("Refresh Network Detection", self.on_refresh_net, False),
            ("Reset Current Quota Session", self.on_reset_quota, True),
            ("Hide to Background Tray", lambda _: self.hide(), False),
            ("Save State & Exit", self.on_quit, False)
        ]
        for label_txt, handler, is_danger in actions:
            btn = Gtk.Button(label=label_txt)
            if is_danger:
                btn.get_style_context().add_class("danger")
            btn.connect("clicked", handler)
            card.pack_start(btn, False, False, 0)

        card.pack_start(Gtk.Label(label=f"Storage Path: {CONFIG_DIR}", halign=Gtk.Align.START), False, False, 4)
        root.pack_start(card, False, False, 0)
        return root

    # --- HANDLERS & TIMERS ---
    def on_save_config(self, _):
        new_iface = self.combo_iface.get_active_text()
        if new_iface and new_iface != self.iface:
            self.save_state()
            self.iface = new_iface
            open(IFACE_CONFIG_FILE, "w").write(self.iface)
            self.ssid = detect_active_ssid(self.iface)
            self.load_state()
            self.load_logs()

        self.limit_mb = self.spin_limit.get_value_as_int()
        self.alert_sent = False
        self.save_state()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.lbl_cfg_msg.set_markup(f"<span foreground='#57e389'>Configuration saved at {ts} ({self.limit_mb} MB on {self.iface})</span>")
        self.tick()

    def on_reset_quota(self, _):
        sys_b = get_total_bytes(self.iface)
        self.accum_bytes = 0
        self.base_bytes = sys_b
        self.cycle_start_bytes = 0
        self.cycle_start_time = time.time()
        self.alert_sent = False
        self.save_state(sys_b)
        self.tick()

    def on_refresh_net(self, _):
        self.save_state()
        self.iface = detect_default_interface()
        self.ssid = detect_active_ssid(self.iface)
        self.load_state()
        self.spin_limit.set_value(self.limit_mb)
        self.load_logs()
        self.tick()

    def on_filter_changed(self, combo):
        if combo.get_active() == 1:
            count = sum(1 for f in os.listdir(CONFIG_DIR) if f.startswith("accum_"))
            self.lbl_profiles.set_text(f"Tracked SSID Profiles: {count}")
        else:
            self.lbl_profiles.set_text("")

    def load_logs(self):
        self.log_store.clear()
        log_f = self.paths()[3]
        if os.path.exists(log_f):
            for line in open(log_f):
                parts = line.strip().split("|")
                if len(parts) == 4:
                    self.log_store.prepend(parts)

    def on_clear_logs(self, _):
        self.log_store.clear()
        log_f = self.paths()[3]
        if os.path.exists(log_f):
            os.remove(log_f)

    def record_snapshot(self, manual=False):
        sys_b = get_total_bytes(self.iface)
        used_b = self.get_used_bytes(sys_b)
        delta_b = max(0, used_b - self.cycle_start_bytes)

        t_start = datetime.datetime.fromtimestamp(self.cycle_start_time).strftime("%H:%M")
        t_end = datetime.datetime.now().strftime("%H:%M:%S")
        t_range = f"{t_start} - {t_end}" + (" [M]" if manual else "")

        row = [t_range, self.ssid, f"+ {fmt_size(delta_b)}", fmt_size(used_b)]
        self.log_store.prepend(row)
        try:
            open(self.paths()[3], "a").write("|".join(row) + "\n")
        except Exception:
            pass

        self.lbl_10m_last.set_markup(f"Last recorded ({t_range}): <span foreground='#57e389' weight='bold'>{fmt_size(delta_b)}</span>")
        self.cycle_start_bytes = used_b
        self.cycle_start_time = time.time()
        self.save_state(sys_b)

    def tick(self):
        now = time.time()
        if int(now) % 10 == 0:
            cur_ssid = detect_active_ssid(self.iface)
            if cur_ssid != self.ssid:
                self.save_state()
                self.ssid = cur_ssid
                self.load_state()
                self.spin_limit.set_value(self.limit_mb)
                self.load_logs()
                self.cycle_start_bytes = self.accum_bytes
                self.cycle_start_time = now

        sys_b = get_total_bytes(self.iface)
        if sys_b > 0:
            # 1. Bandwidth Rate
            rate = max(0, sys_b - self.last_tick_bytes)
            self.last_tick_bytes = sys_b
            rate_str = f"{rate / 1048576:.2f} MB/s" if rate >= 1048576 else f"{rate // 1024} KB/s"
            self.lbl_speed.set_markup(f"<span font='11' weight='bold' foreground='#3584e4'>{rate_str}</span>")

            # 2. Quota Progress
            used_b = self.get_used_bytes(sys_b)
            pct = (used_b / 1048576) / self.limit_mb if self.limit_mb > 0 else 0
            pct_int = int(pct * 100)
            used_str = fmt_size(used_b)

            self.lbl_ssid.set_markup(f"<span font='12' weight='bold'>SSID: {self.ssid} ({self.iface})</span>")
            self.pbar.set_fraction(min(pct, 1.0))

            ctx = self.pbar.get_style_context()
            ctx.remove_class("warn")
            ctx.remove_class("crit")
            if pct >= 1.0:
                ctx.add_class("crit")
                if not self.alert_sent:
                    self.alert_sent = True
                    notify_alert("Quota Limit Reached", f"{self.ssid} has exceeded {self.limit_mb} MB.")
            elif pct >= 0.8:
                ctx.add_class("warn")

            self.lbl_usage.set_text(f"{used_str} / {self.limit_mb} MB ({pct_int}%)")

            # 3. Update Real-Time Top Panel Indicator
            if self.indicator is not None:
                self.indicator.set_label(f" {used_str} ({pct_int}%)", " 999.99 MB (100%)")
                self.tray_info_item.set_label(f"{self.ssid} — {rate_str}")
                if pct >= 1.0:
                    self.indicator.set_icon_full("network-error-symbolic", "Quota Exceeded")
                else:
                    self.indicator.set_icon_full("network-transmit-receive-symbolic", "Normal")

            # 4. 10-Minute Interval Calculation
            elapsed = now - self.cycle_start_time
            rem_m, rem_s = divmod(max(0, int(self.INTERVAL_SEC - elapsed)), 60)
            delta_str = fmt_size(max(0, used_b - self.cycle_start_bytes))
            self.lbl_10m_live.set_markup(
                f"Current cycle consumption: <b>{delta_str}</b>   |   Next log in: <span foreground='#f5c211'>{rem_m:02d}m {rem_s:02d}s</span>"
            )

            if elapsed >= self.INTERVAL_SEC:
                self.record_snapshot(manual=False)
            if int(now) % 30 == 0:
                self.save_state(sys_b)
        return True

    def on_quit(self, *_):
        self.save_state()
        Gtk.main_quit()


if __name__ == "__main__":
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS_STYLE)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    ICheckWindow()
    Gtk.main()
