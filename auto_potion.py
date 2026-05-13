import time
import random
import pydirectinput
from check_hp import check_hp

# Configuration
POTION_KEY = 'f1'
HP_THRESHOLD = 20.0  # 20%
COOLDOWN = 1.0       # 1 second
CHECK_INTERVAL = 0.2  # 0.2 seconds between HP checks

def run_auto_potion():
    print("--- Auto Potion Script Started ---")
    print(f"Target Key: {POTION_KEY}")
    print(f"Threshold: {HP_THRESHOLD}%")
    print(f"Cooldown: {COOLDOWN}s")
    print("Press Ctrl+C to stop.")
    
    last_potion_time = 0
    
    try:
        while True:
            # 1. Check current HP
            current_hp = check_hp(debug=False)
            
            if current_hp is None:
                # Window not found or error
                time.sleep(1.0)
                continue
                
            print(f"\rCurrent HP: {current_hp:.1f}%", end="", flush=True)
            
            # 2. Check if HP is below threshold
            if current_hp <= HP_THRESHOLD:
                current_time = time.time()
                
                # 3. Check cooldown
                if current_time - last_potion_time >= COOLDOWN:
                    print(f"\n[ALERT] HP Low ({current_hp:.1f}%)! Pressing {POTION_KEY}...")
                    
                    # Simulation with random duration for stealth
                    press_duration = random.uniform(0.05, 0.15)
                    pydirectinput.press(POTION_KEY, duration=press_duration)
                    
                    last_potion_time = current_time
                else:
                    # Waiting for cooldown
                    pass
            
            # 4. Wait for next check with random jitter
            jitter = random.uniform(-0.05, 0.05)
            time.sleep(max(0.01, CHECK_INTERVAL + jitter))
            
    except KeyboardInterrupt:
        print("\n--- Auto Potion Script Stopped ---")

if __name__ == "__main__":
    # Initial delay to let the user switch to the game window
    print("Starting in 3 seconds... Switch to Lineage Classic window!")
    time.sleep(3)
    run_auto_potion()
