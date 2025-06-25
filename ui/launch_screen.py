# ui/launch_screen.py
import tkinter as tk
from tkinter import ttk
import os
from PIL import Image, ImageTk # Ensure Pillow is imported
import logging

logger = logging.getLogger(__name__)

class LaunchScreen(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.overrideredirect(True)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Launch screen width is 50% of screen width
        self.window_width = screen_width // 2
        self.window_height = 500 # You can adjust this height

        x = (screen_width // 2) - (self.window_width // 2)
        y = (screen_height // 2) - (self.window_height // 2)
        self.geometry(f'{self.window_width}x{self.window_height}+{x}+{y}')

        self.bg_color = "white" # Default fallback
        try:
            s = ttk.Style(self)
            if 'clam' in s.theme_names(): s.theme_use('clam')
            elif 'alt' in s.theme_names(): s.theme_use('alt')
            self.bg_color = s.lookup('TFrame', 'background')
        except tk.TclError:
            logger.warning("LaunchScreen: Could not lookup TFrame background, using default.")
        self.configure(background=self.bg_color)

        # Main frame with padding
        main_frame_padding = 20
        main_frame = ttk.Frame(self, padding=(main_frame_padding, main_frame_padding, main_frame_padding, main_frame_padding))
        main_frame.pack(expand=True, fill=tk.BOTH)

        app_name_label = ttk.Label(main_frame, text="Transcription dev test", font=("Helvetica", 24, "bold"))
        app_name_label.pack(pady=(10, 5)) # Adjusted padding

        self.loading_label_text = tk.StringVar(value="Loading application, please wait...")
        loading_label = ttk.Label(main_frame, textvariable=self.loading_label_text, font=("Helvetica", 14))
        loading_label.pack(pady=5)

        self.gif_label = ttk.Label(main_frame)
        self.gif_label.pack(pady=10) # Adjusted padding
        
        self.frames = []
        self.current_frame_idx = 0
        self.gif_delay = 100
        self.after_id = None

        # Define max dimensions for the GIF based on window size and padding
        # Max width: window width - (2 * frame_padding) - some_extra_margin_for_gif
        self.max_gif_width = self.window_width - (2 * main_frame_padding) - 200 
        # Max height: Consider available space after labels and padding
        # Approx: window_height - (2*frame_padding) - app_name_pady - loading_label_pady - gif_label_pady_top - gif_label_pady_bottom
        approx_label_space = (10+5) + 5 + (10) # Approximate Y padding for labels
        self.max_gif_height = self.window_height - (2*main_frame_padding) - approx_label_space - 200 # Extra bottom margin for GIF

        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            gif_name = "loading-7528.gif" # Your GIF name
            gif_path = os.path.join(current_dir, gif_name)
            self.load_gif(gif_path)
        except NameError:
            gif_path = os.path.join("ui", "loading-7528.gif")
            self.load_gif(gif_path)
        
        self.lift()
        self.attributes('-topmost', True)
        self.update_idletasks()

    def load_gif(self, gif_path):
        logger.info(f"LaunchScreen: Attempting to load GIF from: {gif_path}")
        try:
            gif_image_pil = Image.open(gif_path)
            logger.info(f"LaunchScreen: GIF opened. Is animated: {getattr(gif_image_pil, 'is_animated', False)}, N_frames: {getattr(gif_image_pil, 'n_frames', 1)}")
            
            idx = 0
            self.frames = [] 
            while True:
                try:
                    gif_image_pil.seek(idx)
                    current_pil_frame = gif_image_pil.copy()

                    # --- RESIZING LOGIC ---
                    original_width, original_height = current_pil_frame.size
                    
                    # Calculate new dimensions maintaining aspect ratio
                    # Use self.max_gif_width and self.max_gif_height defined in __init__
                    ratio = 1.0
                    if original_width > self.max_gif_width or original_height > self.max_gif_height:
                        ratio = min(self.max_gif_width / original_width, self.max_gif_height / original_height)
                    
                    if ratio < 1.0: # Only resize if it's larger than max dimensions
                        new_width = int(original_width * ratio)
                        new_height = int(original_height * ratio)
                        logger.info(f"Resizing frame {idx} from {original_width}x{original_height} to {new_width}x{new_height}")
                        resized_pil_frame = current_pil_frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    else:
                        resized_pil_frame = current_pil_frame # No resize needed
                    # --- END RESIZING LOGIC ---

                    self.frames.append(ImageTk.PhotoImage(resized_pil_frame))
                    idx += 1
                except EOFError:
                    logger.info(f"LaunchScreen: Reached EOF after {idx} frames.")
                    break 
                except Exception as frame_e:
                    logger.error(f"LaunchScreen: Error processing frame {idx}: {frame_e}", exc_info=True)
                    break
            
            if self.frames:
                logger.info(f"LaunchScreen: Loaded {len(self.frames)} frames for GIF.")
                self.gif_delay = gif_image_pil.info.get('duration', 100)
                if self.gif_delay == 0: self.gif_delay = 100 
                logger.info(f"LaunchScreen: GIF delay set to {self.gif_delay} ms.")
                self.animate_gif()
            else:
                logger.warning("LaunchScreen: No frames loaded for GIF.")
                self.loading_label_text.set("Loading... (GIF error or no frames)")
                self.gif_label.configure(text="[GIF Error - No Frames]")

        except ImportError: # Should not happen if Pillow is installed
            logger.error("LaunchScreen: Pillow library (PIL) not found.", exc_info=True)
            self.loading_label_text.set("Loading... (Pillow library needed for GIF)")
            self.gif_label.configure(text="[Pillow Missing]")
        except FileNotFoundError:
            logger.error(f"LaunchScreen: GIF file not found at: {gif_path}", exc_info=True)
            self.loading_label_text.set(f"Loading... (GIF not found)")
            self.gif_label.configure(text="[GIF Not Found]")
        except Exception as e:
            logger.error(f"LaunchScreen: General error loading GIF: {e}", exc_info=True)
            self.loading_label_text.set(f"Loading... (GIF load error)")
            self.gif_label.configure(text=f"[GIF Load Error]")

    def animate_gif(self):
        if not self.frames or not self.winfo_exists():
            logger.warning("LaunchScreen: animate_gif - No frames or window destroyed. Stopping animation.")
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
            return
        
        logger.info(f"LaunchScreen: Animating GIF frame {self.current_frame_idx + 1}/{len(self.frames)}") 

        frame_image = self.frames[self.current_frame_idx]
        self.gif_label.configure(image=frame_image)
        self.gif_label.image = frame_image # Keep explicit reference

        self.current_frame_idx += 1
        if self.current_frame_idx >= len(self.frames):
            self.current_frame_idx = 0 
            
        if self.winfo_exists():
            self.after_id = self.after(self.gif_delay, self.animate_gif)
        else:
            logger.warning("LaunchScreen: animate_gif - Window destroyed during animation loop.")

    def close(self):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.destroy()