# app.py
import gradio as gr
import requests
import random
import urllib.parse
import tempfile
import os

# --- Constants ---
VOICES = [
    "alloy", "echo", "fable", "onyx", "nova", "shimmer",  # Standard OpenAI Voices
    "coral", "verse", "ballad", "ash", "sage", "amuch", "dan" # Additional Pollinations Voices? (Assuming based on list)
]

NSFW_URL_TEMPLATE = "https://text.pollinations.ai/Is this an inappropriate text-to-speech prompt \"{prompt}\". If yes then write \"YES\" only otherwise \"NO\" only"
TTS_URL_TEMPLATE = "https://text.pollinations.ai/only repeat what i say now say with proper emphasis in a \"{emotion}\" emotion this statement - \"{prompt}\"?model=openai-audio&voice={voice}&seed={seed}"

# --- Helper Functions ---

def check_nsfw(prompt: str) -> bool:
    """Checks if the prompt is NSFW using the Pollinations API."""
    try:
        # URL encode the prompt for safety
        encoded_prompt = urllib.parse.quote(prompt)
        url = NSFW_URL_TEMPLATE.format(prompt=encoded_prompt)
        print(f"DEBUG: Checking NSFW URL: {url}") # Optional: for debugging

        response = requests.get(url, timeout=20) # Added timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        result = response.text.strip().upper()
        print(f"DEBUG: NSFW Check Response: '{result}'") # Optional: for debugging

        if result == "YES":
            return True
        elif result == "NO":
            return False
        else:
            # Handle unexpected responses from the NSFW checker
            print(f"Warning: Unexpected response from NSFW checker: {response.text}")
            # Defaulting to safe might be risky, maybe default to NSFW? Or raise error?
            # Let's default to considering it potentially unsafe if unsure.
            return True # Treat unexpected responses as potentially NSFW

    except requests.exceptions.RequestException as e:
        print(f"Error during NSFW check: {e}")
        # If the check fails, maybe treat as unsafe to be cautious
        raise gr.Error(f"Failed to check prompt safety: {e}")
    except Exception as e:
        print(f"Unexpected error during NSFW check: {e}")
        raise gr.Error(f"An unexpected error occurred during safety check: {e}")


def generate_audio(prompt: str, voice: str, emotion: str, seed: int) -> bytes:
    """Generates audio using the Pollinations Text-to-Speech API."""
    try:
        # URL encode the prompt and emotion
        encoded_prompt = urllib.parse.quote(prompt)
        encoded_emotion = urllib.parse.quote(emotion)

        url = TTS_URL_TEMPLATE.format(
            prompt=encoded_prompt,
            emotion=encoded_emotion,
            voice=voice,
            seed=seed
        )
        print(f"DEBUG: Generating Audio URL: {url}") # Optional: for debugging

        response = requests.get(url, timeout=60) # Increased timeout for audio generation
        response.raise_for_status() # Raise an exception for bad status codes

        # Check if response content type suggests audio
        content_type = response.headers.get('content-type', '').lower()
        if 'audio' not in content_type:
            print(f"Warning: Unexpected content type received: {content_type}")
            print(f"Response Text: {response.text[:500]}") # Log beginning of text response
            raise gr.Error(f"API did not return audio. Response: {response.text[:200]}")

        return response.content # Return raw audio bytes

    except requests.exceptions.RequestException as e:
        print(f"Error during audio generation: {e}")
        # Try to get more info from response if available
        error_details = ""
        if hasattr(e, 'response') and e.response is not None:
            error_details = e.response.text[:200] # Get first 200 chars of error response
        raise gr.Error(f"Failed to generate audio: {e}. Details: {error_details}")
    except Exception as e:
        print(f"Unexpected error during audio generation: {e}")
        raise gr.Error(f"An unexpected error occurred during audio generation: {e}")

# --- Main Gradio Function ---

