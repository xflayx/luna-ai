# interface/radial_menu_eel.py
import eel
import pyperclip
import threading
import os
import tempfile
import time
import sys
import json

class RadialMenuEel:
    def __init__(self):
        self.menu_visible = False
        self.arquivo_sinal = os.path.join(tempfile.gettempdir(), "luna_menu_open.signal")
        self.ultima_verificacao = 0
        
        # Caminho da pasta web
        self.web_folder = os.path.join(os.path.dirname(__file__), 'web')
        
        # Verifica se a pasta existe
        if not os.path.exists(self.web_folder):
            print(f"❌ Pasta 'web' não encontrada!")
            print(f"   Caminho esperado: {self.web_folder}")
            sys.exit(1)
        
        # Verifica se o HTML existe
        html_path = os.path.join(self.web_folder, 'radial_menu.html')
        if not os.path.exists(html_path):
            print(f"❌ Arquivo 'radial_menu.html' não encontrado!")
            print(f"   Caminho esperado: {html_path}")
            sys.exit(1)
        
        print(f"✅ HTML encontrado: {html_path}")
        
        # Inicializa Eel
        eel.init(self.web_folder)
        
        # Expõe funções Python para JavaScript
        eel.expose(self.execute_command)
        eel.expose(self.close_menu)
        eel.expose(self.load_sequencias)
        
    def execute_command(self, cmd):
        """Chamado pelo JavaScript quando clica em botão"""
        print(f"🎯 Comando: {cmd}")
        pyperclip.copy(cmd)
        return True
    
    def close_menu(self):
        """Fecha o menu"""
        print("❌ Fechando menu...")
        self.menu_visible = False
        return True
    
    def load_sequencias(self):
        """Carrega lista de sequências salvas do JSON"""
        try:
            macros_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'macros.json')
            
            if not os.path.exists(macros_file):
                print("⚠️ Arquivo de sequências não encontrado")
                return []
            
            with open(macros_file, 'r', encoding='utf-8') as f:
                macros = json.load(f)
            
            # Converte para formato do menu
            sequencias = []
            for nome in macros.keys():
                sequencias.append({
                    'id': f'seq_{nome}',
                    'label': nome,
                    'icon': '▶️',
                    'cmd': f'Luna executar sequência {nome}'
                })
            
            print(f"✅ Carregadas {len(sequencias)} sequências")
            return sequencias
            
        except Exception as e:
            print(f"❌ Erro ao carregar sequências: {e}")
            return []
    
    def verificar_comando_sinal(self):
        """Thread que verifica arquivo de sinal constantemente"""
        print("🔍 Iniciando monitoramento de arquivo de sinal...")
        
        while True:
            try:
                if os.path.exists(self.arquivo_sinal):
                    tempo_atual = time.time()
                    if tempo_atual - self.ultima_verificacao > 0.5:
                        try:
                            os.remove(self.arquivo_sinal)
                            print("🎯 Sinal detectado! Abrindo menu...")
                            self.abrir_menu()
                            self.ultima_verificacao = tempo_atual
                        except Exception as e:
                            print(f"⚠️ Erro ao processar sinal: {e}")
            except Exception as e:
                pass
            
            time.sleep(0.2)
    
    def abrir_menu(self):
        """Abre a janela do menu"""
        if not self.menu_visible:
            self.menu_visible = True
    
    def start(self):
        """Inicia o sistema em modo daemon"""
        print("🚀 Iniciando Menu Radial em modo daemon...")
        
        # Thread para verificar arquivo de sinal
        print("🎤 Iniciando monitoramento de sinais...")
        sinal_thread = threading.Thread(target=self.verificar_comando_sinal, daemon=True)
        sinal_thread.start()
        
        print("\n✅ MENU PRONTO!")
        print("🖱️ Botão lateral do mouse (AutoHotkey)")
        print("⌨️ Alt + Q (AutoHotkey)")
        print("🎤 'Luna, abrir menu' (comando de voz)")
        print("\n⏳ Aguardando sinal...\n")
        
        try:
            # Inicia Eel
            eel.start(
                'radial_menu.html',
                size=(600, 600),
                position='center',
                mode='chrome',
                block=True,
                close_callback=lambda page, sockets: None,
                cmdline_args=[
                    '--disable-http-cache',
                    '--disable-gpu',
                    '--app=http://localhost:8000/radial_menu.html',
                    '--window-position=-10000,-10000',
                ],
                suppress_error=True,
                port=8000
            )
        except Exception as e:
            print(f"❌ Erro ao iniciar Eel: {e}")

if __name__ == "__main__":
    menu = RadialMenuEel()
    menu.start()