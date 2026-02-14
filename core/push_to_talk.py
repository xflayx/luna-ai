# core/push_to_talk.py
"""
Sistema Push-to-Talk para Luna
Suporta mltiplos mtodos de ativao:
- Tecla de atalho (ex: Ctrl+Space)
- Boto de mouse (ex: Mouse4)
- Controle de Xbox/Gamepad
- Pedal USB
- Interface web/painel
"""

import os
import time
import threading
import queue
import logging
import traceback
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum

import speech_recognition as sr

logger = logging.getLogger("PushToTalk")

# Configuraes
PTT_ENABLED = os.getenv("LUNA_PTT_ENABLED", "0") == "1"
PTT_METHOD = os.getenv("LUNA_PTT_METHOD", "keyboard").lower()  # keyboard, mouse, gamepad, pedal, web
PTT_KEY = os.getenv("LUNA_PTT_KEY", "ctrl+space")
PTT_MOUSE_BUTTON = os.getenv("LUNA_PTT_MOUSE_BUTTON", "x1")  # x1=Mouse4, x2=Mouse5
PTT_GAMEPAD_BUTTON = os.getenv("LUNA_PTT_GAMEPAD_BUTTON", "rb")  # rb, lb, a, b, x, y
PTT_VISUAL_FEEDBACK = os.getenv("LUNA_PTT_VISUAL_FEEDBACK", "1") == "1"
PTT_AUDIO_FEEDBACK = os.getenv("LUNA_PTT_AUDIO_FEEDBACK", "1") == "1"
PTT_TIMEOUT_SEC = float(os.getenv("LUNA_PTT_TIMEOUT_SEC", "30"))
PTT_MIN_DURATION_SEC = float(os.getenv("LUNA_PTT_MIN_DURATION_SEC", "0.3"))
PTT_KEY_DEBUG = os.getenv("LUNA_PTT_KEY_DEBUG", "0") == "1"
PTT_STT_ENGINE = os.getenv("LUNA_PTT_STT_ENGINE", "sr").lower()  # sr, faster_whisper
PTT_FW_MODEL = os.getenv("LUNA_PTT_FW_MODEL", "base")
PTT_FW_DEVICE = os.getenv("LUNA_PTT_FW_DEVICE", "cpu")
PTT_FW_COMPUTE = os.getenv("LUNA_PTT_FW_COMPUTE", "float32")
PTT_FW_LANGUAGE = os.getenv("LUNA_PTT_FW_LANGUAGE", "pt")
PTT_FW_SAMPLE_RATE = int(os.getenv("LUNA_PTT_FW_SAMPLE_RATE", "16000"))


