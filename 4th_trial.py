import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import requests
import json
import time
from datetime import datetime
import os
import re

# Import libraries with error handling
try:
    import geocoder

    GEOCODER_AVAILABLE = True
except ImportError:
    GEOCODER_AVAILABLE = False
    print("⚠️ Geocoder not available. Install with: pip install geocoder")

try:
    import pyttsx3

    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("⚠️ Text-to-speech not available. Install with: pip install pyttsx3")

try:
    import serial
    import serial.tools.list_ports

    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("⚠️ PySerial not available. Install with: pip install pyserial")


class AgriGrokGUI:
    def __init__(self):
        # API configurations
        self.groq_config = {
            'api_key': "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",
            'base_url': "https://api.groq.com/openai/v1/chat/completions",
            'model': "llama3-8b-8192",
            'headers': {
                "Authorization": f"Bearer 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",
                "Content-Type": "application/json"
            }
        }

        self.cohere_config = {
            'api_key': "TPSf7KThMQ111e7n4l6czZ1zX4ZXHXtpuhefiNz5",
            'base_url': "https://api.cohere.ai/v1/chat",
            'model': "command-r-plus",
            'headers': {
                "Authorization": f"Bearer TPSf7KThMQ111e7n4l6czZ1zX4ZXHXtpuhefiNz5",
                "Content-Type": "application/json"
            }
        }

        # Initialize text-to-speech
        self.tts_engine = None
        self.voice_type = "none"
        self.setup_tts()

        self.system_prompt = """You are AgriGrok, an expert agricultural AI assistant for farmers and farming robots. 
        You specialize in: crop management, pest identification and control, irrigation systems, weather-based farming decisions, 
        soil health, fertilization, harvest timing, sustainable farming practices, and equipment maintenance. 
        Give practical, actionable advice in a friendly but professional manner. Keep responses clear, helpful, and focused on farming."""

        self.conversation_history = []
        self.location_data = None
        self.weather_data = None
        self.cache = {}
        self.voice_enabled = True
        self.is_speaking = False

        # Arduino shield connection
        self.arduino = None
        self.arduino_connected = False
        self.last_heartbeat = 0

        if SERIAL_AVAILABLE:
            self.setup_arduino_shield()

        self.setup_gui()

        # Start background threads
        threading.Thread(target=self.auto_detect_location, daemon=True).start()
        if SERIAL_AVAILABLE:
            threading.Thread(target=self.arduino_shield_listener, daemon=True).start()
            threading.Thread(target=self.arduino_heartbeat_monitor, daemon=True).start()

    def setup_tts(self):
        """Setup the most reliable TTS engine"""
        if TTS_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()

                # Get available voices
                voices = self.tts_engine.getProperty('voices')
                if voices:
                    # Enhanced voice selection
                    best_voice = None

                    # Look for David or Mark (best male voices)
                    for voice in voices:
                        voice_name = voice.name.lower()
                        if 'david' in voice_name and 'desktop' in voice_name:
                            best_voice = voice
                            break
                        elif 'mark' in voice_name:
                            best_voice = voice
                            break

                    if not best_voice:
                        for voice in voices:
                            voice_name = voice.name.lower()
                            if not any(female_term in voice_name for female_term in
                                       ['zira', 'cortana', 'hazel', 'female', 'eva', 'susan']):
                                best_voice = voice
                                break

                    if best_voice:
                        self.tts_engine.setProperty('voice', best_voice.id)
                        print(f"✅ Selected Voice: {best_voice.name}")

                # Optimize speech settings
                self.tts_engine.setProperty('rate', 175)
                self.tts_engine.setProperty('volume', 0.95)
                self.voice_type = "pyttsx3"

            except Exception as e:
                print(f"❌ TTS setup error: {e}")

    def setup_arduino_shield(self):
        """Setup connection to Arduino with mounted TFT shield"""
        try:
            # Auto-detect Arduino COM port
            ports = serial.tools.list_ports.comports()
            arduino_port = None

            print("🔍 Scanning for Arduino...")
            for port in ports:
                print(f"  Found: {port.device} - {port.description}")

                # Look for Arduino-like devices
                if any(keyword in port.description.lower() for keyword in
                       ['arduino', 'ch340', 'cp210', 'ftdi', 'usb serial']):
                    arduino_port = port.device
                    break

            if arduino_port:
                print(f"🔌 Connecting to Arduino on {arduino_port}...")
                self.arduino = serial.Serial(arduino_port, 9600, timeout=2)
                time.sleep(3)  # Give Arduino time to initialize shield

                # Send connection confirmation
                self.arduino.write(b'PYTHON_CONNECTED\n')
                self.arduino_connected = True
                self.last_heartbeat = time.time()

                print(f"✅ Arduino TFT Shield connected on {arduino_port}")
            else:
                print("⚠️ Arduino not found. Make sure it's connected via USB.")

        except Exception as e:
            print(f"❌ Arduino shield connection error: {e}")
            self.arduino_connected = False

    def arduino_shield_listener(self):
        """Listen for commands from Arduino TFT shield"""
        while True:
            try:
                if self.arduino and self.arduino.in_waiting > 0:
                    message = self.arduino.readline().decode().strip()
                    print(f"📱 Arduino: {message}")

                    if message.startswith("BUTTON_PRESSED:"):
                        command = message.split(":", 1)[1]
                        self.process_shield_command(command)

                    elif message == "ARDUINO_READY":
                        self.arduino.write(b'PYTHON_CONNECTED\n')
                        print("🖥️ Arduino TFT shield is ready")

                    elif message == "SHIELD_MOUNTED":
                        print("🛡️ TFT shield detected and mounted")

                    elif message == "HEARTBEAT":
                        self.arduino.write(b'PONG\n')
                        self.last_heartbeat = time.time()

                    elif message == "PONG":
                        self.last_heartbeat = time.time()

                time.sleep(0.1)

            except Exception as e:
                print(f"❌ Shield listener error: {e}")
                time.sleep(2)
                if not self.arduino_connected:
                    self.setup_arduino_shield()

    def arduino_heartbeat_monitor(self):
        """Monitor Arduino connection health"""
        while True:
            try:
                if self.arduino_connected:
                    if time.time() - self.last_heartbeat > 10:
                        print("⚠️ Arduino connection timeout")
                        self.arduino_connected = False
                        self.setup_arduino_shield()
                    elif time.time() - self.last_heartbeat > 8:
                        if self.arduino:
                            self.arduino.write(b'PING\n')

                time.sleep(2)

            except Exception as e:
                print(f"❌ Heartbeat monitor error: {e}")
                time.sleep(5)

    def process_shield_command(self, command):
        """Process command from TFT shield button press"""
        print(f"🎮 Processing shield command: {command}")

        if self.arduino:
            self.arduino.write(f"STATUS:Processing {command.replace('_', ' ')}...\n".encode())

        command_questions = {
            "SEASONAL_CROPS": lambda: self.generate_location_specific_crop_question(),
            "PEST_CONTROL": "How do I identify and control pests organically?",
            "IRRIGATION": "What's the best irrigation schedule for my crops?",
            "WEATHER": "How should current weather affect my farming decisions?",
            "HARVEST": "When is the optimal time to harvest my crops?",
            "EQUIPMENT": "What farming equipment maintenance should I do?",
            "FERTILIZER": "What are the best organic fertilizer recommendations?",
            "CROP_HEALTH": "How do I monitor and assess crop health?"
        }

        if command in command_questions:
            question_source = command_questions[command]

            if callable(question_source):
                question = question_source()
            else:
                question = self.enhance_with_context(question_source)

            threading.Thread(
                target=self.handle_shield_question,
                args=(question, command),
                daemon=True
            ).start()

    def enhance_with_context(self, base_question):
        """Add location and weather context to questions"""
        enhanced = base_question

        if self.location_data:
            enhanced += f" I'm located in {self.location_data['city']}, {self.location_data['country']}."

        if self.weather_data:
            temp = self.weather_data.get('current_temp', 0)
            humidity = self.weather_data.get('humidity', 0)
            enhanced += f" Current conditions: {temp}°C, {humidity}% humidity."

        return enhanced

    def handle_shield_question(self, question, command_type):
        """Handle question from TFT shield and return response"""
        try:
            self.root.after(0, lambda: self.add_user_message(f"[TFT Shield] {question}"))

            if self.arduino:
                self.arduino.write(b"STATUS:Getting AI response...\n")

            full_response = self.get_groq_response(question)

            if self.arduino:
                self.arduino.write(b"STATUS:Creating summary...\n")

            summary = self.get_cohere_summary(full_response)

            self.root.after(0, lambda: self.add_bot_message(full_response, summary))

            if self.arduino:
                shield_response = summary[:150] + "..." if len(summary) > 150 else summary
                self.arduino.write(f"RESPONSE:{shield_response}\n".encode())
                self.arduino.write(b"STATUS:Response displayed on screen\n")

            self.conversation_history.append({"role": "user", "content": question})
            self.conversation_history.append({"role": "assistant", "content": full_response})

            print(f"✅ Shield question processed: {command_type}")

        except Exception as e:
            error_msg = f"Error processing request: {str(e)[:100]}"
            print(f"❌ Shield question error: {e}")

            if self.arduino:
                self.arduino.write(f"RESPONSE:{error_msg}\n".encode())

    def clean_text_for_speech(self, text):
        """Clean and optimize text for natural speech"""
        clean_text = re.sub(r'[🌾🚜📍🤖👨‍🌾💧🌱🐛🌡️🔧🌿📊🌾🔊📝⚠️❌✅💾🗑️📤]', '', text)

        replacements = {
            '°C': ' degrees Celsius',
            '°F': ' degrees Fahrenheit',
            '%': ' percent',
            'mm': ' millimeters',
            'cm': ' centimeters',
            'kg': ' kilograms',
            'pH': ' P H level',
            'NPK': ' nitrogen phosphorus potassium',
            '&': ' and ',
            'vs.': '  versus ',
            'etc.': '  etcetera ',
            'e.g.': '  for example ',
            'i.e.': '  that is ',
        }

        for old, new in replacements.items():
            clean_text = clean_text.replace(old, new)

        clean_text = clean_text.replace('.', '.  ')
        clean_text = clean_text.replace(',', ',  ')
        clean_text = re.sub(r' +', ' ', clean_text)

        return clean_text.strip()

    def speak_text(self, text):
        """Convert text to speech"""
        if not self.voice_enabled or self.is_speaking or not text or self.voice_type == "none":
            return

        self.is_speaking = True

        def speak_async():
            try:
                clean_text = self.clean_text_for_speech(text)
                if self.tts_engine:
                    self.tts_engine.say(clean_text)
                    self.tts_engine.runAndWait()
            except Exception as e:
                print(f"❌ Speech error: {e}")
            finally:
                self.is_speaking = False

        threading.Thread(target=speak_async, daemon=True).start()

    def stop_speech(self):
        """Stop current speech"""
        try:
            if self.tts_engine:
                self.tts_engine.stop()
            self.is_speaking = False
        except Exception as e:
            print(f"❌ Stop speech error: {e}")

    def make_groq_request(self, messages):
        """Make request to Groq API"""
        payload = {
            "messages": messages,
            "model": self.groq_config['model'],
            "temperature": 0.7,
            "max_tokens": 800,
            "top_p": 0.9,
            "stream": False
        }

        response = requests.post(
            self.groq_config['base_url'],
            headers=self.groq_config['headers'],
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            raise Exception(f"Groq API Error {response.status_code}: {response.text}")

    def make_cohere_summarize_request(self, text_to_summarize):
        """Use Cohere to summarize response"""
        summarize_prompt = f"""Please summarize this agricultural advice into ONE clear, actionable sentence (maximum 10 words):

{text_to_summarize}

Summary:"""

        payload = {
            "message": summarize_prompt,
            "model": self.cohere_config['model'],
            "temperature": 0.3,
            "max_tokens": 25,
            "preamble": "You are a text summarizer. Create very concise, single-sentence summaries."
        }

        response = requests.post(
            self.cohere_config['base_url'],
            headers=self.cohere_config['headers'],
            json=payload,
            timeout=20
        )

        if response.status_code == 200:
            result = response.json()
            return result['text'].strip()
        else:
            raise Exception(f"Cohere API Error {response.status_code}: {response.text}")

    def get_cached_response(self, user_message):
        """Check for cached response"""
        message_key = user_message.lower().strip()[:100]

        for cached_key, cached_data in self.cache.items():
            if cached_key == message_key:
                if time.time() - cached_data['timestamp'] < 3600:
                    return cached_data['response'], cached_data['summary']
        return None, None

    def cache_response(self, user_message, full_response, summary):
        """Cache response and summary"""
        message_key = user_message.lower().strip()[:100]
        self.cache[message_key] = {
            'response': full_response,
            'summary': summary,
            'timestamp': time.time()
        }

        if len(self.cache) > 50:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]

    def auto_detect_location(self):
        """Detect location and get weather"""
        try:
            self.root.after(0, lambda: self.update_status("📍 Detecting your location..."))

            if GEOCODER_AVAILABLE:
                g = geocoder.ip('me')
                if g.ok:
                    self.location_data = {
                        'city': g.city,
                        'country': g.country,
                        'lat': g.latlng[0],
                        'lon': g.latlng[1],
                        'timezone': g.raw.get('timezone', 'Unknown')
                    }
                    self.get_weather_data()
                    self.root.after(0, lambda: self.update_status(
                        f"📍 Location detected: {self.location_data['city']}, {self.location_data['country']}"
                    ))
                else:
                    self.get_location_fallback()
            else:
                self.get_location_fallback()

        except Exception as e:
            print(f"Location detection error: {e}")
            self.root.after(0, lambda: self.update_status("⚠️ Could not detect location"))

    def get_location_fallback(self):
        """Fallback location detection"""
        try:
            response = requests.get('https://ipapi.co/json/', timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.location_data = {
                    'city': data.get('city', 'Unknown'),
                    'country': data.get('country_name', 'Unknown'),
                    'lat': data.get('latitude'),
                    'lon': data.get('longitude'),
                    'timezone': data.get('timezone', 'Unknown')
                }
                self.get_weather_data()
                self.root.after(0, lambda: self.update_status(
                    f"📍 Location detected: {self.location_data['city']}, {self.location_data['country']}"
                ))
        except Exception as e:
            print(f"Fallback location error: {e}")
            self.root.after(0, lambda: self.update_status("⚠️ Using general farming advice"))

    def get_weather_data(self):
        """Get weather data for location"""
        if not self.location_data or not self.location_data.get('lat'):
            return

        try:
            url = f"https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': self.location_data['lat'],
                'longitude': self.location_data['lon'],
                'current': 'temperature_2m,relative_humidity_2m,weather_code',
                'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum',
                'forecast_days': 7,
                'timezone': 'auto'
            }

            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                current = data.get('current', {})
                daily = data.get('daily', {})

                self.weather_data = {
                    'current_temp': current.get('temperature_2m', 0),
                    'humidity': current.get('relative_humidity_2m', 0),
                    'weather_code': current.get('weather_code', 0),
                    'max_temps': daily.get('temperature_2m_max', [])[:7],
                    'min_temps': daily.get('temperature_2m_min', [])[:7],
                    'precipitation': daily.get('precipitation_sum', [])[:7]
                }

                print(f"Weather data obtained: {self.weather_data}")
        except Exception as e:
            print(f"Weather data error: {e}")

    def get_season_from_location(self):
        """Determine season from location and date"""
        if not self.location_data:
            return "unknown"

        current_month = datetime.now().month
        lat = self.location_data.get('lat', 0)

        if lat >= 0:
            if current_month in [12, 1, 2]:
                return "winter"
            elif current_month in [3, 4, 5]:
                return "spring"
            elif current_month in [6, 7, 8]:
                return "summer"
            else:
                return "autumn"
        else:
            if current_month in [12, 1, 2]:
                return "summer"
            elif current_month in [3, 4, 5]:
                return "autumn"
            elif current_month in [6, 7, 8]:
                return "winter"
            else:
                return "spring"

    def generate_location_specific_crop_question(self):
        """Generate location-specific crop question"""
        if not self.location_data:
            return "What crops should I plant this season?"

        location_info = f"{self.location_data['city']}, {self.location_data['country']}"
        season = self.get_season_from_location()

        question = f"What crops should I plant in {location_info} during {season}?"

        if self.weather_data:
            temp = self.weather_data.get('current_temp', 0)
            humidity = self.weather_data.get('humidity', 0)
            question += f" Current temperature is {temp}°C and humidity is {humidity}%."

        return question

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("🌾 AgriGrok - Smart Farming Assistant")
        self.root.geometry("1000x750")
        self.root.configure(bg="#2e7d32")

        style = ttk.Style()
        style.theme_use('clam')

        main_frame = tk.Frame(self.root, bg="#2e7d32", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.create_header(main_frame)
        self.create_voice_controls(main_frame)
        self.create_chat_area(main_frame)
        self.create_quick_buttons(main_frame)
        self.create_input_area(main_frame)
        self.create_status_bar(main_frame)

        welcome_msg = "Welcome to AgriGrok! Your smart farming assistant is ready."
        self.add_bot_message(welcome_msg, "Ready to help with farming questions.")

    def create_header(self, parent):
        header_frame = tk.Frame(parent, bg="#1b5e20", relief=tk.RAISED, bd=2)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = tk.Label(header_frame, text="🌾 AgriGrok Smart Farming Assistant 🤖",
                               font=("Arial", 20, "bold"), fg="white", bg="#1b5e20", pady=15)
        title_label.pack()

        if SERIAL_AVAILABLE and self.arduino_connected:
            status_text = "🖥️ TFT Shield Connected | Groq + Cohere + Voice"
            status_color = "#4caf50"
        elif SERIAL_AVAILABLE:
            status_text = "🖥️ TFT Shield Disconnected | Groq + Cohere + Voice"
            status_color = "#f44336"
        else:
            status_text = "🖥️ No Serial Support | Groq + Cohere + Voice"
            status_color = "#ff9800"

        subtitle_label = tk.Label(header_frame, text=status_text,
                                  font=("Arial", 12), fg=status_color, bg="#1b5e20")
        subtitle_label.pack(pady=(0, 10))

    def create_voice_controls(self, parent):
        """Create voice control buttons"""
        voice_frame = tk.Frame(parent, bg="#2e7d32")
        voice_frame.pack(fill=tk.X, pady=(0, 10))

        voice_label = tk.Label(voice_frame, text="🔊 Voice Controls:",
                               font=("Arial", 12, "bold"), fg="white", bg="#2e7d32")
        voice_label.pack(side=tk.LEFT)

        # Test voice button
        self.test_btn = tk.Button(
            voice_frame,
            text="🎤 Test Voice",
            command=self.test_voice,
            bg="#2196f3",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5,
            cursor="hand2"
        )
        self.test_btn.pack(side=tk.RIGHT, padx=5)

        # Stop speech button
        self.stop_btn = tk.Button(
            voice_frame,
            text="⏹️ Stop",
            command=self.stop_speech,
            bg="#f44336",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5,
            cursor="hand2"
        )
        self.stop_btn.pack(side=tk.RIGHT, padx=5)

        # Voice toggle button
        self.voice_btn = tk.Button(
            voice_frame,
            text="🔊 Voice ON" if self.voice_enabled else "🔇 Voice OFF",
            command=self.toggle_voice,
            bg="#4caf50" if self.voice_enabled else "#f44336",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            bd=2,
            padx=15,
            pady=5,
            cursor="hand2"
        )
        self.voice_btn.pack(side=tk.RIGHT, padx=5)

        # Voice engine indicator
        engine_colors = {
            "pyttsx3": "#4caf50",
            "none": "#f44336"
        }

        engine_label = tk.Label(voice_frame, text=f"Engine: {self.voice_type.upper()}",
                                font=("Arial", 9, "bold"),
                                fg=engine_colors.get(self.voice_type, "#666"), bg="#2e7d32")
        engine_label.pack(side=tk.RIGHT, padx=10)

    def test_voice(self):
        """Test the voice system"""
        if self.voice_type == "none":
            messagebox.showwarning("No Voice", "No voice engine available!")
            return

        test_message = "Hello! This is AgriGrok voice test. The farming assistant is working perfectly."
        self.speak_text(test_message)
        self.update_status("🎤 Testing voice output...")

    def toggle_voice(self):
        """Toggle voice on/off"""
        if self.is_speaking:
            self.stop_speech()

        self.voice_enabled = not self.voice_enabled
        self.voice_btn.configure(
            text="🔊 Voice ON" if self.voice_enabled else "🔇 Voice OFF",
            bg="#4caf50" if self.voice_enabled else "#f44336"
        )

    def create_chat_area(self, parent):
        chat_container = tk.Frame(parent, bg="white", relief=tk.SUNKEN, bd=2)
        chat_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.chat_display = scrolledtext.ScrolledText(
            chat_container,
            wrap=tk.WORD,
            font=("Arial", 11),
            bg="#f8f9fa",
            fg="#333",
            relief=tk.FLAT,
            padx=15,
            pady=15,
            state=tk.DISABLED
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure text tags
        self.chat_display.tag_configure("user", foreground="#1976d2", font=("Arial", 11, "bold"))
        self.chat_display.tag_configure("bot", foreground="#2e7d32", font=("Arial", 11, "bold"))
        self.chat_display.tag_configure("summary", foreground="#ff6f00", font=("Arial", 12, "bold"))
        self.chat_display.tag_configure("timestamp", foreground="#666", font=("Arial", 9))

    def create_quick_buttons(self, parent):
        quick_frame = tk.Frame(parent, bg="#2e7d32")
        quick_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(quick_frame, text="🚀 Quick Questions:", font=("Arial", 12, "bold"),
                 fg="white", bg="#2e7d32").pack(anchor=tk.W, pady=(0, 5))

        button_frame1 = tk.Frame(quick_frame, bg="#2e7d32")
        button_frame1.pack(fill=tk.X, pady=2)
        button_frame2 = tk.Frame(quick_frame, bg="#2e7d32")
        button_frame2.pack(fill=tk.X, pady=2)

        quick_questions = [
            ("🌱 Seasonal Crops", lambda: self.send_seasonal_crops_question()),
            ("🐛 Pest Control", "How do I identify and control pests organically in my area?"),
            ("💧 Irrigation Tips", "What's the best irrigation schedule for my crops considering my local weather?"),
            ("🌡️ Weather Planning", "How should current weather conditions in my area affect my farming decisions?"),
            ("🌾 Harvest Time", "When is the optimal time to harvest my crops in my location?"),
            ("🔧 Equipment Care", "Robot and equipment maintenance tips for farming in my climate?"),
            ("🌿 Natural Fertilizers", "What are the best organic fertilizer recommendations for my region?"),
            ("📊 Crop Monitoring", "How do I monitor and assess crop health in my local climate conditions?")
        ]

        for i, (text, question) in enumerate(quick_questions):
            frame = button_frame1 if i < 4 else button_frame2

            if callable(question):
                btn = tk.Button(frame, text=text, command=question, bg="#4caf50", fg="white",
                                font=("Arial", 9, "bold"), relief=tk.RAISED, bd=2, padx=8, pady=4, cursor="hand2")
            else:
                btn = tk.Button(frame, text=text, command=lambda q=question: self.send_location_aware_question(q),
                                bg="#4caf50", fg="white", font=("Arial", 9, "bold"), relief=tk.RAISED, bd=2, padx=8,
                                pady=4, cursor="hand2")

            btn.pack(side=tk.LEFT, padx=2, pady=1, fill=tk.X, expand=True)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#66bb6a"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg="#4caf50"))

    def send_seasonal_crops_question(self):
        question = self.generate_location_specific_crop_question()
        self.user_input.delete(1.0, tk.END)
        self.user_input.insert(1.0, question)
        self.user_input.configure(fg="black")
        self.send_message()

    def send_location_aware_question(self, base_question):
        enhanced_question = self.enhance_with_context(base_question)
        self.user_input.delete(1.0, tk.END)
        self.user_input.insert(1.0, enhanced_question)
        self.user_input.configure(fg="black")
        self.send_message()

    def create_input_area(self, parent):
        input_frame = tk.Frame(parent, bg="#2e7d32")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        self.user_input = tk.Text(input_frame, height=3, font=("Arial", 11),
                                  wrap=tk.WORD, relief=tk.SUNKEN, bd=2)
        self.user_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.user_input.insert(1.0, "Ask me anything about farming... (Press Ctrl+Enter to send)")
        self.user_input.configure(fg="gray")
        self.user_input.bind("<FocusIn>", self.clear_placeholder)
        self.user_input.bind("<FocusOut>", self.add_placeholder)
        self.user_input.bind("<Control-Return>", lambda e: self.send_message())

        btn_frame = tk.Frame(input_frame, bg="#2e7d32")
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.send_btn = tk.Button(btn_frame, text="📤 Send", command=self.send_message,
                                  bg="#4caf50", fg="white", font=("Arial", 12, "bold"),
                                  relief=tk.RAISED, bd=3, padx=20, pady=10, cursor="hand2")
        self.send_btn.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.clear_btn = tk.Button(btn_frame, text="🗑️ Clear", command=self.clear_chat,
                                   bg="#ff9800", fg="white", font=("Arial", 10, "bold"),
                                   relief=tk.RAISED, bd=2, padx=20, pady=5, cursor="hand2")
        self.clear_btn.pack(fill=tk.X)

        self.send_btn.bind("<Enter>", lambda e: self.send_btn.configure(bg="#66bb6a"))
        self.send_btn.bind("<Leave>", lambda e: self.send_btn.configure(bg="#4caf50"))
        self.clear_btn.bind("<Enter>", lambda e: self.clear_btn.configure(bg="#ffb74d"))
        self.clear_btn.bind("<Leave>", lambda e: self.clear_btn.configure(bg="#ff9800"))

    def create_status_bar(self, parent):
        self.status_frame = tk.Frame(parent, bg="#1b5e20", relief=tk.SUNKEN, bd=1)
        self.status_frame.pack(fill=tk.X)

        self.status_label = tk.Label(self.status_frame, text=f"🔍 Ready with {self.voice_type.upper()} voice engine",
                                     fg="white", bg="#1b5e20", font=("Arial", 10), anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        save_btn = tk.Button(self.status_frame, text="💾 Save Chat", command=self.save_conversation,
                             bg="#607d8b", fg="white", font=("Arial", 9), relief=tk.RAISED, bd=1,
                             padx=10, pady=2, cursor="hand2")
        save_btn.pack(side=tk.RIGHT, padx=10, pady=2)

    def clear_placeholder(self, event):
        if self.user_input.get(1.0, tk.END).strip() == "Ask me anything about farming... (Press Ctrl+Enter to send)":
            self.user_input.delete(1.0, tk.END)
            self.user_input.configure(fg="black")

    def add_placeholder(self, event):
        if not self.user_input.get(1.0, tk.END).strip():
            self.user_input.insert(1.0, "Ask me anything about farming... (Press Ctrl+Enter to send)")
            self.user_input.configure(fg="gray")

    def add_message_to_chat(self, sender, message, tag_prefix):
        self.chat_display.configure(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.chat_display.insert(tk.END, f"{sender}: ", tag_prefix)
        formatted_message = message.replace('\n', '\n    ')
        self.chat_display.insert(tk.END, f"{formatted_message}\n\n")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def add_bot_message(self, full_response, summary=None):
        self.add_message_to_chat("🤖 AgriGrok [via GROQ]", full_response, "bot")

        if summary:
            self.chat_display.configure(state=tk.NORMAL)
            self.chat_display.insert(tk.END, "📝 Voice Summary [via COHERE]: ", "summary")
            self.chat_display.insert(tk.END, f"{summary}\n\n")
            self.chat_display.configure(state=tk.DISABLED)
            self.chat_display.see(tk.END)

            self.speak_text(summary)

    def add_user_message(self, message):
        self.add_message_to_chat("👨‍🌾 You", message, "user")

    def update_status(self, message):
        self.status_label.configure(text=message)
        self.root.update_idletasks()

    def send_message(self):
        user_message = self.user_input.get(1.0, tk.END).strip()
        if not user_message or user_message == "Ask me anything about farming... (Press Ctrl+Enter to send)":
            messagebox.showwarning("Empty Message", "Please enter a question about farming!")
            return

        if self.is_speaking:
            self.stop_speech()

        cached_response, cached_summary = self.get_cached_response(user_message)
        if cached_response:
            self.add_user_message(user_message)
            self.add_bot_message(f"{cached_response}\n\n[Cached Response]", cached_summary)
            self.user_input.delete(1.0, tk.END)
            return

        self.add_user_message(user_message)
        self.user_input.delete(1.0, tk.END)
        self.send_btn.configure(state=tk.DISABLED, text="⏳ Processing...")
        self.update_status("🤖 Getting detailed answer from Groq...")

        threading.Thread(target=self.get_dual_response_thread, args=(user_message,), daemon=True).start()

    def get_dual_response_thread(self, user_message):
        try:
            full_response = self.get_groq_response(user_message)

            self.root.after(0, lambda: self.update_status("📝 Creating voice summary..."))
            summary = self.get_cohere_summary(full_response)

            self.cache_response(user_message, full_response, summary)

            self.root.after(0, lambda: self.handle_dual_response(full_response, summary))

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.root.after(0, lambda: self.handle_dual_response(error_msg, "Error occurred"))

    def get_groq_response(self, user_message):
        """Get detailed response from Groq"""
        enhanced_system_prompt = self.system_prompt

        if self.location_data or self.weather_data:
            enhanced_system_prompt += "\n\nCONTEXT INFORMATION:\n"

            if self.location_data:
                season = self.get_season_from_location()
                enhanced_system_prompt += f"User Location: {self.location_data['city']}, {self.location_data['country']}\n"
                enhanced_system_prompt += f"Current Season: {season}\n"

            if self.weather_data:
                enhanced_system_prompt += f"Current Weather:\n"
                enhanced_system_prompt += f"- Temperature: {self.weather_data['current_temp']}°C\n"
                enhanced_system_prompt += f"- Humidity: {self.weather_data['humidity']}%\n"

        messages = [
            {"role": "system", "content": enhanced_system_prompt},
            *self.conversation_history[-6:],
            {"role": "user", "content": user_message}
        ]

        return self.make_groq_request(messages)

    def get_cohere_summary(self, full_response):
        """Get speech-optimized summary from Cohere"""
        return self.make_cohere_summarize_request(full_response)

    def handle_dual_response(self, full_response, summary):
        self.add_bot_message(full_response, summary)

        self.conversation_history.append({"role": "assistant", "content": full_response})

        self.send_btn.configure(state=tk.NORMAL, text="📤 Send")

        location_text = ""
        if self.location_data:
            location_text = f" | 📍 {self.location_data['city']}, {self.location_data['country']}"

        voice_status = f"🔊 {self.voice_type.upper()}" if self.voice_enabled else "🔇 OFF"
        self.update_status(f"✅ Ready! Voice: {voice_status}{location_text}")

    def clear_chat(self):
        if messagebox.askyesno("Clear Chat", "Are you sure you want to clear the conversation?"):
            self.stop_speech()
            self.chat_display.configure(state=tk.NORMAL)
            self.chat_display.delete(1.0, tk.END)
            self.chat_display.configure(state=tk.DISABLED)
            self.conversation_history = []
            self.cache = {}

            welcome_msg = "Chat cleared! How can I help you with farming today?"
            self.add_bot_message(welcome_msg, "Ready to help with farming questions.")

    def save_conversation(self):
        if not self.conversation_history:
            messagebox.showinfo("No Conversation", "No conversation to save yet!")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agrigrok_conversation_{timestamp}.json"

        try:
            save_data = {
                'conversation': self.conversation_history,
                'location_data': self.location_data,
                'weather_data': self.weather_data,
                'cache_count': len(self.cache),
                'voice_enabled': self.voice_enabled,
                'voice_type': self.voice_type,
                'arduino_connected': self.arduino_connected,
                'timestamp': timestamp
            }
            with open(filename, 'w') as f:
                json.dump(save_data, f, indent=2)
            messagebox.showinfo("Saved!", f"Conversation saved to {filename}")
            self.update_status(f"💾 Conversation saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.destroy()


def main():
    print("🌾 Starting AgriGrok with Arduino TFT Shield Support...")
    print("🔄 Dual AI Mode: Groq (answers) + Cohere (summaries)")

    if SERIAL_AVAILABLE:
        print("✅ PySerial available for Arduino communication")
    else:
        print("⚠️ Install PySerial: pip install pyserial")

    if TTS_AVAILABLE:
        print("✅ Text-to-speech available")
    else:
        print("⚠️ Install TTS: pip install pyttsx3")

    app = AgriGrokGUI()
    app.run()


if __name__ == "__main__":
    main()
