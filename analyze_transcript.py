import requests
import json
import logging
import sys

# --- Setup basic logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_thematic_analysis(transcript: str) -> dict:
    """
    Sends the transcript to a local Ollama server for thematic analysis,
    specifically identifying barriers and enablers to mobility.
    """
    ollama_url = "http://localhost:11434/api/generate"

    prompt = f"""
    Vous êtes un assistant de recherche qualitative spécialisé dans les études sur l'accessibilité et la mobilité urbaine.
    Votre unique tâche est d'analyser la transcription d'entrevue suivante avec une personne utilisant un appareil d'aide à la mobilité.
    Votre objectif est d'identifier les thèmes principaux liés aux 'obstacles' (ce qui rend les déplacements difficiles ou insécurisants) et aux 'facilitateurs' (ce qui aide ou sécurise les déplacements).

    Répondez UNIQUEMENT avec un objet JSON valide et rien d'autre. N'ajoutez aucune introduction, conclusion ou texte conversationnel.
    L'analyse et tout le contenu de la réponse JSON doivent être en français, la même langue que la transcription.

    L'objet JSON doit suivre ce schéma exact :
    {{
      "obstacles": [
        {{
          "nom_obstacle": "Un titre très court et descriptif de l'obstacle.",
          "resume": "Un résumé d'une phrase de l'obstacle.",
          "citations_directes": [
            "Une citation exacte de la transcription qui prouve cet obstacle.",
            "Une autre citation exacte."
          ]
        }}
      ],
      "facilitateurs": [
        {{
          "nom_facilitateur": "Un titre très court et descriptif du facilitateur.",
          "resume": "Un résumé d'une phrase du facilitateur.",
          "citations_directes": [
            "Une citation exacte de la transcription qui prouve ce facilitateur."
          ]
        }}
      ]
    }}

    Voici la transcription à analyser :
    ---
    {transcript}
    ---
    """

    payload = {
        "model": "llama3:latest",
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }

    try:
        logging.info("Sending analysis request to local Ollama server...")
        response = requests.post(ollama_url, data=json.dumps(payload))
        response.raise_for_status()
        logging.info("Received response from Ollama.")
        
        response_data_str = response.json().get("response", "{}")
        analysis_json = json.loads(response_data_str)
        return analysis_json

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response from Ollama: {response_data_str}")
        return {"error": "The model returned an invalid JSON response. Please try again.", "details": str(e)}
    except requests.exceptions.ConnectionError:
        logging.error("Connection to Ollama failed. Is it running?")
        return {"error": "Connection Error: Could not connect to the local Ollama server. Please ensure it is running."}
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred during the request: {e}")
        return {"error": f"An error occurred: {e}"}

# --- Main execution block to run the test ---
if __name__ == "__main__":
    # 1. Check if a file path was provided as a command-line argument.
    #    sys.argv is a list containing the script name and its arguments.
    #    len(sys.argv) should be 2: [script_name, file_path]
    if len(sys.argv) < 2:
        print("Error: Please provide the path to the transcript file.")
        print("Usage: python analyze_transcript.py /path/to/your/transcript.txt")
        sys.exit(1) # Exit the script with an error code

    # 2. Get the file path from the command-line arguments.
    #    sys.argv[0] is the script name itself, so sys.argv[1] is the first argument.
    transcript_file_path = sys.argv[1]

    try:
        # 3. Read the content from the provided file path
        logging.info(f"Reading transcript from: {transcript_file_path}")
        with open(transcript_file_path, 'r', encoding='utf-8') as f:
            transcript_content = f.read()
    except FileNotFoundError:
        print(f"Error: The file was not found at the specified path: {transcript_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        sys.exit(1)

    # 4. Run the analysis with the content read from the file
    analysis_result = run_thematic_analysis(transcript_content)
    
    # 5. Pretty-print the JSON result to the console
    print(json.dumps(analysis_result, indent=2, ensure_ascii=False))