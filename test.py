import io
import random
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from curl_cffi import requests

def fetch_candidates():
    api_url = "https://api.fbi.gov/wanted/v1/list"
    session = requests.Session(impersonate="chrome")
    
    # Pick a random page so you get different fugitives each time you play
    valid_profiles = []
    while len(valid_profiles) < 3:
        page = random.randint(1, 62)
        print(f"Fetching FBI Most Wanted data (Page {page})...")
        
        response = session.get(api_url, params={"page": page})
        response.raise_for_status()
        items = response.json().get("items", [])
        
        for p in items:
            images = p.get("images", [])
            desc = p.get("caution")

            # We only want people with both an image and a crime description.
            if not images or not desc or not images[0].get("original"):
                continue

            try:
                resp = session.get(images[0]["original"], timeout=10)
                resp.raise_for_status()
                if "image" not in resp.headers.get("Content-Type", ""):
                    continue

                valid_profiles.append({
                    "name": p.get("title", "Unknown"),
                    "description": desc,
                    "image_url": images[0]["original"]
                })
            except requests.exceptions.RequestException:
                print("Failed to fetch image. Skipping this profile.")
                continue
    # Shuffle the profiles so we can try them one by one
    random.shuffle(valid_profiles)
    
    print("Downloading images...")

    loaded_options = []

    for c in valid_profiles:
        try:
            resp = session.get(c["image_url"], timeout=1)
            resp.raise_for_status()
            
            # Verify the response is actually an image, not an HTML block page
            content_type = resp.headers.get('Content-Type', '')
            if 'image' not in content_type:
                print(f"Skipping {c['name']} (Received {content_type} instead of image).")
                continue
                
            img = Image.open(io.BytesIO(resp.content))
            
            # Resize images so they display uniformly next to each other
            img.thumbnail((250, 300), Image.Resampling.LANCZOS)
            c["image_obj"] = img
            loaded_options.append(c)
            print(f"Loaded image for: {c['name']}")
            
        except (requests.exceptions.RequestException, OSError) as e:
            print(f"Failed to load image for {c['name']}: {e}")

        if len(loaded_options) == 3:
            break

    if len(loaded_options) < 3:
        raise RuntimeError("Could not load three valid profile images.")

    return loaded_options

class FBIGuessingGame:
    def __init__(self, root, profiles):
        self.root = root
        self.root.title("FBI Wanted - Who Did It?")
        self.root.configure(bg="#222222")
        self.profiles = profiles
        
        # Pick one of the 3 to be the answer
        self.target = random.choice(profiles)
        
        # Layout: Frame for images
        self.frame_images = tk.Frame(root, bg="#222222")
        self.frame_images.pack(pady=20, padx=20)
        
        self.tk_images = []
        for idx, p in enumerate(self.profiles):
            # Convert PIL image to Tkinter format
            tk_img = ImageTk.PhotoImage(p["image_obj"])
            self.tk_images.append(tk_img)
            
            # Make the image a clickable button
            btn = tk.Button(
                self.frame_images, 
                image=tk_img, 
                command=lambda i=idx: self.check_guess(i),
                borderwidth=0,
                cursor="hand2"
            )
            btn.grid(row=0, column=idx, padx=15)
            
        # Layout: Text description below
        desc_text = self.target["description"]
        lbl_title = tk.Label(root, text="WHICH FUGITIVE IS WANTED FOR:", fg="white", bg="#222222", font=("Arial", 12, "bold"))
        lbl_title.pack(pady=(10, 0))
        
        self.lbl_desc = tk.Label(
            root, 
            text=desc_text, 
            wraplength=700, 
            fg="#ffcc00", 
            bg="#222222", 
            font=("Arial", 16, "italic")
        )
        self.lbl_desc.pack(pady=20, padx=20)
        
    def check_guess(self, idx):
        guessed = self.profiles[idx]
        if guessed["name"] == self.target["name"]:
            messagebox.showinfo("Correct!", f"Spot on!\n\nThat is {self.target['name']}.")
            self.root.destroy()
        else:
            messagebox.showerror("Wrong!", f"Incorrect. That was {guessed['name']}.\n\nTry again!")

def main():
    try:
        profiles = fetch_candidates()
    except Exception as e:
        print(f"Error initializing game: {e}")
        return
        
    # Start the UI
    root = tk.Tk()
    app = FBIGuessingGame(root, profiles)
    
    # Center the window on the screen
    root.eval('tk::PlaceWindow . center')
    root.mainloop()

if __name__ == "__main__":
    main()