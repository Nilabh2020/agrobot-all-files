#include <SPI.h>
#include <Adafruit_GFX.h>
#include <MCUFRIEND_kbv.h>
#include <TouchScreen.h>

MCUFRIEND_kbv tft;

// YOUR EXACT CALIBRATION VALUES
int XP = 8, XM = A2, YP = A3, YM = 9;
TouchScreen ts(XP, YP, XM, YM, 300);

// YOUR EXACT TOUCH MAPPING VALUES
int TS_LEFT = 192;
int TS_RT = 874;
int TS_TOP = 939;
int TS_BOT = 103;

// Colors
#define BLACK 0x0000
#define WHITE 0xFFFF
#define RED 0xF800
#define GREEN 0x07E0
#define BLUE 0x001F
#define YELLOW 0xFFE0
#define CYAN 0x07FF
#define ORANGE 0xFD20
#define DARKGREEN 0x03E0

// Button positions for 320x480 portrait
int buttonY[] = {80, 130, 180, 230, 280, 330, 380, 430};
String buttonNames[] = {"Seasonal Crops", "Pest Control", "Irrigation", "Weather Plan", "Harvest Time", "Equipment", "Fertilizers", "Crop Health"};
String buttonCmds[] = {"SEASONAL_CROPS", "PEST_CONTROL", "IRRIGATION", "WEATHER", "HARVEST", "EQUIPMENT", "FERTILIZER", "CROP_HEALTH"};

bool connected = false;
unsigned long lastTouch = 0;

void setup() {
  Serial.begin(9600);
  
  uint16_t ID = tft.readID();
  if (ID == 0xD3D3) ID = 0x9486;
  tft.begin(ID);
  tft.setRotation(0); // Portrait mode like your calibration
  
  drawScreen();
  
  Serial.println("ARDUINO_READY");
  Serial.println("SHIELD_MOUNTED");
  Serial.println("CALIBRATION_LOADED");
}

void loop() {
  checkTouch();
  checkSerial();
  delay(30);
}

void drawScreen() {
  tft.fillScreen(BLACK);
  
  // Header
  tft.fillRect(0, 0, 320, 60, DARKGREEN);
  tft.setTextColor(WHITE);
  tft.setTextSize(3);
  tft.setCursor(50, 15);
  tft.print("AgriGrok");
  
  tft.setTextSize(1);
  tft.setCursor(90, 40);
  tft.print("Smart Farming Assistant");
  
  // Draw 8 buttons
  uint16_t colors[] = {DARKGREEN, ORANGE, BLUE, CYAN, GREEN, 0xF81F, YELLOW, RED};
  
  for (int i = 0; i < 8; i++) {
    tft.fillRect(10, buttonY[i], 300, 40, colors[i]);
    tft.drawRect(10, buttonY[i], 300, 40, WHITE);
    
    tft.setTextColor(WHITE);
    tft.setTextSize(2);
    tft.setCursor(15, buttonY[i] + 12);
    tft.print(buttonNames[i]);
  }
  
  // Status bar at bottom
  tft.fillRect(0, 450, 320, 30, BLACK);
  tft.drawRect(0, 450, 320, 30, WHITE);
  updateStatus();
}

void updateStatus() {
  tft.setTextColor(connected ? GREEN : RED);
  tft.setTextSize(1);
  tft.setCursor(10, 460);
  tft.print(connected ? "Python Connected - Ready!" : "Waiting for Python...");
  
  // Connection indicator
  tft.fillCircle(300, 465, 8, connected ? GREEN : RED);
}

void checkTouch() {
  TSPoint p = ts.getPoint();
  pinMode(YP, OUTPUT);
  pinMode(XM, OUTPUT);
  
  if (p.z > 200 && p.z < 1000) {
    
    // Debounce
    if (millis() - lastTouch < 300) return;
    lastTouch = millis();
    
    // Use YOUR EXACT calibration values
    int x = map(p.x, TS_LEFT, TS_RT, 0, 320);  // 192 to 874 -> 0 to 320
    int y = map(p.y, TS_TOP, TS_BOT, 0, 480);  // 939 to 103 -> 0 to 480
    
    // Constrain to screen
    x = constrain(x, 0, 319);
    y = constrain(y, 0, 479);
    
    Serial.print("Raw: (");
    Serial.print(p.x);
    Serial.print(",");
    Serial.print(p.y);
    Serial.print(") -> Mapped: (");
    Serial.print(x);
    Serial.print(",");
    Serial.print(y);
    Serial.println(")");
    
    // Check which button was pressed
    for (int i = 0; i < 8; i++) {
      if (x >= 10 && x <= 310 && y >= buttonY[i] && y <= buttonY[i] + 40) {
        
        Serial.print("BUTTON HIT: ");
        Serial.println(buttonNames[i]);
        
        // Send command to Python
        Serial.print("BUTTON_PRESSED:");
        Serial.println(buttonCmds[i]);
        
        // Visual feedback
        flashButton(i);
        break;
      }
    }
  }
}

