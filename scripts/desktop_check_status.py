"""Optional Windows desktop indicator; no browser, database or network access."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading


class DesktopCheckStatus:
    def __init__(self, enabled=False):
        self.process = None
        if enabled and os.name == "nt":
            try:
                self.process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "--window"],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass  # The indicator must never prevent checking.

    def update(self, completed, total, asin="", phase="確認中"):
        process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            process.stdin.write(json.dumps({
                "completed": completed, "total": total,
                "asin": asin, "phase": phase,
            }, ensure_ascii=True) + "\n")
            process.stdin.flush()
        except Exception:
            self.close()

    def close(self):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            process.stdin.close()  # EOF also closes the window after parent death.
            process.wait(timeout=1)
        except Exception:
            try:
                process.terminate()
                process.wait(timeout=1)
            except Exception:
                pass


def run_window():
    import tkinter as tk
    from tkinter import ttk
    from datetime import datetime

    updates = queue.Queue(maxsize=1)
    ended = threading.Event()

    def read_updates():
        try:
            for line in sys.stdin:
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                try:
                    updates.get_nowait()
                except queue.Empty:
                    pass
                updates.put_nowait(data)
        finally:
            ended.set()

    root = tk.Tk()
    root.title("価格・在庫チェック — Headless Shell")
    root.geometry("390x175")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)
    status = ttk.Label(frame, text="● 起動中", font=("Yu Gothic UI", 12, "bold"))
    status.pack(anchor="w")
    detail = ttk.Label(frame, text="")
    detail.pack(anchor="w", pady=6)
    progress = ttk.Progressbar(frame, mode="determinate", length=360)
    progress.pack()
    stamp = ttk.Label(frame, text="")
    stamp.pack(anchor="w", pady=4)
    ttk.Label(frame, text="×で閉じても処理は続きます。最終更新は進捗更新時刻です。").pack(anchor="w")

    def refresh():
        if ended.is_set():
            root.destroy()
            return
        try:
            data = updates.get_nowait()
        except queue.Empty:
            pass
        else:
            status.configure(text="● " + str(data["phase"]))
            detail.configure(text=f"今回の処理済み: {data['completed']} / {data['total']} 件  {data['asin']}")
            progress.configure(maximum=max(1, data["total"]), value=data["completed"])
            stamp.configure(text="最終更新: " + datetime.now().strftime("%H:%M:%S"))
        root.after(500, refresh)

    threading.Thread(target=read_updates, daemon=True).start()
    refresh()
    root.mainloop()


if __name__ == "__main__" and "--window" in sys.argv:
    run_window()
