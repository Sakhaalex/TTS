
# app_voice_clone.py

import gradio as gr
import requests
import random
import urllib.parse
import tempfile
import os

NSFW_URL_TEMPLATE = os.getenv("NSFW_API_URL_TEMPLATE")
TTS_URL_TEMPLATE = os.getenv("TTS_API_URL_TEMPLATE")
XTTS_API_URL = os.getenv("XTTS_CLONE_API_URL")  # NEW: Your custom XTTS-style backend

if not NSFW_URL_TEMPLATE or not TTS_URL_TEMPLATE or not XTTS_API_URL:
    raise ValueError("Missing Secret: One or more API URLs are not set.")

VOICES = [
    "alloy", "echo", "fable", "onyx", "nova", "shimmer",
    "coral", "verse", "ballad", "ash", "sage", "amuch", "dan"
]


def check_nsfw(prompt: str) -> bool:
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = NSFW_URL_TEMPLATE.format(prompt=encoded_prompt)
        response = requests.get(url, timeout=20)
        result = response.text.strip().upper()
        return result == "YES"
    except:
        raise gr.Error("Prompt safety check failed.")


def generate_standard_audio(prompt: str, voice: str, emotion: str, seed: int) -> bytes:
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        encoded_emotion = urllib.parse.quote(emotion)
        url = TTS_URL_TEMPLATE.format(prompt=encoded_prompt, emotion=encoded_emotion, voice=voice, seed=seed)
        response = requests.get(url, timeout=60)
        if 'audio' not in response.headers.get('content-type', ''):
            raise gr.Error("API did not return audio.")
        return response.content
    except:
        raise gr.Error("Audio generation failed.")


def generate_cloned_audio(prompt: str, reference_audio_path: str, emotion: str, seed: int) -> bytes:
    try:
        with open(reference_audio_path, 'rb') as f:
            files = {'reference': f}
            data = {'prompt': prompt, 'emotion': emotion, 'seed': seed}
            response = requests.post(XTTS_API_URL, files=files, data=data, timeout=90)
            response.raise_for_status()
            return response.content
    except:
        raise gr.Error("Voice cloning generation failed.")


def tts_main(prompt, voice, emotion, use_random_seed, seed_value, use_voice_clone, reference_audio):

    if not prompt:
        raise gr.Error("Prompt is required.")
    if use_voice_clone and reference_audio is None:
        raise gr.Error("Please upload a reference audio for voice cloning.")

    seed = random.randint(0, 2**32 - 1) if use_random_seed else int(seed_value)

    if check_nsfw(prompt):
        return None, "Prompt is unsafe."

    try:
        if use_voice_clone:
            audio_bytes = generate_cloned_audio(prompt, reference_audio, emotion, seed)
        else:
            if not voice:
                raise gr.Error("Please select a voice.")
            audio_bytes = generate_standard_audio(prompt, voice, emotion, seed)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            temp_audio.write(audio_bytes)
            return temp_audio.name, f"Audio generated successfully. Voice cloning: {use_voice_clone}"
    except Exception as e:
        return None, str(e)


def toggle_seed_input(use_random):
    return gr.update(visible=not use_random, value=12345)


with gr.Blocks() as app:
    gr.Markdown("# 🧠 High-Grade Voice Cloning TTS")
    gr.Markdown("Generate speech with your own voice! Upload a reference voice and enter text with optional emotion and seed.")

    with gr.Row():
        with gr.Column(scale=2):
            prompt_input = gr.Textbox(label="Prompt", placeholder="Enter your text here...")
            emotion_input = gr.Textbox(label="Emotion Style", placeholder="e.g., suspenseful, calm, excited...")
            voice_clone_toggle = gr.Checkbox(label="Use Voice Cloning", value=False)
            voice_dropdown = gr.Dropdown(label="Voice (if not cloning)", choices=VOICES, value="alloy")
            reference_input = gr.Audio(label="Upload Reference Voice", type="filepath", visible=True)
        with gr.Column(scale=1):
            random_seed_checkbox = gr.Checkbox(label="Use Random Seed", value=True)
            seed_input = gr.Number(label="Specific Seed", value=12345, visible=False, precision=0)

    submit_button = gr.Button("Generate Audio 🔊")

    with gr.Row():
        audio_output = gr.Audio(label="Output Audio", type="filepath")
        status_output = gr.Textbox(label="Status")

    # Dynamic visibility
    random_seed_checkbox.change(fn=toggle_seed_input, inputs=[random_seed_checkbox], outputs=[seed_input])

    # Trigger
    submit_button.click(
        fn=tts_main,
        inputs=[prompt_input, voice_dropdown, emotion_input, random_seed_checkbox, seed_input, voice_clone_toggle, reference_input],
        outputs=[audio_output, status_output]
    )

if __name__ == "__main__":
    app.launch()
