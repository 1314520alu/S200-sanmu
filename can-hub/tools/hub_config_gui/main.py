"""DroneCAN Hub port-enable configuration GUI."""

from __future__ import annotations

import tkinter.messagebox as messagebox
from tkinter import BooleanVar

import customtkinter as ctk
import serial
import serial.tools.list_ports

import protocol

BAUD = 115200
TIMEOUT = 0.2
DEFAULT_ENABLE = [1, 1, 1, 1, 1, 1, 1, 0]
POLL_MS = 50


class HubConfigApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DroneCAN Hub Config")
        self.geometry("720x560")
        self.minsize(640, 480)

        self.ser: serial.Serial | None = None
        self._rx_buffer = ""
        self._poll_id: str | None = None

        self._build_ui()
        self.refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        conn = ctk.CTkFrame(self)
        conn.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        conn.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(conn, text="COM:").grid(row=0, column=0, padx=(8, 4), pady=8)
        self.port_combo = ctk.CTkComboBox(conn, values=[], width=220)
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=8)
        self.refresh_btn = ctk.CTkButton(conn, text="刷新", width=60, command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=2, padx=4, pady=8)
        self.connect_btn = ctk.CTkButton(conn, text="打开", width=80, command=self.toggle_serial)
        self.connect_btn.grid(row=0, column=3, padx=(4, 8), pady=8)

        ports = ctk.CTkFrame(self)
        ports.grid(row=1, column=0, sticky="ew", padx=10, pady=6)
        ctk.CTkLabel(ports, text="端口启用", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4)
        )

        self.vars: list[BooleanVar] = []
        for i, name in enumerate(protocol.PORT_NAMES):
            var = BooleanVar(value=bool(DEFAULT_ENABLE[i]))
            self.vars.append(var)
            cb = ctk.CTkCheckBox(ports, text=name, variable=var)
            if i == 0:
                cb.configure(state="disabled")
            cb.grid(row=1 + i // 4, column=i % 4, sticky="w", padx=12, pady=4)

        actions = ctk.CTkFrame(self)
        actions.grid(row=2, column=0, sticky="ew", padx=10, pady=6)
        ctk.CTkButton(actions, text="读取配置", command=self.on_read_config).pack(
            side="left", padx=8, pady=8
        )
        ctk.CTkButton(actions, text="写入保存", command=self.on_write).pack(
            side="left", padx=8, pady=8
        )
        ctk.CTkButton(actions, text="读取状态", command=self.on_read_status).pack(
            side="left", padx=8, pady=8
        )
        ctk.CTkButton(actions, text="恢复默认", command=self.on_restore_default).pack(
            side="left", padx=8, pady=8
        )

        body = ctk.CTkFrame(self)
        body.grid(row=3, column=0, sticky="nsew", padx=10, pady=(6, 10))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        log_frame = ctk.CTkFrame(body)
        log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_frame, text="日志", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        self.log_box = ctk.CTkTextbox(log_frame, wrap="word")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        status_frame = ctk.CTkFrame(body)
        status_frame.grid(row=0, column=1, sticky="nsew")
        status_frame.grid_rowconfigure(1, weight=1)
        status_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(status_frame, text="端口状态", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        self.status_box = ctk.CTkTextbox(status_frame, wrap="word")
        self.status_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.status_box.insert("1.0", "未连接或未读取状态")

    def refresh_ports(self) -> None:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            ports = ["(无可用端口)"]
        self.port_combo.configure(values=ports)
        self.port_combo.set(ports[0])

    def toggle_serial(self) -> None:
        if self.ser and self.ser.is_open:
            self.close_serial()
            return

        port = self.port_combo.get()
        if not port or port.startswith("("):
            messagebox.showwarning("串口", "请选择有效 COM 端口")
            return

        try:
            self.ser = serial.Serial(port, BAUD, timeout=TIMEOUT)
        except serial.SerialException as exc:
            messagebox.showerror("串口", f"无法打开 {port}: {exc}")
            self.ser = None
            return

        self._rx_buffer = ""
        self.connect_btn.configure(text="关闭")
        self.port_combo.configure(state="disabled")
        self.refresh_btn.configure(state="disabled")
        self.append_log(f"已连接 {port} @ {BAUD}")
        self.start_poll()

    def close_serial(self) -> None:
        self.stop_poll()
        if self.ser:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except serial.SerialException:
                pass
            self.ser = None
        self.connect_btn.configure(text="打开")
        self.port_combo.configure(state="normal")
        self.refresh_btn.configure(state="normal")
        self.append_log("串口已关闭")

    def start_poll(self) -> None:
        if self._poll_id is None:
            self._poll_id = self.after(POLL_MS, self.poll_serial)

    def stop_poll(self) -> None:
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def poll_serial(self) -> None:
        self._poll_id = None
        if self.ser and self.ser.is_open:
            try:
                chunk = self.ser.read(self.ser.in_waiting or 1)
                if chunk:
                    self._rx_buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in self._rx_buffer:
                        line, self._rx_buffer = self._rx_buffer.split("\n", 1)
                        if line.strip():
                            self.handle_line(line)
            except serial.SerialException as exc:
                self.append_log(f"RX 错误: {exc}")
                self.close_serial()
                return
            self.start_poll()

    def send_line(self, line: str) -> None:
        if not self.ser or not self.ser.is_open:
            self.append_log("TX 跳过（串口未打开）")
            return
        try:
            self.ser.write(line.encode("utf-8"))
            self.append_log("TX " + line.strip())
        except serial.SerialException as exc:
            messagebox.showerror("串口", f"发送失败: {exc}")

    def append_log(self, text: str) -> None:
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")

    def handle_line(self, line: str) -> None:
        self.append_log("RX " + line.strip())
        try:
            msg = protocol.parse_line(line)
        except ValueError as exc:
            messagebox.showerror("协议", f"JSON 解析失败: {exc}")
            return

        if msg.get("ok") is False:
            messagebox.showerror("设备错误", str(msg.get("err", "unknown error")))
            return

        if "enable" in msg and isinstance(msg["enable"], list) and len(msg["enable"]) == 8:
            self.apply_enable(msg["enable"])

        if "ports" in msg and isinstance(msg["ports"], list):
            self.update_status(msg["ports"])

    def apply_enable(self, enable: list) -> None:
        try:
            normalized = protocol.validate_enable(enable)
        except ValueError as exc:
            messagebox.showerror("配置", str(exc))
            return
        for i in range(1, 8):
            self.vars[i].set(bool(normalized[i]))

    def update_status(self, ports: list) -> None:
        lines: list[str] = []
        for i, port in enumerate(ports):
            name = protocol.PORT_NAMES[i] if i < len(protocol.PORT_NAMES) else f"P{i}"
            if isinstance(port, dict):
                tx = port.get("tx", "-")
                rx = port.get("rx", "-")
                err = port.get("err", "-")
                fault = port.get("fault", "-")
                lines.append(f"{name}: tx={tx} rx={rx} err={err} fault={fault}")
            else:
                lines.append(f"{name}: {port}")
        self.status_box.delete("1.0", "end")
        self.status_box.insert("1.0", "\n".join(lines) if lines else "无端口数据")

    def current_enable(self) -> list[int]:
        return [1] + [1 if self.vars[i].get() else 0 for i in range(1, 8)]

    def on_read_config(self) -> None:
        self.send_line(protocol.encode_get_config())

    def on_write(self) -> None:
        self.send_line(protocol.encode_set_config(self.current_enable()))

    def on_read_status(self) -> None:
        self.send_line(protocol.encode_get_status())

    def on_restore_default(self) -> None:
        self.apply_enable(DEFAULT_ENABLE)
        self.send_line(protocol.encode_set_config(DEFAULT_ENABLE))

    def on_close(self) -> None:
        self.close_serial()
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = HubConfigApp()
    app.mainloop()


if __name__ == "__main__":
    main()
