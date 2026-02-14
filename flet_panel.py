import time
import threading

import requests
import flet as ft


PANEL_HOST = "127.0.0.1"
PANEL_PORT = 5055
PANEL_TOKEN = ""

HEALTH_URL = f"http://{PANEL_HOST}:{PANEL_PORT}/health"


def fetch_health():
    try:
        resp = requests.get(HEALTH_URL, timeout=2)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"status_{resp.status_code}"
    except Exception as e:
        return None, str(e)


def main(page: ft.Page):
    page.title = "Luna - Flet Panel"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16

    status_text = ft.Text("offline", size=14)
    uptime_text = ft.Text("-", size=14)
    skills_text = ft.Text("-", size=14)
    tts_text = ft.Text("-", size=14)
    stt_text = ft.Text("-", size=14)
    vision_text = ft.Text("-", size=14)
    sys_text = ft.Text("-", size=14)

    log_box = ft.Text(value="", size=12)

    def update_ui(data, err):
        if err:
            status_text.value = f"offline ({err})"
            page.update()
            return
        status_text.value = "online"
        uptime_text.value = f"{data.get('uptime_seconds', 0)}s"
        skills_text.value = (
            f"loaded {data.get('skills_loaded', 0)} | failed {data.get('skills_failed', 0)}"
        )
        tts_text.value = f"queue {data.get('tts_queue_size', '-')}"
        stt_text.value = "ok"
        vision = data.get("vision", {})
        vision_text.value = f"last_len {vision.get('last_vision_len', 0)}"
        system = data.get("system", {})
        if system:
            sys_text.value = (
                f"cpu {system.get('cpu_percent', 0)}% | ram {system.get('memory_percent', 0)}%"
            )
        else:
            sys_text.value = "-"
        page.update()

    def poller():
        while True:
            data, err = fetch_health()
            update_ui(data, err)
            time.sleep(1)

    t = threading.Thread(target=poller, daemon=True)
    t.start()

    page.add(
        ft.Text("Luna - Flet Panel prototype", size=20, weight=ft.FontWeight.BOLD),
        ft.Row(
            [
                ft.Text("Status:"),
                status_text,
                ft.Text("Uptime:"),
                uptime_text,
            ],
            wrap=True,
        ),
        ft.Row(
            [
                ft.Text("Skills:"),
                skills_text,
            ],
            wrap=True,
        ),
        ft.Row(
            [
                ft.Text("TTS:"),
                tts_text,
                ft.Text("STT:"),
                stt_text,
            ],
            wrap=True,
        ),
        ft.Row(
            [
                ft.Text("Vision:"),
                vision_text,
                ft.Text("System:"),
                sys_text,
            ],
            wrap=True,
        ),
        ft.Divider(),
        ft.Text("Log", size=14, weight=ft.FontWeight.BOLD),
        log_box,
    )


if __name__ == "__main__":
    ft.app(target=main)
