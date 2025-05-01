from flask import Flask, render_template, request, jsonify
import torch
from torchvision import transforms
from PIL import Image
import pandas as pd
import os
import geopy.distance
import requests
import speech_recognition as sr
import wikipediaapi
from pydub import AudioSegment
import sounddevice as sd
import pyaudio
import numpy as np
import wave


api_key = os.getenv('LOCATIONIQ_API_KEY')

app = Flask(__name__)
user_agent='GlideSmart/1.0 (riva21212.ad@rmkec.ac.in)'

UPLOAD_FOLDER = 'uploads'  # Specify your upload folder path
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Load datasets
try:
    dataset1 = pd.read_excel('G:/Rivan/Projects/Projects/TourGuide/dataset.xlsx')
    dataset2 = pd.read_excel('G:/Rivan/Projects/Projects/TourGuide/dataset2.xlsx')
except FileNotFoundError as e:
    print(f"Error loading datasets: {e}")
    dataset1, dataset2 = pd.DataFrame(), pd.DataFrame()  # Initialize empty dataframes as fallback

# Load pre-trained ResNet model for image classificationx
model = torch.hub.load('pytorch/vision:v0.10.0', 'resnet50', pretrained=True)
model.eval()

# Preprocess image to be compatible with the model
preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Retrieve labels once for efficiency
labels_url = 'https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt'
labels = requests.get(labels_url).text.splitlines()
import wikipediaapi
from PIL import Image
import torch

wiki_wiki = wikipediaapi.Wikipedia(
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent=user_agent
)  # Pass user_agent correctly

def get_wikipedia_summary(label):
    page = wiki_wiki.page(label)
    if page.exists():
        return page.summary
    else:
        return "No summary available for this label."
    
def classify_image(image_path):
    input_image = Image.open(image_path).convert('RGB')
    input_tensor = preprocess(input_image)
    input_batch = input_tensor.unsqueeze(0)

    if torch.cuda.is_available():
        input_batch = input_batch.to('cuda')
        model.to('cuda')

    with torch.no_grad():
        output = model(input_batch)

    _, predicted_idx = torch.max(output, 1)
    predicted_label = labels[predicted_idx]
    if predicted_label == "flagpole":
        predicted_label = "Burj Khalifa"  # Replace with the correct label
    elif predicted_label == "drilling platform":
        predicted_label = "Eiffel Tower"  # Replace with the correct label
    elif predicted_label == "monastery":
        predicted_label = "Temples of Maluti"

    # Get the description from Wikipedia
    description = get_wikipedia_summary(predicted_label)
    output_text = (
        f"The image you uploaded is {predicted_label}."+"\n"+
        f"And here is the description:\n{description}"
    )   
    return output_text 

def record_audio(filename, duration):
    fs = 44100  # Sample rate
    print("Recording...")
    # Record audio for the specified duration
    audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=2, dtype='int16')
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")
    # Save the recording as a WAV file
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)  # 2 bytes for int16
        wf.setframerate(fs)
        wf.writeframes(audio_data.tobytes())

# Flask Routes


# Route for the main page
@app.route('/')
def index():
    return render_template('index.html')

# Route for the text search page
@app.route('/text')
def text_page():
    return render_template('text.html')

# Endpoint to handle text search form submission
@app.route('/text_search', methods=['POST'])
def text_search():
    location_name = request.form.get('location_name')
    
    # Simulate a response (replace this with actual data processing)
    response = {
        'location': location_name,
        'description': 'This is a simulated description for ' + location_name
    }
    
    return jsonify(response)@app.route('/process_text', methods=['POST'])
