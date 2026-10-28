# ICheck — Network Quota & Bandwidth Monitor

![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/Toolkit-GTK%203.0-4A86CF?logo=gtk&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

**ICheck** is a lightweight, dark-themed desktop network quota monitor for Linux built with **Python 3** and **GTK+ 3 (PyGObject)**. Inspired by the clean, tabbed utility layout of `pavucontrol`, it reads kernel network interface statistics directly from `/proc/net/dev` to track real-time bandwidth rates, per-SSID data consumption, and automated 10-minute usage snapshots with minimal CPU and memory overhead.

---

## Key Features

* **Per-SSID Quota Tracking:** Automatically detects the active Wi-Fi SSID and network interface, maintaining separate data consumption profiles and quota limits for every hotspot.
* **Real-Time Bandwidth Telemetry:** Polls `/proc/net/dev` every second to calculate live RX/TX throughput (`KB/s` or `MB/s`) without relying on heavy background daemons.
* **10-Minute Interval Logger:** Tracks data consumed within a rolling 10-minute window (with a live countdown timer) and automatically commits snapshots to a persistent log table.
* **Visual Threshold Alerts:** Dynamic progress bar styling that transitions from normal (Blue) to warning at **80%** (Amber) and critical at **100%** (Red), accompanied by desktop notifications and audio alerts.
* **Crash-Safe Persistence:** Automatically saves cumulative byte counters to `~/.config/icheck_guard/` across reboots, interface changes, and SSID switches.

---

---

## Application Features & Screenshots

Here is a preview of the user interface from each main feature tab in the ICheck application:

### 1. Monitor Tab
Monitors real-time quota consumption, active network download/upload speed, dynamic progress bar, and the 10-minute interval countdown cycle.
![Monitor Tab](preview-monitor.png)

### 2. Configuration Tab
Flexibly configures daily or monthly quota limits using a SpinButton or quick-select preset buttons, and allows selecting the network interface to monitor.
![Configuration Tab](preview-configuration.png)

### 3. Usage Logs (10m) Tab
Presents an automated historical table of 10-minute data consumption intervals along with manual snapshot recording and log clearing features.
![Logs Tab](preview-log.png)

### 4. System Tab
Provides session management controls such as network redetection, emergency quota reset, and safe application exit buttons.
![System Tab](preview-system.png)

### 5. Windows & Tray Integration Preview
Displays how ICheck seamlessly integrates with the desktop environment, featuring real-time quota telemetry right next to the system tray and panel indicators.
![Windows Preview](preview-windows.png)

## System Dependencies & Library Installation

ICheck relies on native Linux system utilities and GTK+ 3 bindings for Python. Before running the application, install the required libraries according to your Linux distribution:

### 1. Ubuntu / Debian / Linux Mint
```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 network-manager iproute2 libnotify-bin alsa-utils
```

### 2. Fedora / RHEL
```bash
sudo dnf install python3 python3-gobject gtk3 NetworkManager iproute libnotify alsa-utils
```

### 3. Arch Linux / Manjaro
```bash
sudo pacman -S python python-gobject gtk3 networkmanager iproute2 libnotify alsa-utils
```

> **Optional Font:** For the best visual appearance matching the stylesheet, install the **League Spartan** or **Ubuntu** font family on your system.

### Dependency Breakdown
| Package / Library | Purpose in ICheck |
| :--- | :--- |
| `python3-gi` & `gir1.2-gtk-3.0` | Renders the GTK+ 3 graphical user interface and CSS styling. |
| `network-manager` (`nmcli`) | Detects the currently connected Wi-Fi SSID name. |
| `iproute2` (`ip`) | Automatically identifies the active default network interface. |
| `libnotify-bin` (`notify-send`) | Sends critical desktop notifications when quota reaches 100%. |
| `alsa-utils` (`aplay`) | Plays system audio alerts when quota limits are exceeded. |

---

## Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/icheck-network-monitor.git](https://github.com/YOUR_USERNAME/icheck-network-monitor.git)
   cd icheck-network-monitor
   ```

2. **Grant execution permissions:**
   ```bash
   chmod +x icheck.py
   ```

3. **Run the application:**
   ```bash
   ./icheck.py
   # or
   python3 icheck.py
   ```

---

## Application Structure

* **Monitor Tab:** Displays active SSID, network interface, real-time transfer rate, visual quota progress bar, and the live 10-minute cycle tracker.
* **Configuration Tab:** Allows switching the monitored network interface (`wlp2s0`, `wlan0`, `eth0`, etc.) and configuring custom MB/GB quota limits with quick-select presets.
* **Usage Logs (10m) Tab:** Presents a historical table of 10-minute consumption intervals (`Time Interval`, `SSID Profile`, `Interval Usage`, and `Cumulative Usage`), with support for manual snapshot triggers.
* **System Tab:** Provides session management controls to refresh network detection, reset active quota counters to `0 KB`, or safely save state and exit.

---

## Configuration & Data Storage

All configuration files and historical logs are stored locally in plain text inside `~/.config/icheck_guard/`:

* `iface.txt` — Stores the user-selected network interface.
* `limit_<SSID>.txt` — Stores the configured quota threshold (in MB) for a specific SSID.
* `base_bytes_<SSID>.txt` & `accum_<SSID>.txt` — Tracks session byte offsets and cumulative usage.
* `log10m_<SSID>.txt` — Pipe-delimited (`|`) historical records of 10-minute usage snapshots.

---

## License

This project is open-source and available under the [MIT License](LICENSE).
