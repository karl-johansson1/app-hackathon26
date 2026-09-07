import io
import random
import re
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from curl_cffi import requests
import threading
import queue
import time

BACKGROUND_COLOR = "#222222"

# === Customize your Albert here ===
ALBERT_IMAGE = "albert.jpeg"
ALBERT_NAME = "Albert"
ALBERT_DESC = "Skyldig Edvin 20kr."

def fetch_candidates(needs_albert=False):
    api_url = "https://api.fbi.gov/wanted/v1/list"
    session = requests.Session(impersonate="chrome")
    
    loaded_options = []
    
    # Loop until we have 3 valid candidates
    while len(loaded_options) < 3:
        page = random.randint(1, 62)
        print(f"Fetching FBI Most Wanted data (Page {page})...")
        
        try:
            response = session.get(api_url, params={"page": page}, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch page {page}: {e}")
            continue
            
        items = response.json().get("items", [])
        random.shuffle(items)
        
        for p in items:
            images = p.get("images", [])
            desc = p.get("caution")

            if not images or not desc or not images[0].get("original"):
                continue

            try:
                # Do a single request to get the image and check headers at the same time
                resp = session.get(images[0]["original"], timeout=4)
                resp.raise_for_status()
                
                content_type = resp.headers.get('Content-Type', '')
                if 'image' not in content_type:
                    continue
                    
                img = Image.open(io.BytesIO(resp.content))
                img.thumbnail((250, 300), Image.Resampling.LANCZOS)
                
                loaded_options.append({
                    "name": p.get("title", "Unknown"),
                    "description": desc,
                    "image_url": images[0]["original"],
                    "image_obj": img
                })
                print(f"Loaded image for: {p.get('title', 'Unknown')}")
                
            except (requests.exceptions.RequestException, OSError) as e:
                print(f"Failed to load image for {p.get('title', 'Unknown')}. Skipping.")
                continue

            # Stop extracting from this page if we hit our target of 3
            if len(loaded_options) == 3:
                break

    # If Albert is needed, load him and replace one of the candidates
    if needs_albert:
        try:
            img = Image.open(ALBERT_IMAGE)
            img.thumbnail((250, 300), Image.Resampling.LANCZOS)
            albert_profile = {
                "name": ALBERT_NAME,
                "description": ALBERT_DESC,
                "image_obj": img,
                "is_albert": True
            }
            # Remove the last loaded FBI profile to make room for Albert
            loaded_options.pop()
            loaded_options.append(albert_profile)
            random.shuffle(loaded_options)
            print("Loaded Albert as a candidate.")
        except Exception as e:
            print(f"Could not load Albert (check filename): {e}")

    if len(loaded_options) < 3:
        raise RuntimeError("Could not load three valid profile images.")

    return loaded_options

class FBIGuessingGame:
    def __init__(self, root, profiles, on_correct_callback):
        self.root = root
        self.root.title("FBI Wanted - Who Did It?")
        self.profiles = profiles
        self.on_correct_callback = on_correct_callback  
        
        # Ensure Albert is always the target if he is in the current round
        albert = next((p for p in profiles if p.get("is_albert")), None)
        if albert:
            self.target = albert
        else:
            self.target = random.choice(profiles)
        
        self.frame_images = tk.Frame(root, bg=BACKGROUND_COLOR)
        self.frame_images.pack(pady=20, padx=20)
        
        self.tk_images = []
        for idx, p in enumerate(self.profiles):
            tk_img = ImageTk.PhotoImage(p["image_obj"])
            self.tk_images.append(tk_img)
            
            btn = tk.Button(
                self.frame_images, 
                image=tk_img, 
                command=lambda i=idx: self.check_guess(i),
                borderwidth=0,
                cursor="hand2"
            )
            btn.grid(row=0, column=idx, padx=15)
            
        # Only apply the FBI text filter if it is NOT Albert
        if self.target.get("is_albert"):
            desc_text = self.target["description"]
        else:
            desc_text = self.target["description"]
            desc_text = re.sub(r"<.*?>", "", desc_text)
            match = re.search(
                r"\b(?:wanted|alleged|charged)\b[^.]*[.]",
                desc_text,
                flags=re.IGNORECASE,
            )
            desc_text = match.group(0) if match else ""
            if desc_text:
                desc_text = desc_text[:1].upper() + desc_text[1:]
            
        lbl_title = tk.Label(root, text="WHICH FUGITIVE IS WANTED FOR:", fg="white", bg=BACKGROUND_COLOR, font=("Arial", 12, "bold"))
        lbl_title.pack(pady=(10, 0))
        
        self.lbl_desc = tk.Label(
            root, 
            text=desc_text, 
            wraplength=700, 
            fg="#f2f0ea", 
            bg=BACKGROUND_COLOR,
            font=("Arial", 16, "italic")
        )
        self.lbl_desc.pack(pady=20, padx=20)
        
    def check_guess(self, idx):
        guessed = self.profiles[idx]
        if guessed["name"] == self.target["name"]:
            messagebox.showinfo("Correct!", f"Spot on!\n\nThat is {self.target['name']}.")
            self.on_correct_callback()
        else:
            messagebox.showerror("Wrong!", f"Incorrect. That was {guessed['name']}.\n\nTry again!")

class GameManager:
    def __init__(self, root):
        self.root = root
        self.albert_queued_or_played = False
        self.profile_queue = queue.Queue(maxsize=10)
        
        # Start the background fetching thread
        self.fetch_thread = threading.Thread(target=self._prefetch_loop, daemon=True)
        self.fetch_thread.start()
        
        self.play_round()

    def _prefetch_loop(self):
        """Runs continuously in the background to keep 2 rounds ready."""
        while True:
            if not self.profile_queue.full():
                include_albert_this_round = False
                
                # Roll for Albert only if he hasn't been queued yet
                if not self.albert_queued_or_played:
                    if random.random() < 0.3:
                        include_albert_this_round = True
                        # Mark him as queued immediately so next iterations don't spawn him again
                        self.albert_queued_or_played = True
                
                try:
                    profiles = fetch_candidates(needs_albert=include_albert_this_round)
                    self.profile_queue.put(profiles)
                except Exception as e:
                    print(f"Background fetch error: {e}")
                    # If we fail, undo the Albert queued flag if it was set this round
                    if include_albert_this_round:
                        self.albert_queued_or_played = False
                    time.sleep(2)
            else:
                # Queue is full, sleep for a moment before checking again
                time.sleep(1)

    def play_round(self):
        # Clear the window
        for widget in self.root.winfo_children():
            widget.destroy()
            
        if self.profile_queue.empty():
            # If the background thread hasn't finished yet, show a loading screen
            self.lbl_loading = tk.Label(self.root, text="Loading next round...", fg="white", bg=BACKGROUND_COLOR, font=("Arial", 16))
            self.lbl_loading.pack(expand=True)
            self._wait_for_queue()
        else:
            self._start_game_from_queue()

    def _wait_for_queue(self):
        """Polls the queue every 500ms without freezing the UI."""
        if not self.profile_queue.empty():
            self._start_game_from_queue()
        else:
            self.root.after(500, self._wait_for_queue)

    def _start_game_from_queue(self):
        """Pulls the next set of profiles from the queue and starts the game."""
        for widget in self.root.winfo_children():
            widget.destroy()
            
        profiles = self.profile_queue.get()
        self.game = FBIGuessingGame(self.root, profiles, self.play_round)

def main():
    root = tk.Tk()
    root.geometry("800x600")
    root.configure(bg=BACKGROUND_COLOR)
    manager = GameManager(root)
    root.eval('tk::PlaceWindow . center')
    root.mainloop()

if __name__ == "__main__":
    main()