void flashButton(int buttonIndex) {
  // Flash the pressed button
  tft.fillRect(10, buttonY[buttonIndex], 300, 40, WHITE);
  tft.setTextColor(BLACK);
  tft.setTextSize(2);
  tft.setCursor(15, buttonY[buttonIndex] + 12);
  tft.print(buttonNames[buttonIndex]);
  
  delay(200);
  
  // Restore original color
  uint16_t colors[] = {DARKGREEN, ORANGE, BLUE, CYAN, GREEN, 0xF81F, YELLOW, RED};
  tft.fillRect(10, buttonY[buttonIndex], 300, 40, colors[buttonIndex]);
  tft.drawRect(10, buttonY[buttonIndex], 300, 40, WHITE);
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  tft.setCursor(15, buttonY[buttonIndex] + 12);
  tft.print(buttonNames[buttonIndex]);
  
  // Show confirmation
  showConfirmation(buttonNames[buttonIndex]);
}

void showConfirmation(String buttonName) {
  // Show "SENT!" popup
  tft.fillRect(110, 240, 100, 30, BLUE);
  tft.drawRect(110, 240, 100, 30, WHITE);
  
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  tft.setCursor(130, 248);
  tft.print("SENT!");
  
  delay(1000);
  
  // Clear popup
  tft.fillRect(110, 240, 100, 30, BLACK);
}

void checkSerial() {
  if (Serial.available()) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    
    if (msg == "PYTHON_CONNECTED") {
      connected = true;
      updateStatus();
      
    } else if (msg.startsWith("STATUS:")) {
      // Could display status updates here
      
    } else if (msg.startsWith("RESPONSE:")) {
      String response = msg.substring(9);
      showResponse(response);
      
    } else if (msg == "PING") {
      Serial.println("PONG");
    }
  }
}

void showResponse(String response) {
  // Simple response display
  tft.fillScreen(BLACK);
  
  // Header
  tft.fillRect(0, 0, 320, 40, BLUE);
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  tft.setCursor(20, 12);
  tft.print("AI Response");
  
  // Close button
  tft.fillRect(270, 5, 45, 30, RED);
  tft.drawRect(270, 5, 45, 30, WHITE);
  tft.setTextColor(WHITE);
  tft.setTextSize(2);
  tft.setCursor(285, 13);
  tft.print("X");
  
  // Response text
  tft.setTextColor(GREEN);
  tft.setTextSize(1);
  displayText(response, 10, 60);
  
  // Wait for close or timeout
  unsigned long startTime = millis();
  while (millis() - startTime < 15000) {
    TSPoint p = ts.getPoint();
    pinMode(YP, OUTPUT);
    pinMode(XM, OUTPUT);
    
    if (p.z > 200) {
      int x = map(p.x, TS_LEFT, TS_RT, 0, 320);
      int y = map(p.y, TS_TOP, TS_BOT, 0, 480);
      
      // Check close button
      if (x >= 270 && x <= 315 && y >= 5 && y <= 35) {
        break;
      }
      delay(200);
    }
    delay(100);
  }
  
  drawScreen(); // Redraw main screen
}

void displayText(String text, int startX, int startY) {
  int x = startX;
  int y = startY;
  int maxChars = 50;
  
  for (int i = 0; i < text.length() && y < 430; i++) {
    char c = text.charAt(i);
    
    if (c == '\n' || (i % maxChars == 0 && i > 0)) {
      x = startX;
      y += 12;
    }
    
    if (c != '\n') {
      tft.setCursor(x, y);
      tft.print(c);
      x += 6;
    }
  }
}