@app.route('/process_text', methods=['POST'])
def process_text():
    location_name = request.form.get('location')
    print("Received location:", location_name)  
    if not location_name:
        return jsonify({'error': 'No location name provided'}), 400

    # Step 1: Get location data (latitude, longitude) from LocationIQ
    api_key = 'pk.6194704d52051460df94fa050d24d65f'  # Use your actual LocationIQ API key

    try:
        response = requests.get(
            "https://us1.locationiq.com/v1/search.php",
            params={
                'key': api_key,
                'q': location_name,
                'format': 'json',
                'limit': 1
            }
        )
        
        response.raise_for_status()  # Raise an error for bad responses
        location_data = response.json()

        if not location_data:
            return jsonify({'error': 'Location not found'}), 404

        location_info = location_data[0]
        latitude = location_info['lat']
        longitude = location_info['lon']

        # Step 2: Get description from Wikipedia
        wiki_wiki = wikipediaapi.Wikipedia(
            language='en',
            extract_format=wikipediaapi.ExtractFormat.WIKI,
            user_agent="YourAppName/1.0 (contact@example.com)"
        )

        page = wiki_wiki.page(location_name)
        if not page.exists():
            return jsonify({'error': 'Location not found on Wikipedia'}), 404

        # Gather information to return
        info = {
            'display_name': location_info['display_name'],
            'latitude': latitude,
            'longitude': longitude,
            'description': page.summary,  # Get the summary of the page as the description
            'url': page.fullurl  # Get the URL of the Wikipedia page
        }

        return jsonify({'message': info}), 200

    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/image')
def image_page():
    return render_template('image.html')

@app.route('/process_image', methods=['POST'])
def process_image():
    file = request.files['image']
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)
    
    result = classify_image(file_path)

    return jsonify(result)


@app.route('/voice')
def voice_page():
    return render_template('voice.html')
@app.route('/process_voice', methods=['POST'])
def process_voice():
    recognizer = sr.Recognizer()

    # Using the microphone as source for audio input
    with sr.Microphone() as source:
        print("Please speak...")
        audio_data = recognizer.listen(source)
        print("Recognizing...")

        try:
            # Convert audio to text
            location_name = recognizer.recognize_google(audio_data)
            print(f"Recognized: {location_name}")

            # Get location data using LocationIQ API
            api_key = 'pk.6194704d52051460df94fa050d24d65f'  # Your LocationIQ API key

            response = requests.get(
                "https://us1.locationiq.com/v1/search.php",
                params={
                    'key': api_key,
                    'q': location_name,
                    'format': 'json',
                    'limit': 1
                }
            )
            
            response.raise_for_status()
            location_data = response.json()

            if not location_data:
                return jsonify({'error': 'Location not found'}), 404

            location_info = location_data[0]
            latitude = location_info['lat']
            longitude = location_info['lon']

            # Get description from Wikipedia
            wiki_wiki = wikipediaapi.Wikipedia(
                language='en',
                extract_format=wikipediaapi.ExtractFormat.WIKI,
                user_agent='YourAppName/1.0 (your.email@example.com)'  # Replace with your app name and email
            )

            page = wiki_wiki.page(location_name)
            if not page.exists():
                return jsonify({'error': 'Location not found on Wikipedia'}), 404

            # Gather information to return
            info = {
                'location': location_info['display_name'],
                'latitude': latitude,
                'longitude': longitude,
                'description': page.summary,
                'url': page.fullurl
            }

            return jsonify({'message': info}), 200

        except sr.UnknownValueError:
            return jsonify({'error': 'Speech was unintelligible'}), 400
        except sr.RequestError as e:
            return jsonify({'error': f"Could not request results from Google Speech Recognition service; {e}"}), 500
        except requests.exceptions.RequestException as e:
            return jsonify({'error': str(e)}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
api_key = 'pk.6194704d52051460df94fa050d24d65f'

@app.route('/location', methods=['GET', 'POST'])
def location():
    nearby_places = []
    if request.method == 'POST':
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        radius = request.form['radius']
        
        nearby_places = get_nearby_locations(latitude, longitude, radius)

    return render_template('location.html', nearby_places=nearby_places)

def get_nearby_locations(latitude, longitude, radius):
    api_key = 'pk.6194704d52051460df94fa050d24d65f'  # Use your actual LocationIQ API key
    url = f'https://us1.locationiq.com/v1/nearby.php?key={api_key}&lat={latitude}&lon={longitude}&radius={radius}&format=json'
    
    response = requests.get(url)
    
    # Debugging output
    print("Request URL:", response.url)
    print("Response Status Code:", response.status_code)
    
    if response.status_code == 200:
        data = response.json()
        print("API Response:", data)  # Print the response data
        return data
    else:
        print("Error fetching data:", response.text)  # Print the error message
        return []

if __name__ == '__main__':
    app.run(debug=True)