def text_to_speech_app(prompt: str, voice: str, emotion: str, use_random_seed: bool, specific_seed: int):
    """
    Main function for the Gradio app. Checks NSFW, then generates audio.
    Returns the path to a temporary audio file or an error message.
    """
    if not prompt:
        raise gr.Error("Prompt cannot be empty.")
    if not emotion:
        # Default emotion if none provided, or raise error? Let's default.
        emotion = "neutral"
        print("Warning: No emotion provided, defaulting to 'neutral'.")
        # raise gr.Error("Emotion cannot be empty.") # Alternative: require emotion
    if not voice:
         raise gr.Error("Please select a voice.")

    # 1. Determine Seed
    seed = random.randint(0, 2**32 - 1) if use_random_seed else int(specific_seed)
    print(f"Using Seed: {seed}")

    # 2. Check NSFW
    print("Checking prompt safety...")
    try:
        is_nsfw = check_nsfw(prompt)
    except gr.Error as e:
        # Propagate errors raised by check_nsfw
        return None, str(e) # Return None for audio, error message for text

    if is_nsfw:
        print("Prompt flagged as inappropriate.")
        # Return None for audio output, and a message for a text output
        return None, "Error: The prompt was flagged as inappropriate and cannot be processed."

    # 3. Generate Audio (only if not NSFW)
    print("Prompt is safe. Generating audio...")
    try:
        audio_bytes = generate_audio(prompt, voice, emotion, seed)

        # 4. Save audio to a temporary file for Gradio
        # Suffix is important for Gradio to recognize the format. Assuming MP3 based on common web usage.
        # If the API returns WAV, change suffix to ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
            temp_audio_file.write(audio_bytes)
            temp_file_path = temp_audio_file.name
            print(f"Audio saved temporarily to: {temp_file_path}")

        # Return the path to the temp file for the Audio component, and success message for Text
        return temp_file_path, f"Audio generated successfully with voice '{voice}', emotion '{emotion}', and seed {seed}."

    except gr.Error as e:
        # Handle errors raised by generate_audio
         return None, str(e) # Return None for audio, error message for text
    except Exception as e:
        print(f"Unexpected error in main function: {e}")
        return None, f"An unexpected error occurred: {e}"


# --- Gradio Interface ---

def toggle_seed_input(use_random_seed):
    """Updates the visibility of the specific seed input field."""
    return gr.update(visible=not use_random_seed, value=12345) # Reset to default when shown

with gr.Blocks() as app:
    gr.Markdown("# Text-to-Speech with NSFW Check")
    gr.Markdown(
        "Enter text, choose a voice and emotion, and generate audio. "
        "The text will be checked for appropriateness before generation."
    )

    with gr.Row():
        with gr.Column(scale=2):
            prompt_input = gr.Textbox(label="Prompt", placeholder="Enter the text you want to convert to speech...")
            emotion_input = gr.Textbox(label="Emotion Style", placeholder="e.g., happy, sad, excited, calm...")
            voice_dropdown = gr.Dropdown(label="Voice", choices=VOICES, value="alloy") # Default voice
        with gr.Column(scale=1):
            random_seed_checkbox = gr.Checkbox(label="Use Random Seed", value=True)
            seed_input = gr.Number(label="Specific Seed", value=12345, visible=False, precision=0) # Integer seed

    submit_button = gr.Button("Generate Audio", variant="primary")

    with gr.Row():
        audio_output = gr.Audio(label="Generated Audio", type="filepath") # Use filepath as we save temp file
        status_output = gr.Textbox(label="Status") # To display errors or success messages

    # --- Event Listeners ---
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
        outputs=[audio_output, status_output] # Output to both components
    )

    gr.Examples(
        examples=[
            ["Hello there! This is a test of the text-to-speech system.", "alloy", "neutral", True, 12345],
            ["What a beautiful day to build Gradio apps.", "shimmer", "happy", True, 12345],
            ["I am feeling a bit down today.", "fable", "sad", False, 9876],
            ["This technology is absolutely amazing!", "nova", "excited", True, 12345],
        ],
        inputs=[prompt_input, voice_dropdown, emotion_input, random_seed_checkbox, seed_input],
        outputs=[audio_output, status_output], # Outputs match the click function
        fn=text_to_speech_app, # The function to call for examples
        cache_examples=False, # Might be good to disable caching if APIs change or have quotas
    )

# --- Launch the App ---
if __name__ == "__main__":
    app.launch()
    