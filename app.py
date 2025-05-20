# app.py
import gradio as gr
import requests
import random
import urllib.parse
import tempfile
import os

NSFW_URL_TEMPLATE = os.getenv("NSFW_API_URL_TEMPLATE")
TTS_URL_TEMPLATE = os.getenv("TTS_API_URL_TEMPLATE")

if not NSFW_URL_TEMPLATE:
    raise ValueError("Missing Secret: NSFW_API_URL_TEMPLATE is not set.")
if not TTS_URL_TEMPLATE:
    raise ValueError("Missing Secret: TTS_API_URL_TEMPLATE is not set.")

VOICES = [
    "alloy", "echo", "fable", "onyx", "nova", "shimmer",
    "coral", "verse", "ballad", "ash", "sage", "amuch", "dan"
]


def check_nsfw(prompt: str) -> bool:
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = NSFW_URL_TEMPLATE.format(prompt=encoded_prompt)
        print(f"DEBUG: Checking NSFW URL: {url.split('?')[0]}...")

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        result = response.text.strip().upper()
        return result != "NO"
    except Exception as e:
        print(f"NSFW check error: {e}")
        raise gr.Error("Safety check failed. Please try again.")


def generate_audio(prompt: str, voice: str, emotion: str, seed: int) -> bytes:
    try:
        url = TTS_URL_TEMPLATE.format(
            prompt=urllib.parse.quote(prompt),
            emotion=urllib.parse.quote(emotion),
            voice=voice,
            seed=seed
        )
        print(f"DEBUG: Audio URL: {url.split('?')[0]}...")
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        if 'audio' not in response.headers.get("content-type", "").lower():
            raise gr.Error("Invalid response: No audio returned.")

        return response.content
    except Exception as e:
        print(f"TTS error: {e}")
        raise gr.Error("Audio generation failed. Please try again.")


def text_to_speech_app(prompt, voice, emotion, use_random_seed, specific_seed):
    if not prompt:
        raise gr.Error("Prompt cannot be empty.")
    if not voice:
        raise gr.Error("Please select a voice.")
    if not emotion:
        emotion = "neutral"

    seed = random.randint(0, 2**32 - 1) if use_random_seed else int(specific_seed)
    print(f"Seed: {seed}")

    try:
        if check_nsfw(prompt):
            return None, "⚠️ Prompt flagged as inappropriate."
    except gr.Error as e:
        return None, str(e)

    try:
        audio_bytes = generate_audio(prompt, voice, emotion, seed)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(audio_bytes)
            return f.name, f"✅ Audio generated with voice '{voice}', emotion '{emotion}', seed {seed}."
    except gr.Error as e:
        return None, str(e)


def toggle_seed_input(use_random_seed):
    return gr.update(visible=not use_random_seed, value=12345)


def show_loading():
    return gr.update(value="⏳ Generating...", interactive=False), gr.update(interactive=False)


def hide_loading():
    return gr.update(value="", interactive=True), gr.update(interactive=True)


with gr.Blocks(theme=gr.themes.Base()) as app:
    gr.Markdown("""
    # 🎤 Advanced TTS Generator
    Convert your text into expressive speech using multiple voice styles.
    _Safe, fast, and unlimited!_

    ---
    """)

    with gr.Row():
        with gr.Column(scale=2):
            prompt_input = gr.Textbox(label="Prompt", placeholder="Type something...")
            emotion_input = gr.Textbox(label="Emotion Style", placeholder="e.g., happy, calm, angry...")
            voice_dropdown = gr.Dropdown(label="Voice", choices=VOICES, value="alloy")
        with gr.Column(scale=1):
            random_seed_checkbox = gr.Checkbox(label="Use Random Seed", value=True)
            seed_input = gr.Number(label="Specific Seed", value=12345, visible=False, precision=0)

    submit_button = gr.Button("✨ Generate Audio", variant="primary")
    loading_status = gr.Textbox(visible=False)

    with gr.Row():
        audio_output = gr.Audio(label="Generated Audio", type="filepath")
        status_output = gr.Textbox(label="Status", interactive=False)

    random_seed_checkbox.change(
        fn=toggle_seed_input,
        inputs=[random_seed_checkbox],
        outputs=[seed_input]
    )

    submit_button.click(
        fn=show_loading,
        inputs=[],
        outputs=[status_output, submit_button]
    ).then(
        fn=text_to_speech_app,
        inputs=[prompt_input, voice_dropdown, emotion_input, random_seed_checkbox, seed_input],
        outputs=[audio_output, status_output]
    ).then(
        fn=hide_loading,
        inputs=[],
        outputs=[status_output, submit_button]
    )

    gr.Examples(
        examples=[
            ["Hello! Testing text-to-speech.", "alloy", "neutral", True, 12345],
            ["I'm excited to show you what I can do!", "nova", "excited", True, 12345],
            ["This is surprisingly realistic.", "shimmer", "calm and robotic", False, 56789],
        ],
        inputs=[prompt_input, voice_dropdown, emotion_input, random_seed_checkbox, seed_input],
        outputs=[audio_output, status_output],
        fn=text_to_speech_app,
        cache_examples=False
    )

if __name__ == "__main__":
    if NSFW_URL_TEMPLATE and TTS_URL_TEMPLATE:
        app.launch()
    else:
        print("Missing environment variables for API URLs.")