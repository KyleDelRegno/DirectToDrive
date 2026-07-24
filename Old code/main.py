import os
import threading
import customtkinter as ctk
from tkinter import filedialog
import gdown

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class DriveDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Drive to SSD")
        self.geometry("720x420")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self, corner_radius=16)
        container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)

        ### Title Label
        self.title_label = ctk.CTkLabel(
            container,
            text="Google Drive Downloader",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")


        ### Drive URL Location
        self.url_entry = ctk.CTkEntry(
            container,
            placeholder_text="Paste Google Drive file or folder URL"
        )
        self.url_entry.grid(row=1, column=0, padx=20, pady=10, sticky="ew")


        ### Download Location URL
        self.path_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.path_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.path_frame.grid_columnconfigure(0, weight=1)

        self.path_entry = ctk.CTkEntry(
            self.path_frame,
            placeholder_text="External SSD path, e.g. E:\\Backup or /Volumes/SSD/Backup"
        )
        self.path_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.browse_button = ctk.CTkButton(
            self.path_frame,
            text="Browse",
            width=100,
            command=self.browse_folder
        )
        self.browse_button.grid(row=0, column=1, sticky="e")



        ### Download Button
        self.download_button = ctk.CTkButton(
            container,
            text="Download",
            command=self.start_download
        )
        self.download_button.grid(row=3, column=0, padx=20, pady=12, sticky="ew")

        self.status_label = ctk.CTkLabel(
            container,
            text="Ready",
            anchor="w"
        )
        self.status_label.grid(row=4, column=0, padx=20, pady=(6, 10), sticky="ew")

        self.log_box = ctk.CTkTextbox(container, height=180)
        self.log_box.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="nsew")
        container.grid_rowconfigure(5, weight=1)

    def log(self, message):
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    def start_download(self):
        thread = threading.Thread(target=self.download_task, daemon=True)
        thread.start()

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

    def download_task(self):
        url = self.url_entry.get().strip()
        output_path = self.path_entry.get().strip()

        if not url or not output_path:
            self.status_label.configure(text="Please enter both URL and SSD path.")
            return

        try:
            os.makedirs(output_path, exist_ok=True)
            self.status_label.configure(text="Downloading...")
            self.log(f"Starting download to: {output_path}")

            if "folders" in url:
                gdown.download_folder(url, output=output_path)
            else:
                gdown.download(url, output=output_path, fuzzy=True)

            self.status_label.configure(text="Download complete.")
            self.log("Finished successfully.")
        except Exception as e:
            self.status_label.configure(text="Download failed.")
            self.log(f"Error: {e}")


if __name__ == "__main__":
    app = DriveDownloaderApp()
    app.mainloop()