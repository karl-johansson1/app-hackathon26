import io
import random
import re
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageEnhance, ImageTk
from curl_cffi import requests
import threading
import queue
import time

BACKGROUND_COLOR = "#222222"

# === Customize your Albert here ===
ALBERT_IMAGE = "albert.jpeg"
ALBERT_NAME = "Albert"
ALBERT_DESC = "Skyldig Edvin 20kr."
TITLE_IMAGE = "Designer.png" # Add your cool title PNG here

def fetch_candidates(needs_albert=False):
    api_url = "https://api.fbi.gov/wanted/v1/list"
    session = requests.Session(impersonate="chrome")
    
    loaded_options = []
    
    # 2. Loop until we have 3 valid candidates total
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
            # Skip if it is Juan Jose, to prevent duplicates
            if "Juan Jose" in p.get("title", ""):
                continue

            images = p.get("images", [])
            desc = p.get("caution")

            if not images or not desc or not images[0].get("original"):
                continue

            try:
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

            if len(loaded_options) == 3:
                break

    # 3. If Albert is needed, load him and replace the last candidate
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

    # Final shuffle so Juan Jose is not always the first image displayed
    random.shuffle(loaded_options)

    if len(loaded_options) < 3:
        raise RuntimeError("Could not load three valid profile images.")

    return loaded_options

class FBIGuessingGame:
    def __init__(self, root, profiles, on_correct_callback):
        self.root = root
        self.root.title("FBI Wanted - Who Did It?")
        self.profiles = profiles
        self.on_correct_callback = on_correct_callback
        self.guess_made = False
        self.option_buttons = []
        self.dimmed_images = []        
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

            dimmed_img = ImageEnhance.Brightness(p["image_obj"]).enhance(0.45)
            dimmed_photo = ImageTk.PhotoImage(dimmed_img)
            self.dimmed_images.append(dimmed_photo)

            container = tk.Frame(self.frame_images, bg=BACKGROUND_COLOR)
            container.grid(row=0, column=idx, padx=15)
            
            btn = tk.Button(
                container,
                image=tk_img,
                command=lambda i=idx: self.check_guess(i),
                borderwidth=0,
                cursor="hand2",
                relief="flat",
                bg=BACKGROUND_COLOR,
                activebackground=BACKGROUND_COLOR,
                highlightthickness=0,
                compound="top",
            )
            btn.pack()

            self.option_buttons.append(btn)
            
        # Only apply the FBI text filter if it is NOT Albert
        if self.target.get("is_albert"):
            desc_text = self.target["description"]
        else:
            desc_text = self.target["description"]
            desc_text = re.sub(r"<.*?>", "", desc_text)
            match = re.search(
                r"\b(?:wanted|alleged|allegedly|charged|arrest|warrant|confined)\b[^.]*[.]",
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

    def _handle_correct_guess(self):
        messagebox.showinfo("Correct!", f"Spot on!\n\nThat is {self.target['name']}.")
        self.on_correct_callback()

    def check_guess(self, idx):
        if self.option_buttons[idx]["state"] == "disabled":
            return

        guessed = self.profiles[idx]
        self.option_buttons[idx].configure(state="disabled")

        if guessed["name"] == self.target["name"]:
            self.option_buttons[idx].configure(image=self.tk_images[idx])
            self._handle_correct_guess()
        else:
            self.option_buttons[idx].configure(image=self.dimmed_images[idx])

class GameManager:
    def __init__(self, root):
        self.root = root
        self.albert_queued_or_played = False
        self.rounds_queued_count = 0
        self.profile_queue = queue.Queue(maxsize=10)
        
        # Start the background fetching thread
        self.fetch_thread = threading.Thread(target=self._prefetch_loop, daemon=True)
        self.fetch_thread.start()
        
        self.play_round()

    def _prefetch_loop(self):
        """Runs continuously in the background to keep rounds ready."""
        while True:
            if not self.profile_queue.full():
                include_albert_this_round = False
                upcoming_round = self.rounds_queued_count + 1
                
                # Only roll for Albert starting on Round 3 or later
                if upcoming_round >= 3 and not self.albert_queued_or_played:
                    if random.random() < 0.6:
                        include_albert_this_round = True
                        # Mark him as queued immediately so subsequent rounds don't duplicate him
                        self.albert_queued_or_played = True
                
                try:
                    profiles = fetch_candidates(needs_albert=include_albert_this_round)
                    self.profile_queue.put(profiles)
                    self.rounds_queued_count += 1
                except Exception as e:
                    print(f"Background fetch error: {e}")
                    # If fetching failed, reset the flag so he can be rolled again later
                    if include_albert_this_round:
                        self.albert_queued_or_played = False
                    time.sleep(2)
            else:
                time.sleep(1)

    def play_round(self):
        for widget in self.root.winfo_children():
            widget.destroy()
            
        if self.profile_queue.empty():
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
        
def show_main_menu(root):
    # Clear the window
    for widget in root.winfo_children():
        widget.destroy()
        
    root.unbind("<Configure>")
    
    # ==========================================
    # CONFIGURE YOUR IMAGE SIZE HERE (in pixels)
    # Increase these numbers to make it bigger!
    # ==========================================
    TITLE_WIDTH = 1200  # Max width on your 1400px screen
    TITLE_HEIGHT = 800   # Max height on your 1000px screen
    # ==========================================

    try:
        orig = Image.open(TITLE_IMAGE)
        orig_w, orig_h = orig.size
        
        # Calculate aspect ratio scale factor (allows upsizing!)
        scale = min(TITLE_WIDTH / orig_w, TITLE_HEIGHT / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        # Force Pillow to resize to the large dimensions
        resized = orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        tk_title_img = ImageTk.PhotoImage(resized)
        lbl_img = tk.Label(root, image=tk_title_img, bg=BACKGROUND_COLOR)
        lbl_img.image = tk_title_img
        lbl_img.pack(pady=(40, 20))
        
    except Exception as e:
        print(f"Error loading title image: {e}")
        lbl_img = tk.Label(
            root, 
            text="[FBI WANTED: WHO DID IT?]", 
            font=("Arial", 32, "bold"), 
            fg="red", 
            bg=BACKGROUND_COLOR
        )
        lbl_img.pack(pady=(120, 50))

    # Start Button
    btn_start = tk.Button(
        root,
        text="START GAME",
        font=("Arial", 22, "bold"),
        bg="#444444",
        fg="red",
        activebackground="#E9E933",
        activeforeground="black",
        padx=40,
        pady=15,
        cursor="hand2",
        borderwidth=0,
        command=lambda: GameManager(root)
    )
    btn_start.pack(pady=20)
    
def main():
    root = tk.Tk()
    root.title("FBI Wanted - Who Did It?")
    root.geometry("1400x1000")
    root.configure(bg=BACKGROUND_COLOR)
    
    # Show the main menu first
    show_main_menu(root)
    
    root.eval('tk::PlaceWindow . center')
    root.mainloop()

if __name__ == "__main__":
    main()