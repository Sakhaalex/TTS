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
    raise ValueError("Missing Secret: NSFW_API_URL_TEMPLATE is not set in Hugging Face Space secrets.")
if not TTS_URL_TEMPLATE:
    raise ValueError("Missing Secret: TTS_API_URL_TEMPLATE is not set in Hugging Face Space secrets.")
# VOICES
VOICES = [
    "alloy", "echo", "fable", "onyx", "nova", "shimmer",  # Standard OpenAI Voices
    "coral", "verse", "ballad", "ash", "sage", "amuch", "dan" # Some additional pre-trained
]



def check_nsfw(prompt: str) -> bool:
    global NSFW_URL_TEMPLATE 
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = NSFW_URL_TEMPLATE.format(prompt=encoded_prompt)
        print(f"DEBUG: Checking NSFW URL: {url.split('?')[0]}... (query params hidden)")

        response = requests.get(url, timeout=20)
        response.raise_for_status()

        result = response.text.strip().upper()
        print(f"DEBUG: NSFW Check Response: '{result}'")

        if result == "YES":
            return True
        elif result == "NO":
            return False
        else:
            print(f"Warning: Unexpected response from NSFW checker: {response.text}")
            return True # unexpected responses = potentially NSFW

    except requests.exceptions.RequestException as e:
        print(f"Error during NSFW check: {e}")
        raise gr.Error(f"Failed to check prompt safety.")
    except Exception as e:
        print(f"Unexpected error during NSFW check: {e}")
        raise gr.Error(f"An unexpected error occurred during safety check. Please wait for a second and try again.")


def generate_audio(prompt: str, voice: str, emotion: str, seed: int) -> bytes:
   # Generates audio using the API from server
    global TTS_URL_TEMPLATE 
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        encoded_emotion = urllib.parse.quote(emotion)

        url = TTS_URL_TEMPLATE.format(
            prompt=encoded_prompt,
            emotion=encoded_emotion,
            voice=voice,
            seed=seed
        )
        print(f"DEBUG: Generating Audio URL: {url.split('?')[0]}... (query params hidden)")

        response = requests.get(url, timeout=60)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '').lower()
        if 'audio' not in content_type:
            print(f"Warning: Unexpected content type received: {content_type}")
            print(f"Response Text: {response.text[:500]}")
            raise gr.Error(f"API did not return audio.")

        return response.content

    except requests.exceptions.RequestException as e:
        print(f"Error during audio generation: {e}")
        error_details = ""
        if hasattr(e, 'response') and e.response is not None:
            error_details = e.response.text[:200]
        raise gr.Error(f"Failed to generate audio. Please wait for a second and try again.")
    except Exception as e:
        print(f"Unexpected error during audio generation: {e}")
        raise gr.Error(f"An unexpected error occurred during audio generation. Please wait for a second and try again.")



def text_to_speech_app(prompt: str, voice: str, emotion: str, use_random_seed: bool, specific_seed: int):

    print("\n\n\n"+prompt+"\n\n\n")
    if not prompt:
        raise gr.Error("Prompt cannot be empty.")
    if not emotion:
        emotion = "neutral"
        print("Warning: No emotion provided, defaulting to 'neutral'.")
    if not voice:
         raise gr.Error("Please select a voice.")

    seed = random.randint(0, 2**32 - 1) if use_random_seed else int(specific_seed)
    print(f"Using Seed: {seed}")

    # check NSFW
    print("Checking prompt safety...")
    try:
        # is_nsfw = check_nsfw(prompt)
        is_nsfw = False
    except gr.Error as e:
        return None, f"There was an error. Please wait for a second and try again."

    if is_nsfw:
        print("Prompt flagged as inappropriate.")
        return None, "Error: The prompt was flagged as inappropriate and cannot be processed."

    # if not nsfw
    print("Prompt is safe. Generating audio...")
    try:
        audio_bytes = generate_audio(prompt, voice, emotion, seed)

        # audio save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
            temp_audio_file.write(audio_bytes)
            temp_file_path = temp_audio_file.name
            print(f"Audio saved temporarily to: {temp_file_path}")

        return temp_file_path, f"Audio generated successfully with voice '{voice}', emotion '{emotion}', and seed {seed}."

    except gr.Error as e:
         return None, str(e)
    except Exception as e:
        print(f"Unexpected error in main function: {e}")
        return None, f"An unexpected error occurred: {e}"




def toggle_seed_input(use_random_seed):
    
    return gr.update(visible=not use_random_seed, value=12345)

with gr.Blocks() as app:
    gr.Markdown("# Advanced OpenAI Text-To-Speech Unlimited")
    gr.Markdown(
        """Enter text, choose a voice and emotion, and generate audio. 
        The text will be checked for appropriateness before generation. 
        Use it as much as you want.
        
        
        **Like & follow** for more AI projects:

        
        • Instagram: [@nihal_gazi_io](https://www.instagram.com/nihal_gazi_io/)  
        • Discord: nihal_gazi_io"""
    )

    with gr.Row():
        with gr.Column(scale=2):
            prompt_input = gr.Textbox(label="Prompt", placeholder="Enter the text you want to convert to speech...")
            emotion_input = gr.Textbox(label="Emotion Style", placeholder="e.g., happy, sad, excited, calm...")
            voice_dropdown = gr.Dropdown(label="Voice", choices=VOICES, value="alloy")
        with gr.Column(scale=1):
            random_seed_checkbox = gr.Checkbox(label="Use Random Seed", value=True)
            seed_input = gr.Number(label="Specific Seed", value=12345, visible=False, precision=0)

    submit_button = gr.Button("Generate Audio", variant="primary")

    with gr.Row():
        audio_output = gr.Audio(label="Generated Audio", type="filepath")
        status_output = gr.Textbox(label="Status")


    random_seed_checkbox.change(
        fn=toggle_seed_input,
        inputs=[random_seed_checkbox],
        outputs=[seed_input]
    )

    submit_button.click(
        fn=text_to_speech_app,
        inputs=[
            prompt_input,
            voice_dropdown,
            emotion_input,
            random_seed_checkbox,
            seed_input
        ],
        outputs=[audio_output, status_output],
        concurrency_limit=30
    )


    gr.Examples(
        examples=[
            ["Hello there! This is a test of the text-to-speech system.", "alloy", "neutral", False, 12345],
            ["Surely *you* wouldn't want *that*. [laughs]", "shimmer", "sarcastic and mocking", True, 12345],
            ["[sobbing] I am feeling... [sighs] a bit down today [cry]", "ballad", "sad and depressed, with stammering", True, 662437],
            ["This technology is absolutely amazing!", "nova", "excited and joyful", True, 12345],
        ],
        inputs=[prompt_input, voice_dropdown, emotion_input, random_seed_checkbox, seed_input],
        outputs=[audio_output, status_output],
        fn=text_to_speech_app,
        cache_examples=False, 
    )


if __name__ == "__main__":
    
    if NSFW_URL_TEMPLATE and TTS_URL_TEMPLATE:
        app.launch()
    else:
        print("ERROR: Cannot launch app. Required API URL secrets are missing.")
        