class PTTState(Enum):
    """Estados do Push-to-Talk"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass
class PTTConfig:
    """Configurao do Push-to-Talk"""
    method: str
    key: str
    mouse_button: str
    gamepad_button: str
    visual_feedback: bool
    audio_feedback: bool
    timeout_sec: float
    min_duration_sec: float
    stt_engine: str
    fw_model: str
    fw_device: str
    fw_compute: str
    fw_language: str
    fw_sample_rate: int


class PushToTalkManager:
    """
    Gerenciador de Push-to-Talk
    
    Funciona com qualquer mtodo de entrada e integra com o sistema de voz da Luna.
    """
    
    def __init__(self, config: Optional[PTTConfig] = None):
        self.config = config or self._load_config()
        self.state = PTTState.IDLE
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None
        self._recording_lock = threading.Lock()
        self.audio_queue: queue.Queue = queue.Queue(maxsize=10)
        self.listener_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self._fw_model = None
        self._recording_start_ts: float | None = None
        self._stop_timer: Optional[threading.Timer] = None
        
        # Importaes lazy
        self._keyboard_listener = None
        self._mouse_listener = None
        self._gamepad_listener = None
        
        # Callbacks
        self.on_start_recording: Optional[Callable] = None
        self.on_stop_recording: Optional[Callable] = None
        self.on_audio_ready: Optional[Callable[[str], None]] = None
        self.on_state_change: Optional[Callable[[PTTState], None]] = None
        
    def _load_config(self) -> PTTConfig:
        """Carrega configurao das variveis de ambiente"""
        return PTTConfig(
            method=PTT_METHOD,
            key=PTT_KEY,
            mouse_button=PTT_MOUSE_BUTTON,
            gamepad_button=PTT_GAMEPAD_BUTTON,
            visual_feedback=PTT_VISUAL_FEEDBACK,
            audio_feedback=PTT_AUDIO_FEEDBACK,
            timeout_sec=PTT_TIMEOUT_SEC,
            min_duration_sec=PTT_MIN_DURATION_SEC,
            stt_engine=PTT_STT_ENGINE,
            fw_model=PTT_FW_MODEL,
            fw_device=PTT_FW_DEVICE,
            fw_compute=PTT_FW_COMPUTE,
            fw_language=PTT_FW_LANGUAGE,
            fw_sample_rate=PTT_FW_SAMPLE_RATE,
        )
    
    def start(self):
        """Inicia o sistema Push-to-Talk"""
        if not PTT_ENABLED:
            logger.info("Push-to-Talk desabilitado")
            return
        
        logger.info(f"Iniciando Push-to-Talk: mtodo={self.config.method}")
        
        # Iniciar listener apropriado
        if self.config.method == "keyboard":
            self._start_keyboard_listener()
        elif self.config.method == "mouse":
            self._start_mouse_listener()
        elif self.config.method == "gamepad":
            self._start_gamepad_listener()
        elif self.config.method == "web":
            self._start_web_listener()
        else:
            logger.error(f"Mtodo PTT desconhecido: {self.config.method}")
            return
        
        logger.info(" Push-to-Talk ativo")
    
    def stop(self):
        """Para o sistema Push-to-Talk"""
        logger.info("Parando Push-to-Talk...")
        self.stop_event.set()
        
        if self.is_recording:
            self._stop_recording(force=True)
        
        # Parar listeners
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._gamepad_listener:
            self._gamepad_listener.stop()
        
        logger.info(" Push-to-Talk parado")
    
    def _set_state(self, new_state: PTTState):
        """Atualiza estado e notifica callbacks"""
        old_state = self.state
        self.state = new_state
        
        if old_state != new_state:
            logger.debug(f"PTT state: {old_state.value}  {new_state.value}")
            
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.error(f"Erro em on_state_change: {e}")
    
    def _start_recording(self):
        """Inicia gravao de udio"""
        if self.is_recording:
            logger.warning("J est gravando")
            return
        if self.recording_thread and self.recording_thread.is_alive():
            logger.warning("Thread de gravacao ainda ativa")
            return
        
        self.is_recording = True
        self._recording_start_ts = time.time()
        if self._stop_timer:
            try:
                self._stop_timer.cancel()
            except Exception:
                pass
            self._stop_timer = None
        self._set_state(PTTState.LISTENING)
        
        # Feedback visual
        if self.config.visual_feedback:
            self._show_visual_feedback(True)
        
        # Feedback sonoro
        if self.config.audio_feedback:
            self._play_sound("start")
        
        # Callback
        if self.on_start_recording:
            try:
                self.on_start_recording()
            except Exception as e:
                logger.error(f"Erro em on_start_recording: {e}")
        
        # Iniciar gravao em thread
        self.recording_thread = threading.Thread(
            target=self._recording_worker,
            daemon=True
        )
        self.recording_thread.start()
        
        logger.info(" Gravao iniciada")
    
    def _stop_recording(self, force: bool = False):
        """Para gravao de udio"""
        if not self.is_recording:
            logger.warning("No est gravando")
            return

        if not force:
            if self._recording_start_ts is not None:
                elapsed = time.time() - self._recording_start_ts
                if elapsed < self.config.min_duration_sec:
                    if self._stop_timer is None:
                        delay = max(0.0, self.config.min_duration_sec - elapsed)
                        self._stop_timer = threading.Timer(delay, self._stop_recording, kwargs={"force": True})
                        self._stop_timer.daemon = True
                        self._stop_timer.start()
                    return
        
        self.is_recording = False
        self._recording_start_ts = None
        if self._stop_timer:
            try:
                self._stop_timer.cancel()
            except Exception:
                pass
            self._stop_timer = None
        self._set_state(PTTState.PROCESSING)
        
        # Feedback visual
        if self.config.visual_feedback:
            self._show_visual_feedback(False)
        
        # Feedback sonoro
        if self.config.audio_feedback:
            self._play_sound("stop")
        
        # Callback
        if self.on_stop_recording:
            try:
                self.on_stop_recording()
            except Exception as e:
                logger.error(f"Erro em on_stop_recording: {e}")
        
        logger.info(" Gravao parada")
    
    def _recording_worker(self):
        """Worker thread que grava udio enquanto boto pressionado"""
        if self.config.stt_engine == "faster_whisper":
            self._recording_worker_faster_whisper()
            return

        from core.voice import rec, mic, _STT_ENGINE, _transcrever_groq, _vad_rejeitar_audio

        if not self._recording_lock.acquire(blocking=False):
            logger.warning("Gravacao ja em andamento (lock)")
            return
        try:
            with mic as source:
                rec.adjust_for_ambient_noise(source, duration=0.3)

                chunks = []
                sample_rate = None
                sample_width = None
                start_ts = time.time()

                # Captura em pequenos blocos para permitir parar ao soltar
                while self.is_recording:
                    if (time.time() - start_ts) > self.config.timeout_sec:
                        break
                    try:
                        audio = rec.listen(
                            source,
                            timeout=0.6,
                            phrase_time_limit=0.8,
                        )
                    except sr.WaitTimeoutError:
                        continue

                    if sample_rate is None:
                        sample_rate = audio.sample_rate
                        sample_width = audio.sample_width
                    chunks.append(audio.frame_data)

                if not chunks:
                    self._set_state(PTTState.IDLE)
                    return

                if sample_rate is None or sample_width is None:
                    self._set_state(PTTState.IDLE)
                    return

                audio = sr.AudioData(b"".join(chunks), sample_rate, sample_width)

                # Validar durao mnima
                duration = len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
                if duration < self.config.min_duration_sec:
                    logger.warning(f"udio muito curto: {duration:.2f}s < {self.config.min_duration_sec}s")
                    self._set_state(PTTState.IDLE)
                    return

                # VAD
                if _vad_rejeitar_audio(audio):
                    logger.warning("udio rejeitado pelo VAD (sem fala detectada)")
                    self._set_state(PTTState.IDLE)
                    return

                # Transcrever
                logger.info(" Transcrevendo...")
                texto = ""

                if _STT_ENGINE == "groq":
                    texto = _transcrever_groq(audio)
                    if not texto:
                        # Fallback para Google
                        texto = rec.recognize_google(audio, language="pt-BR")
                else:
                    texto = rec.recognize_google(audio, language="pt-BR")

                texto = (texto or "").lower().strip()

                if not texto:
                    logger.warning("Transcrio vazia")
                    self._set_state(PTTState.IDLE)
                    return

                logger.info(f"[PTT OUVIDO]: {texto}")

                # Notificar callback
                if self.on_audio_ready:
                    try:
                        self.on_audio_ready(texto)
                    except Exception as e:
                        logger.error(f"Erro em on_audio_ready: {e}")

                self._set_state(PTTState.IDLE)

        except sr.UnknownValueError:
            logger.warning("No consegui entender o udio")
            self._set_state(PTTState.IDLE)
        except Exception as e:
            logger.error(f"Erro na gravao: {e}")
            self._set_state(PTTState.ERROR)
        finally:
            try:
                self._recording_lock.release()
            except Exception:
                pass

    def _get_fw_model(self):
        if self._fw_model is not None:
            return self._fw_model
        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            raise RuntimeError(f"faster_whisper no disponivel: {e}")
        self._fw_model = WhisperModel(
            self.config.fw_model,
            device=self.config.fw_device,
            compute_type=self.config.fw_compute,
        )
        return self._fw_model

    def _recording_worker_faster_whisper(self):
        """Gravacao via sounddevice + transcricao com faster-whisper"""
        try:
            import sounddevice as sd
        except Exception as e:
            logger.error(f"sounddevice nao disponivel: {e}")
            self._set_state(PTTState.ERROR)
            return

        if not self._recording_lock.acquire(blocking=False):
            logger.warning("Gravacao ja em andamento (lock)")
            return
        try:
            samplerate = self.config.fw_sample_rate
            max_sec = float(self.config.timeout_sec)
            max_frames = int(max_sec * samplerate)
            if max_frames <= 0:
                max_frames = int(30 * samplerate)

            start_ts = time.time()
            recording = sd.rec(
                max_frames,
                samplerate=samplerate,
                channels=1,
                dtype="float32",
            )

            while self.is_recording and (time.time() - start_ts) < max_sec:
                time.sleep(0.05)

            sd.stop()

            elapsed = min(time.time() - start_ts, max_sec)
            frames = int(elapsed * samplerate)
            if frames <= 0:
                self._set_state(PTTState.IDLE)
                return

            audio = recording[:frames, 0]
            duration = frames / float(samplerate)
            if duration < self.config.min_duration_sec:
                logger.warning(f"udio muito curto: {duration:.2f}s < {self.config.min_duration_sec}s")
                self._set_state(PTTState.IDLE)
                return

            try:
                model = self._get_fw_model()
            except Exception as e:
                logger.error(f"Falha ao carregar faster_whisper: {e}")
                self._set_state(PTTState.ERROR)
                return

            logger.info(" Transcrevendo...")
            segments, _ = model.transcribe(
                audio,
                language=self.config.fw_language or None,
            )
            transcription = " ".join([segment.text for segment in segments])
            texto = (transcription or "").lower().strip()

            if not texto:
                logger.warning("Transcrio vazia")
                self._set_state(PTTState.IDLE)
                return

            logger.info(f"[PTT OUVIDO]: {texto}")

            if self.on_audio_ready:
                try:
                    self.on_audio_ready(texto)
                except Exception as e:
                    logger.error(f"Erro em on_audio_ready: {e}")

            self._set_state(PTTState.IDLE)
        except Exception as e:
            logger.error(f"Erro na gravao (faster_whisper): {e}")
            self._set_state(PTTState.ERROR)
        finally:
            try:
                self._recording_lock.release()
            except Exception:
                pass
    
    # =========================================================================
    # LISTENERS - KEYBOARD
    # =========================================================================
    
    def _start_keyboard_listener(self):
        """Inicia listener de teclas"""
        from pynput import keyboard
        
        hotkey_combo = self._parse_hotkey(self.config.key)
        modifiers = {"ctrl", "shift", "alt", "alt_gr", "cmd", "win"}
        has_modifier = any(k in modifiers for k in hotkey_combo)
        has_alpha = any(len(k) == 1 and k.isalpha() for k in hotkey_combo)
        stop_on_any_release = not (has_modifier and has_alpha)
        
        def on_activate():
            logger.debug(f"Hotkey ativada: {self.config.key}")
            self._start_recording()
        
        def on_deactivate():
            logger.debug(f"Hotkey desativada: {self.config.key}")
            self._stop_recording()
        
        # Listener com suporte a press e release
        current_keys = set()
        
        def on_press(key):
            try:
                key_name = self._key_to_name(key)
                if not key_name:
                    return
                key_name = self._normalize_key_name(key_name)
                current_keys.add(key_name)
                if PTT_KEY_DEBUG:
                    logger.debug(f"[PTT KEY] press={key_name} current={sorted(current_keys)}")
                
                # Checar se combo est pressionado
                if self._is_hotkey_active(current_keys, hotkey_combo):
                    if not self.is_recording:
                        on_activate()
            except Exception as e:
                logger.error(f"Erro no on_press: {e}")
                logger.debug(traceback.format_exc())
        
        def on_release(key):
            try:
                key_name = self._key_to_name(key)
                if not key_name:
                    return
                key_name = self._normalize_key_name(key_name)
                current_keys.discard(key_name)
                if PTT_KEY_DEBUG:
                    logger.debug(f"[PTT KEY] release={key_name} current={sorted(current_keys)}")
                
                # Se soltou tecla do combo, parar gravacao
                if self.is_recording:
                    if stop_on_any_release:
                        if key_name in hotkey_combo:
                            on_deactivate()
                    else:
                        if hotkey_combo.isdisjoint(current_keys):
                            on_deactivate()
            except Exception as e:
                logger.error(f"Erro no on_release: {e}")
                logger.debug(traceback.format_exc())
        
        self._keyboard_listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        self._keyboard_listener.start()
        
        logger.info(f"Keyboard listener iniciado: {self.config.key}")

    def _key_to_name(self, key) -> Optional[str]:
        """Normaliza a tecla do pynput para string simples"""
        try:
            if hasattr(key, "char") and key.char:
                ch = str(key.char)
                # Ctrl+<letra> pode virar caractere de controle (ex: Ctrl+L = \x0c)
                if len(ch) == 1 and ord(ch) < 32:
                    ch = chr(ord(ch) + 96)
                return ch.lower()
        except Exception:
            pass
        try:
            name = str(key).replace("Key.", "")
            return name.lower() if name else None
        except Exception:
            return None

    def _normalize_key_name(self, key_name: str) -> str:
        if key_name in ["ctrl_l", "ctrl_r"]:
            return "ctrl"
        if key_name in ["shift_l", "shift_r"]:
            return "shift"
        if key_name in ["alt_l", "alt_r", "alt_gr"]:
            return "alt"
        if key_name in ["cmd", "cmd_l", "cmd_r", "win", "win_l", "win_r"]:
            return "win"
        return key_name
    
    def _parse_hotkey(self, hotkey_str: str) -> set:
        """Parse hotkey string para conjunto de teclas"""
        # "ctrl+space"  {"ctrl", "space"}
        # "ctrl+shift+f"  {"ctrl", "shift", "f"}
        return set(k.strip().lower() for k in hotkey_str.split('+'))
    
    def _is_hotkey_active(self, current_keys: set, hotkey_combo: set) -> bool:
        """Checa se todas as teclas do combo esto pressionadas"""
        # Normalizar nomes de teclas especiais
        normalized_current = set()
        for key in current_keys:
            if key in ['ctrl_l', 'ctrl_r']:
                normalized_current.add('ctrl')
            elif key in ['shift_l', 'shift_r']:
                normalized_current.add('shift')
            elif key in ['alt_l', 'alt_r']:
                normalized_current.add('alt')
            else:
                normalized_current.add(key)
        
        return hotkey_combo.issubset(normalized_current)
    
    # =========================================================================
    # LISTENERS - MOUSE
    # =========================================================================
    
    def _start_mouse_listener(self):
        """Inicia listener de mouse"""
        from pynput import mouse
        
        button_map = {
            'x1': mouse.Button.x1,
            'x2': mouse.Button.x2,
            'left': mouse.Button.left,
            'right': mouse.Button.right,
            'middle': mouse.Button.middle,
        }
        
        target_button = button_map.get(self.config.mouse_button.lower())
        if not target_button:
            logger.error(f"Boto de mouse invlido: {self.config.mouse_button}")
            return
        
        def on_click(x, y, button, pressed):
            if button == target_button:
                if pressed:
                    self._start_recording()
                else:
                    self._stop_recording()
        
        self._mouse_listener = mouse.Listener(on_click=on_click)
        self._mouse_listener.start()
        
        logger.info(f"Mouse listener iniciado: {self.config.mouse_button}")
    
    # =========================================================================
    # LISTENERS - GAMEPAD
    # =========================================================================
    
    def _start_gamepad_listener(self):
        """Inicia listener de controle/gamepad"""
        try:
            import inputs
        except ImportError:
            logger.error("Mdulo 'inputs' no instalado. Instale com: pip install inputs")
            return
        
        def gamepad_worker():
            button_map = {
                'rb': 'BTN_TR',
                'lb': 'BTN_TL',
                'a': 'BTN_SOUTH',
                'b': 'BTN_EAST',
                'x': 'BTN_WEST',
                'y': 'BTN_NORTH',
            }
            
            target_button = button_map.get(self.config.gamepad_button.lower())
            if not target_button:
                logger.error(f"Boto de gamepad invlido: {self.config.gamepad_button}")
                return
            
            logger.info(f"Gamepad listener iniciado: {self.config.gamepad_button}")
            
            while not self.stop_event.is_set():
                try:
                    events = inputs.get_gamepad()
                    for event in events:
                        if event.code == target_button:
                            if event.state == 1:  # Pressionado
                                self._start_recording()
                            elif event.state == 0:  # Solto
                                self._stop_recording()
                except Exception as e:
                    logger.error(f"Erro no gamepad: {e}")
                    break
        
        self._gamepad_listener = threading.Thread(target=gamepad_worker, daemon=True)
        self._gamepad_listener.start()
    
    # =========================================================================
    # LISTENERS - WEB
    # =========================================================================
    
    def _start_web_listener(self):
        """
        Listener via WebSocket/HTTP
        Permite controlar PTT pelo painel web ou app mobile
        """
        # Este mtodo  controlado externamente pelo painel
        # Via chamadas a ptt_manager.start_recording() e ptt_manager.stop_recording()
        logger.info("Web listener ativo (controlado externamente)")
    
    def trigger_recording_start(self):
        """API pblica para iniciar gravao (ex: via web)"""
        self._start_recording()
    
    def trigger_recording_stop(self):
        """API pblica para parar gravao (ex: via web)"""
        self._stop_recording()
    
    # =========================================================================
    # FEEDBACK
    # =========================================================================
    
    def _show_visual_feedback(self, recording: bool):
        """Mostra feedback visual (OBS, LED, etc)"""
        try:
            from core.obs_client import update_text
            
            if recording:
                update_text(" GRAVANDO...", source_name="PTT_Status")
            else:
                update_text("", source_name="PTT_Status")
        except Exception as e:
            logger.debug(f"Feedback visual falhou: {e}")
    
    def _play_sound(self, sound_type: str):
        """Toca som de feedback"""
        import winsound
        
        try:
            if sound_type == "start":
                # Beep curto (1000 Hz, 100ms)
                winsound.Beep(1000, 100)
            elif sound_type == "stop":
                # Beep duplo (800 Hz, 50ms cada)
                winsound.Beep(800, 50)
                winsound.Beep(800, 50)
        except Exception as e:
            logger.debug(f"Feedback sonoro falhou: {e}")


# =========================================================================
# INSTNCIA GLOBAL
# =========================================================================

_ptt_manager: Optional[PushToTalkManager] = None


def get_ptt_manager() -> PushToTalkManager:
    """Retorna instncia global do PTT Manager"""
    global _ptt_manager
    if _ptt_manager is None:
        _ptt_manager = PushToTalkManager()
    return _ptt_manager


def iniciar_push_to_talk(on_audio_ready: Callable[[str], None]):
    """
    Inicializa Push-to-Talk e configura callback
    
    Args:
        on_audio_ready: Funo chamada quando udio transcrito est pronto
                       Recebe texto transcrito como argumento
    """
    if not PTT_ENABLED:
        return None
    
    ptt = get_ptt_manager()
    ptt.on_audio_ready = on_audio_ready
    
    # Callbacks opcionais para feedback
    ptt.on_start_recording = lambda: logger.info(" PTT: Gravao iniciada")
    ptt.on_stop_recording = lambda: logger.info(" PTT: Gravao parada")
    ptt.on_state_change = lambda state: logger.debug(f"PTT state  {state.value}")
    
    ptt.start()
    return ptt


def parar_push_to_talk():
    """Para o sistema Push-to-Talk"""
    global _ptt_manager
    if _ptt_manager:
        _ptt_manager.stop()
        _ptt_manager = None


# =========================================================================
# INTEGRAO COM PAINEL WEB
# =========================================================================

def adicionar_rotas_ptt(app):
    """
    Adiciona rotas Flask/SocketIO para controle via web
    
    Uso:
        from flask import Flask
        from flask_socketio import SocketIO
        
        app = Flask(__name__)
        socketio = SocketIO(app)
        
        adicionar_rotas_ptt(app)
    """
    from flask_socketio import emit
    
    @app.route("/ptt/status")
    def ptt_status():
        ptt = get_ptt_manager()
        return {
            "enabled": PTT_ENABLED,
            "method": ptt.config.method,
            "state": ptt.state.value,
            "is_recording": ptt.is_recording,
        }
    
    # WebSocket events
    def setup_socketio(socketio):
        @socketio.on('ptt_start')
        def handle_ptt_start():
            ptt = get_ptt_manager()
            ptt.trigger_recording_start()
            emit('ptt_state', {'state': 'listening'})
        
        @socketio.on('ptt_stop')
        def handle_ptt_stop():
            ptt = get_ptt_manager()
            ptt.trigger_recording_stop()
            emit('ptt_state', {'state': 'idle'})
    
    return setup_socketio


if __name__ == "__main__":
    # Teste standalone
    logging.basicConfig(level=logging.DEBUG)
    
    def on_audio(texto: str):
        print(f"\n TEXTO TRANSCRITO: {texto}\n")
    
    print(" Push-to-Talk Test")
    print(f"Mtodo: {PTT_METHOD}")
    print(f"Tecla: {PTT_KEY}")
    print("Pressione a tecla/boto configurado para gravar...")
    
    ptt = iniciar_push_to_talk(on_audio)
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nEncerrando...")
        parar_push_to_talk()


