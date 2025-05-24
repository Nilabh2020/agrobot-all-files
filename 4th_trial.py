import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import requests
import json
import time
from datetime import datetime
import os


class AgriGrokGUI:
    def __init__(self):
        self.api_key = "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"
        # Correct Grok API endpoint
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        self.system_prompt = """You are AgriGrok, an expert agricultural AI assistant for farmers and farming robots. 
        You specialize in: crop management, pest identification and control, irrigation systems, weather-based farming decisions, 
        soil health, fertilization, harvest timing, sustainable farming practices, and equipment maintenance. 
        Give practical, actionable advice in a friendly but professional manner. Keep responses clear, helpful, and focused on farming."""

        self.conversation_history = []
        self.setup_gui()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("🌾 AgriGrok - Smart Farming Assistant")
        self.root.geometry("1000x700")
        self.root.configure(bg="#2e7d32")

        # Configure styles
        style = ttk.Style()
        style.theme_use('clam')

        # Main container with padding
        main_frame = tk.Frame(self.root, bg="#2e7d32", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        self.create_header(main_frame)

        # Chat area
        self.create_chat_area(main_frame)

        # Quick buttons
        self.create_quick_buttons(main_frame)

        # Input area
        self.create_input_area(main_frame)

        # Status bar
        self.create_status_bar(main_frame)

        # Welcome message
        self.add_bot_message(
            "🌾 Welcome to AgriGrok! I'm your AI farming assistant ready to help with crops, pests, irrigation, weather planning, and more. How can I help you today? 🚜")

    def create_header(self, parent):
        header_frame = tk.Frame(parent, bg="#1b5e20", relief=tk.RAISED, bd=2)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = tk.Label(header_frame, text="🌾 AgriGrok Smart Farming Assistant 🤖",
                               font=("Arial", 20, "bold"), fg="white", bg="#1b5e20", pady=15)
        title_label.pack()

        subtitle_label = tk.Label(header_frame, text="AI-Powered Agricultural Guidance for Modern Farmers",
                                  font=("Arial", 12), fg="#a5d6a7", bg="#1b5e20")
        subtitle_label.pack(pady=(0, 10))

    def create_chat_area(self, parent):
        # Chat container
        chat_container = tk.Frame(parent, bg="white", relief=tk.SUNKEN, bd=2)
        chat_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Scrollable chat area
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

        # Configure text tags for styling
        self.chat_display.tag_configure("user", foreground="#1976d2", font=("Arial", 11, "bold"))
        self.chat_display.tag_configure("bot", foreground="#2e7d32", font=("Arial", 11, "bold"))
        self.chat_display.tag_configure("user_msg", background="#e3f2fd", relief=tk.RAISED, borderwidth=1)
        self.chat_display.tag_configure("bot_msg", background="#e8f5e8", relief=tk.RAISED, borderwidth=1)
        self.chat_display.tag_configure("timestamp", foreground="#666", font=("Arial", 9))

    def create_quick_buttons(self, parent):
        quick_frame = tk.Frame(parent, bg="#2e7d32")
        quick_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(quick_frame, text="🚀 Quick Questions:", font=("Arial", 12, "bold"),
                 fg="white", bg="#2e7d32").pack(anchor=tk.W, pady=(0, 5))

        # Create button frames for better organization
        button_frame1 = tk.Frame(quick_frame, bg="#2e7d32")
        button_frame1.pack(fill=tk.X, pady=2)

        button_frame2 = tk.Frame(quick_frame, bg="#2e7d32")
        button_frame2.pack(fill=tk.X, pady=2)

        quick_questions = [
            ("🌱 Seasonal Crops", "What crops should I plant this season based on current weather?"),
            ("🐛 Pest Control", "How do I identify and control pests organically?"),
            ("💧 Irrigation Tips", "What's the best irrigation schedule for my crops?"),
            ("🌡️ Weather Planning", "How should weather conditions affect my farming decisions?"),
            ("🌾 Harvest Time", "When is the optimal time to harvest my crops?"),
            ("🔧 Equipment Care", "Robot and equipment maintenance tips for farming?"),
            ("🌿 Natural Fertilizers", "What are the best organic fertilizer recommendations?"),
            ("📊 Crop Monitoring", "How do I monitor and assess crop health effectively?")
        ]

        # Distribute buttons across frames
        for i, (text, question) in enumerate(quick_questions):
            frame = button_frame1 if i < 4 else button_frame2
            btn = tk.Button(
                frame,
                text=text,
                command=lambda q=question: self.send_quick_question(q),
                bg="#4caf50",
                fg="white",
                font=("Arial", 9, "bold"),
                relief=tk.RAISED,
                bd=2,
                padx=8,
                pady=4,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=2, pady=1, fill=tk.X, expand=True)

            # Hover effects
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#66bb6a"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg="#4caf50"))

    def create_input_area(self, parent):
        input_frame = tk.Frame(parent, bg="#2e7d32")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        # Input field
        self.user_input = tk.Text(input_frame, height=3, font=("Arial", 11),
                                  wrap=tk.WORD, relief=tk.SUNKEN, bd=2)
        self.user_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Placeholder text
        self.user_input.insert(1.0, "Ask me anything about farming... (Press Ctrl+Enter to send)")
        self.user_input.configure(fg="gray")
        self.user_input.bind("<FocusIn>", self.clear_placeholder)
        self.user_input.bind("<FocusOut>", self.add_placeholder)
        self.user_input.bind("<Control-Return>", lambda e: self.send_message())

        # Button frame
        btn_frame = tk.Frame(input_frame, bg="#2e7d32")
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Send button
        self.send_btn = tk.Button(
            btn_frame,
            text="📤 Send",
            command=self.send_message,
            bg="#4caf50",
            fg="white",
            font=("Arial", 12, "bold"),
            relief=tk.RAISED,
            bd=3,
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.send_btn.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Clear button
        self.clear_btn = tk.Button(
            btn_frame,
            text="🗑️ Clear",
            command=self.clear_chat,
            bg="#ff9800",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=5,
            cursor="hand2"
        )
        self.clear_btn.pack(fill=tk.X)

        # Hover effects
        self.send_btn.bind("<Enter>", lambda e: self.send_btn.configure(bg="#66bb6a"))
        self.send_btn.bind("<Leave>", lambda e: self.send_btn.configure(bg="#4caf50"))
        self.clear_btn.bind("<Enter>", lambda e: self.clear_btn.configure(bg="#ffb74d"))
        self.clear_btn.bind("<Leave>", lambda e: self.clear_btn.configure(bg="#ff9800"))

    def create_status_bar(self, parent):
        self.status_frame = tk.Frame(parent, bg="#1b5e20", relief=tk.SUNKEN, bd=1)
        self.status_frame.pack(fill=tk.X)

        self.status_label = tk.Label(self.status_frame, text="✅ Ready to help with your farming questions!",
                                     fg="white", bg="#1b5e20", font=("Arial", 10), anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        # Save button in status bar
        save_btn = tk.Button(
            self.status_frame,
            text="💾 Save Chat",
            command=self.save_conversation,
            bg="#607d8b",
            fg="white",
            font=("Arial", 9),
            relief=tk.RAISED,
            bd=1,
            padx=10,
            pady=2,
            cursor="hand2"
        )
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

        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")

        # Add sender
        self.chat_display.insert(tk.END, f"{sender}: ", tag_prefix)

        # Add message with proper formatting
        formatted_message = message.replace('\n', '\n    ')
        self.chat_display.insert(tk.END, f"{formatted_message}\n\n")

        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def add_bot_message(self, message):
        self.add_message_to_chat("🤖 AgriGrok", message, "bot")

    def add_user_message(self, message):
        self.add_message_to_chat("👨‍🌾 You", message, "user")

    def send_quick_question(self, question):
        self.user_input.delete(1.0, tk.END)
        self.user_input.insert(1.0, question)
        self.user_input.configure(fg="black")
        self.send_message()

    def update_status(self, message):
        self.status_label.configure(text=message)
        self.root.update_idletasks()

    def send_message(self):
        user_message = self.user_input.get(1.0, tk.END).strip()

        if not user_message or user_message == "Ask me anything about farming... (Press Ctrl+Enter to send)":
            messagebox.showwarning("Empty Message", "Please enter a question about farming!")
            return

        # Add user message to chat
        self.add_user_message(user_message)

        # Clear input
        self.user_input.delete(1.0, tk.END)

        # Disable send button
        self.send_btn.configure(state=tk.DISABLED, text="⏳ Thinking...")
        self.update_status("🤖 AgriGrok is analyzing your farming question...")

        # Get response in separate thread
        threading.Thread(target=self.get_response_thread, args=(user_message,), daemon=True).start()

    def get_response_thread(self, user_message):
        try:
            response = self.get_grok_response(user_message)

            # Update GUI in main thread
            self.root.after(0, lambda: self.handle_response(response))

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.root.after(0, lambda: self.handle_response(error_msg))

    def handle_response(self, response):
        # Add bot response
        self.add_bot_message(response)

        # Re-enable send button
        self.send_btn.configure(state=tk.NORMAL, text="📤 Send")
        self.update_status("✅ Ready for your next farming question!")

    def get_grok_response(self, user_message):
        # Prepare messages for the API
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]

        # Add conversation history (keep last 4 exchanges for context)
        messages.extend(self.conversation_history[-8:])

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        # Payload for Groq API
        payload = {
            "messages": messages,
            "model": "llama-3.1-70b-versatile",  # Using Llama model available on Groq
            "temperature": 0.7,
            "max_tokens": 600,
            "top_p": 0.9,
            "stream": False
        }

        try:
            # Debug: Print the API call details
            print(f"Making API call to: {self.base_url}")
            print(f"Headers: {self.headers}")
            print(f"Payload model: {payload['model']}")

            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            print(f"Response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                bot_message = result['choices'][0]['message']['content']

                # Update conversation history
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": bot_message})

                return bot_message

            else:
                print(f"Error response: {response.text}")
                return f"⚠️ API Error {response.status_code}: {response.text}\n\nPlease check your API key or try again later."

        except requests.exceptions.Timeout:
            return "⏰ Request timed out. Please check your internet connection and try again."

        except requests.exceptions.ConnectionError:
            return "🌐 Connection error. Please check your internet connection."

        except json.JSONDecodeError:
            return "📊 Invalid response format from API. Please try again."

        except Exception as e:
            return f"❌ Unexpected error: {str(e)}\n\nPlease try again or check your API configuration."

    def clear_chat(self):
        if messagebox.askyesno("Clear Chat", "Are you sure you want to clear the conversation?"):
            self.chat_display.configure(state=tk.NORMAL)
            self.chat_display.delete(1.0, tk.END)
            self.chat_display.configure(state=tk.DISABLED)
            self.conversation_history = []
            self.add_bot_message("🌾 Chat cleared! How can I help you with farming today? 🚜")

    def save_conversation(self):
        if not self.conversation_history:
            messagebox.showinfo("No Conversation", "No conversation to save yet!")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agrigrok_conversation_{timestamp}.json"

        try:
            with open(filename, 'w') as f:
                json.dump(self.conversation_history, f, indent=2)

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
    print("🌾 Starting AgriGrok Farming Assistant...")
    app = AgriGrokGUI()
    app.run()


if __name__ == "__main__":
    main()