# Documentacao - Fallback de Audio (sounddevice -> winsound/ffplay)

## Objetivo
Garantir que a Luna continue tocando audio mesmo quando o `sounddevice` falha
(ex: erro do DirectSound no Windows).

## O que mudou
Arquivo: `core/voice.py`

Funcao: `_tocar_audio_arquivo`

Antes:
- Se `sounddevice` falhava e `LUNA_AUDIO_DEVICE` estava definido, o erro podia
  interromper a fala e nada era reproduzido.

Depois:
- Se `sounddevice` falhar, o codigo registra o aviso e faz fallback automatico
  para `winsound` (WAV) e, se necessario, `ffplay`.
- Resultado: mesmo com erro de DirectSound, o audio continua saindo.

## Por que isso foi necessario
A configuracao no `.env` nao era suficiente porque o Windows estava bloqueando
o dispositivo (ou o DirectSound falhava). O fallback evita o silencio total.

## Como alternar a saida no futuro
1. Ajuste o dispositivo no Windows (permitir uso).
2. Atualize o `.env`:
   - Alto-falante:
     `LUNA_AUDIO_DEVICE=Alto-falantes (2- Realtek(R) Audio)`
   - Cabo virtual:
     `LUNA_AUDIO_DEVICE=CABLE Input (VB-Audio Virtual Cable)`
   - Ou vazio para usar o padrao do Windows:
     `LUNA_AUDIO_DEVICE=`

Se mesmo assim ocorrer erro de DirectSound, o fallback continuara garantindo
audio.

