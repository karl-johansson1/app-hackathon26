import io
import random
import re
import os
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from curl_cffi import requests

def strip_html(text):
    """Removes HTML tags from the FBI API descriptions."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).replace('&nbsp;', ' ').strip()

def load_custom_suspect():
    """Loads your custom profile into the game."""
    image_path = "albert.jpeg"  # Change this to your actual image file name!
    
    if not os.path.exists(image_path):
        print("Custom image not found. The game will play without the custom suspect.")
        return None
        
    try:
        img = Image.open(image_path)
        img.thumbnail((250, 300), Image.Resampling.LANCZOS)
        return {
            "name": "Albert",
            "description": "Skyldig Edvin 20 kr.",
            "image_obj": img
        }
    except Exception as e:
        print(f"Failed to load custom suspect image: {e}")
        return None

game_med_albert = False  # har vi haft ett game med albert?
def fetch_candidates(custom_suspect=None):
    global game_med_albert
    api_url = "https://api.fbi.gov/wanted/v1/list"
    session = requests.Session(impersonate="chrome")
    
    page = random.randint(1, 40) 
    print(f"Fetching FBI Most Wanted data (Page {page})...")
    
    response = session.get(api_url, params={"page": page})
    response.raise_for_status()
    items = response.json().get("items", [])
    
    random.shuffle(items)
    
    valid_profiles = []
    
    # If we have a custom suspect, give them a 35% chance to appear in this round
    if custom_suspect and random.random() < 0.5 and not game_med_albert:
        game_med_albert = True
        valid_profiles.append(custom_suspect)
        print("Injected custom suspect into this round!")

    print("Downloading images and processing profiles...")

    for p in items:
        if len(valid_profiles) == 3:
            break

        images = p.get("images", [])
        desc = p.get("caution")

        if not images or not desc or not images[0].get("original"):
            continue

        image_url = images[0]["original"]

        try:
            resp = session.get(image_url, timeout=5)
            resp.raise_for_status()
            
            content_type = resp.headers.get('Content-Type', '')
            if 'image' not in content_type:
                continue
                
            img = Image.open(io.BytesIO(resp.content))
            img.thumbnail((250, 300), Image.Resampling.LANCZOS)
            
            valid_profiles.append({
                "name": p.get("title", "Unknown"),
                "description": strip_html(desc),
                "image_obj": img
            })
            print(f"Loaded: {p.get('title')}")
            
        except Exception as e:
            print(f"Failed to load image for {p.get('title')}: {e}")

    if len(valid_profiles) < 3:
        raise RuntimeError("Could not load three valid profile images. Try running again.")

    random.shuffle(valid_profiles)
    return valid_profiles

class FBIGuessingGame:
    def __init__(self, root, custom_suspect):
        self.root = root
        self.custom_suspect = custom_suspect
        self.root.title("FBI Wanted - Who Did It?")
        self.root.configure(bg="#222222")
        
        # Setup the UI containers once
        self.lbl_title = tk.Label(root, text="WHICH FUGITIVE IS WANTED FOR:", fg="white", bg="#222222", font=("Arial", 12, "bold"))
        self.lbl_title.pack(pady=(10, 0))
        
        self.lbl_desc = tk.Label(
            root, 
            text="Loading first round...", 
            wraplength=700, 
            fg="#f2f0ea", 
            bg=BACKGROUND_COLOR,
            font=("Arial", 16, "italic")
        )
        self.lbl_desc.pack(pady=20, padx=20)

        self.frame_images = tk.Frame(root, bg="#222222")
        self.frame_images.pack(pady=20, padx=20)
        
        # Create placeholders for the 3 buttons
        self.buttons = []
        self.tk_images = []
        for i in range(3):
            btn = tk.Button(
                self.frame_images, 
                borderwidth=0,
                cursor="hand2",
                highlightthickness=0,
                bg="#222222"
            )
            btn.grid(row=0, column=i, padx=15)
            self.buttons.append(btn)
            
        # Start the first round
        self.start_new_round()
        
    def start_new_round(self):
        """Fetches new suspects and updates the UI."""
        # Hide old images and show loading text
        for btn in self.buttons:
            btn.config(image='')
        self.lbl_desc.config(text="Fetching new suspects from the FBI database...")
        self.root.update() # Force the UI to refresh before the download starts
        
        try:
            self.profiles = fetch_candidates(self.custom_suspect)
        except Exception as e:
            self.lbl_desc.config(text=f"Error fetching suspects: {e}")
            return
            
        self.target = random.choice(self.profiles)
        self.lbl_desc.config(text=self.target["description"])
        
        self.tk_images = [] # Clear old images from memory
        for idx, p in enumerate(self.profiles):
            tk_img = ImageTk.PhotoImage(p["image_obj"])
            self.tk_images.append(tk_img)
            
            # Update the existing buttons with new images and commands
            self.buttons[idx].config(
                image=tk_img, 
                command=lambda i=idx: self.check_guess(i)
            )
        
    def check_guess(self, idx):
        guessed = self.profiles[idx]
        if guessed["name"] == self.target["name"]:
            messagebox.showinfo("Correct!", f"Spot on!\n\nThat is {self.target['name']}.")
            self.start_new_round() # Load the next level instead of quitting
        else:
            messagebox.showerror("Wrong!", f"Incorrect. That was {guessed['name']}.\n\nTry again!")

def main():
    custom_suspect = load_custom_suspect()
    
    root = tk.Tk()
    app = FBIGuessingGame(root, custom_suspect)
    root.eval('tk::PlaceWindow . center')
    root.mainloop()

if __name__ == "__main__":
    main()