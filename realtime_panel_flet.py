"""
Painel Luna em Flet - Interface nativa moderna
Para executar: python realtime_panel_flet.py
"""

import os
import time
import threading
from datetime import datetime
from typing import Any, Dict, Optional
import flet as ft
from socketio import Client


class LunaPanelFlet:
    def __init__(self):
        self.sio = Client()
        self.connected = False
        self.last_state = {}
        
        # UI Components (serão criados no build)
        self.conn_status = None
        self.modo_text = None
        self.stt_text = None
        self.tts_text = None
        self.memoria_text = None
        self.temperamento_text = None
        self.visao_auto_text = None
        self.ultimo_cmd_text = None
        self.status_text = None
        self.ultima_resposta_field = None
        self.cmd_input = None
        self.resultado_text = None
        self.timestamp_text = None
        
    def _panel_host(self) -> str:
        return os.getenv("LUNA_PANEL_HOST", "127.0.0.1")
    
    def _panel_port(self) -> int:
        try:
            return int(os.getenv("LUNA_PANEL_PORT", "5055"))
        except ValueError:
            return 5055
    
    def _panel_token(self) -> str:
        return os.getenv("LUNA_PANEL_TOKEN", "").strip()
    
    def connect_socketio(self, page: ft.Page):
        """Conecta ao servidor Socket.IO"""
        host = self._panel_host()
        port = self._panel_port()
        token = self._panel_token()
        
        @self.sio.on('connect')
        def on_connect():
            self.connected = True
            page.run_task(self.update_connection_status, True)
            page.run_task(self.show_snackbar, "Conectado ao servidor Luna", ft.colors.GREEN)
        
        @self.sio.on('disconnect')
        def on_disconnect():
            self.connected = False
            page.run_task(self.update_connection_status, False)
            page.run_task(self.show_snackbar, "Desconectado do servidor", ft.colors.RED)
        
        @self.sio.on('state_update')
        def on_state_update(data):
            self.last_state = data
            page.run_task(self.update_ui_from_state, data)
        
        @self.sio.on('control_result')
        def on_control_result(data):
            page.run_task(self.handle_control_result, data)
        
        # Conecta com token
        try:
            url = f"http://{host}:{port}"
            self.sio.connect(url, auth={'token': token}, transports=['polling', 'websocket'])
        except Exception as e:
            page.run_task(self.show_snackbar, f"Erro ao conectar: {e}", ft.colors.RED)
    
    async def update_connection_status(self, connected: bool):
        """Atualiza indicador de conexão"""
        if self.conn_status:
            if connected:
                self.conn_status.value = "Conectado"
                self.conn_status.color = ft.colors.GREEN
                self.conn_status.icon = ft.icons.CLOUD_DONE
            else:
                self.conn_status.value = "Desconectado"
                self.conn_status.color = ft.colors.RED
                self.conn_status.icon = ft.icons.CLOUD_OFF
            self.conn_status.update()
    
    async def update_ui_from_state(self, state: Dict[str, Any]):
        """Atualiza a UI com o estado recebido"""
        if not state:
            return
        
        if self.modo_text:
            self.modo_text.value = state.get("modo", "-")
            self.modo_text.update()
        
        if self.stt_text:
            self.stt_text.value = state.get("stt_engine", "-")
            self.stt_text.update()
        
        if self.tts_text:
            tts = state.get("tts_engine", "-")
            if state.get("tts_async"):
                tts += " (async)"
            self.tts_text.value = tts
            self.tts_text.update()
        
        if self.memoria_text:
            self.memoria_text.value = str(state.get("memoria_curta_len", 0))
            self.memoria_text.update()
        
        if self.temperamento_text:
            self.temperamento_text.value = state.get("temperamento", "-")
            self.temperamento_text.update()
        
        if self.visao_auto_text:
            visao = state.get("visao_auto", {})
            if visao:
                rest = int(visao.get("cooldown_restante", 0))
                label = f"Ativo ({rest}s)" if visao.get("ativo") else "Inativo"
                self.visao_auto_text.value = label
            else:
                self.visao_auto_text.value = "-"
            self.visao_auto_text.update()
        
        if self.timestamp_text:
            self.timestamp_text.value = state.get("ts", "-")
            self.timestamp_text.update()
        
        if self.ultimo_cmd_text:
            self.ultimo_cmd_text.value = state.get("ultimo_comando", "-")
            self.ultimo_cmd_text.update()
        
        if self.status_text:
            status = state.get("status", "")
            if status:
                self.status_text.value = status
                self.status_text.update()
        
        if self.ultima_resposta_field:
            self.ultima_resposta_field.value = state.get("ultima_resposta", "")
            self.ultima_resposta_field.update()
    
    async def handle_control_result(self, result: Dict[str, Any]):
        """Processa resultado de comandos de controle"""
        if not result:
            return
        
        msg = result.get("msg", "")
        
        if self.resultado_text:
            self.resultado_text.value = msg
            self.resultado_text.update()
        
        if result.get("resposta") and self.ultima_resposta_field:
            self.ultima_resposta_field.value = result["resposta"]
            self.ultima_resposta_field.update()
        
        # Mostrar notificação
        color = ft.colors.GREEN if result.get("ok") else ft.colors.RED
        await self.show_snackbar(msg, color)
    
    async def show_snackbar(self, message: str, color: str):
        """Mostra uma notificação snackbar"""
        if hasattr(self, 'page') and self.page:
            snack = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=color,
            )
            self.page.overlay.append(snack)
            snack.open = True
            self.page.update()
    
    def set_modo(self, e, modo: str):
        """Define o modo de operação"""
        self.sio.emit("control", {"action": "set_mode", "payload": {"modo": modo}})
    
    def limpar_memoria(self, e):
        """Limpa a memória curta"""
        self.sio.emit("control", {"action": "limpar_memoria_curta", "payload": {}})
    
    def recarregar_skills(self, e):
        """Recarrega as skills"""
        self.sio.emit("control", {"action": "recarregar_skills", "payload": {}})
    
    def enviar_comando(self, e, falar: bool = False):
        """Envia comando para a Luna"""
        cmd = self.cmd_input.value.strip() if self.cmd_input else ""
        if not cmd:
            self.page.run_task(self.show_snackbar, "Digite um comando primeiro", ft.colors.ORANGE)
            return
        
        self.sio.emit("control", {
            "action": "comando",
            "payload": {"comando": cmd, "falar": falar}
        })
        
        if self.cmd_input:
            self.cmd_input.value = ""
            self.cmd_input.update()
    
    def build_stat_card(self, icon: str, title: str, value_ref: ft.Ref, 
                       color: str, badge_text: str) -> ft.Container:
        """Cria um card de estatística"""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=color, size=30),
                    ft.Container(
                        content=ft.Text(badge_text, size=10, color=ft.colors.WHITE),
                        bgcolor=f"{color}33",
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=20,
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(ref=value_ref, size=24, weight=ft.FontWeight.BOLD),
                ft.Text(title, size=12, color=ft.colors.GREY_400),
            ], spacing=8),
            bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
            border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
            border_radius=12,
            padding=20,
        )
    
    def main(self, page: ft.Page):
        """Interface principal do Flet"""
        self.page = page
        page.title = "Luna AI - Painel de Controle"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 0
        
        # Refs para componentes
        modo_ref = ft.Ref[ft.Text]()
        stt_ref = ft.Ref[ft.Text]()
        tts_ref = ft.Ref[ft.Text]()
        memoria_ref = ft.Ref[ft.Text]()
        
        self.modo_text = ft.Text(ref=modo_ref, value="-")
        self.stt_text = ft.Text(ref=stt_ref, value="-")
        self.tts_text = ft.Text(ref=tts_ref, value="-")
        self.memoria_text = ft.Text(ref=memoria_ref, value="0")
        
        # Header
        header = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.NIGHTLIGHT, color=ft.colors.WHITE, size=30),
                        bgcolor=ft.colors.PURPLE,
                        width=50,
                        height=50,
                        border_radius=25,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text("Luna AI", size=24, weight=ft.FontWeight.BOLD,
                               color=ft.colors.PURPLE),
                        ft.Text("Painel de Controle", size=12, color=ft.colors.GREY_400),
                    ], spacing=0),
                ], spacing=15),
                ft.Row([
                    self.conn_status := ft.TextButton(
                        "Desconectado",
                        icon=ft.icons.CLOUD_OFF,
                        style=ft.ButtonStyle(color=ft.colors.RED),
                    ),
                    self.timestamp_text := ft.Text("-", size=12, color=ft.colors.GREY_400),
                ], spacing=15),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE))),
            padding=20,
        )
        
        # Stats Grid
        stats_grid = ft.Row([
            self.build_stat_card(ft.icons.ROBOT, "Modo de Operação", modo_ref, 
                               ft.colors.PURPLE, "Modo"),
            self.build_stat_card(ft.icons.MIC, "Speech to Text", stt_ref, 
                               ft.colors.BLUE, "STT"),
            self.build_stat_card(ft.icons.VOLUME_UP, "Text to Speech", tts_ref, 
                               ft.colors.GREEN, "TTS"),
            self.build_stat_card(ft.icons.PSYCHOLOGY, "Memória Curta", memoria_ref, 
                               ft.colors.PINK, "Memória"),
        ], wrap=True, spacing=15, run_spacing=15)
        
        # Additional Info
        self.temperamento_text = ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.PURPLE_300)
        self.visao_auto_text = ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_300)
        
        additional_info = ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.icons.PALETTE, color=ft.colors.PURPLE_400), 
                           ft.Text("Temperamento", size=16, weight=ft.FontWeight.BOLD)]),
                    self.temperamento_text,
                ], spacing=10),
                bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
                border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
                border_radius=12,
                padding=20,
                expand=True,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.icons.REMOVE_RED_EYE, color=ft.colors.BLUE_400), 
                           ft.Text("Visão Automática", size=16, weight=ft.FontWeight.BOLD)]),
                    self.visao_auto_text,
                ], spacing=10),
                bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
                border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
                border_radius=12,
                padding=20,
                expand=True,
            ),
        ], spacing=15)
        
        # Quick Actions
        quick_actions = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.BOLT, color=ft.colors.YELLOW_400),
                    ft.Text("Ações Rápidas", size=16, weight=ft.FontWeight.BOLD),
                ]),
                ft.Row([
                    ft.ElevatedButton(
                        "Assistente",
                        icon=ft.icons.PERSON,
                        on_click=lambda e: self.set_modo(e, "assistente"),
                        bgcolor=ft.colors.PURPLE,
                        color=ft.colors.WHITE,
                    ),
                    ft.ElevatedButton(
                        "VTuber",
                        icon=ft.icons.VIDEOCAM,
                        on_click=lambda e: self.set_modo(e, "vtuber"),
                        bgcolor=ft.colors.PINK,
                        color=ft.colors.WHITE,
                    ),
                    ft.ElevatedButton(
                        "Limpar Memória",
                        icon=ft.icons.DELETE,
                        on_click=self.limpar_memoria,
                        bgcolor=ft.colors.RED,
                        color=ft.colors.WHITE,
                    ),
                    ft.ElevatedButton(
                        "Recarregar Skills",
                        icon=ft.icons.REFRESH,
                        on_click=self.recarregar_skills,
                        bgcolor=ft.colors.BLUE,
                        color=ft.colors.WHITE,
                    ),
                ], wrap=True, spacing=10),
            ], spacing=15),
            bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
            border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
            border_radius=12,
            padding=20,
        )
        
        # Command Panel
        self.cmd_input = ft.TextField(
            label="Digite um comando para a Luna",
            hint_text="Ex: qual é a previsão do tempo?",
            border_color=ft.colors.PURPLE_400,
            focused_border_color=ft.colors.PURPLE,
            on_submit=lambda e: self.enviar_comando(e, False),
        )
        
        self.resultado_text = ft.Text("", size=12, color=ft.colors.GREY_400)
        
        command_panel = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.TERMINAL, color=ft.colors.GREEN_400),
                    ft.Text("Enviar Comando", size=16, weight=ft.FontWeight.BOLD),
                ]),
                self.cmd_input,
                ft.Row([
                    ft.ElevatedButton(
                        "Enviar (Silencioso)",
                        icon=ft.icons.SEND,
                        on_click=lambda e: self.enviar_comando(e, False),
                        bgcolor=ft.colors.GREEN,
                        color=ft.colors.WHITE,
                        expand=True,
                    ),
                    ft.ElevatedButton(
                        "Enviar e Falar",
                        icon=ft.icons.VOLUME_UP,
                        on_click=lambda e: self.enviar_comando(e, True),
                        bgcolor=ft.colors.BLUE,
                        color=ft.colors.WHITE,
                        expand=True,
                    ),
                ], spacing=10),
                self.resultado_text,
            ], spacing=15),
            bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
            border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
            border_radius=12,
            padding=20,
        )
        
        # Activity Log
        self.ultimo_cmd_text = ft.Text("-", size=12, color=ft.colors.GREY_300)
        self.status_text = ft.Text("Aguardando...", size=12, color=ft.colors.GREY_300)
        
        activity_log = ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.HISTORY, color=ft.colors.PURPLE_400),
                        ft.Text("Último Comando", size=16, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Container(
                        content=self.ultimo_cmd_text,
                        bgcolor=ft.colors.with_opacity(0.5, ft.colors.BLACK),
                        padding=15,
                        border_radius=8,
                    ),
                ], spacing=10),
                bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
                border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
                border_radius=12,
                padding=20,
                expand=True,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.INFO, color=ft.colors.BLUE_400),
                        ft.Text("Status", size=16, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Container(
                        content=self.status_text,
                        bgcolor=ft.colors.with_opacity(0.5, ft.colors.BLACK),
                        padding=15,
                        border_radius=8,
                    ),
                ], spacing=10),
                bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
                border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
                border_radius=12,
                padding=20,
                expand=True,
            ),
        ], spacing=15)
        
        # Last Response
        self.ultima_resposta_field = ft.TextField(
            label="Última Resposta",
            multiline=True,
            min_lines=5,
            max_lines=10,
            read_only=True,
            border_color=ft.colors.PURPLE_400,
        )
        
        last_response = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.CHAT, color=ft.colors.GREEN_400),
                    ft.Text("Última Resposta", size=16, weight=ft.FontWeight.BOLD),
                ]),
                self.ultima_resposta_field,
            ], spacing=10),
            bgcolor=ft.colors.with_opacity(0.1, ft.colors.PURPLE),
            border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.PURPLE)),
            border_radius=12,
            padding=20,
        )
        
        # Main Layout
        main_content = ft.Column([
            header,
            ft.Container(
                content=ft.Column([
                    stats_grid,
                    additional_info,
                    quick_actions,
                    command_panel,
                    activity_log,
                    last_response,
                ], spacing=20, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True,
            ),
        ], spacing=0, expand=True)
        
        page.add(main_content)
        
        # Conectar ao Socket.IO em thread separada
        threading.Thread(target=lambda: self.connect_socketio(page), daemon=True).start()


def main():
    panel = LunaPanelFlet()
    ft.app(target=panel.main, view=ft.AppView.WEB_BROWSER)


if __name__ == "__main__":
    main()
