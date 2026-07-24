import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from Auth import get_credentials
from DriveClient import (
    get_drive_service,
    list_folder,
    download_file,
    download_folder_recursive,
    FOLDER_MIME,
)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")



### Drive Row Item ###
class DriveItemRow(ctk.CTkFrame):
    def __init__(self, master, item, folder_mime, open_folder_callback):
        super().__init__(master, corner_radius=10, fg_color=("gray92", "gray14"))
        self.item = item
        self.default_color = ("gray92", "gray14")
        self.hover_color = ("gray84", "gray22")

        self.grid_columnconfigure(0, weight=1)

        prefix = "[Folder]" if item["mimeType"] == folder_mime else "[File]"
        label = f"{prefix} {item['name']}"

        self.checkbox = ctk.CTkCheckBox(self, text=label)
        self.checkbox.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        self.open_button = None
        if item["mimeType"] == folder_mime:
            self.open_button = ctk.CTkButton(
                self,
                text="Open",
                width=70,
                command=lambda folder=item:open_folder_callback(folder)
            )
            self.open_button.grid(row=0, column=1, padx=(10, 12), pady=8)

        self.bind_hover_recursive(self)

    def set_hover(self, hovering):
        self.configure(fg_color=self.hover_color if hovering else self.default_color)

    def bind_hover_recursive(self, widget):
        widget.bind("<Enter>", lambda e: self.set_hover(True))
        widget.bind("<Leave>", lambda e: self.set_hover(False))
        for child in widget.winfo_children():
            self.bind_hover_recursive(child)




### Drive Display Container ###
class DriveItemPicker(ctk.CTkScrollableFrame):
    def __init__(self, master, open_folder_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.checkboxes = []
        self.items = []
        self.open_folder_callback = open_folder_callback

    def load_items(self, items, folder_mime):
        for row in self.winfo_children():
            row.destroy()

        self.checkboxes.clear()
        self.items = items

        for i, item in enumerate(items):
            row_frame = ctk.CTkFrame(self, fg_color="transparent")
            row_frame.grid(row=i, column=0, padx=8, pady=(6, 0), sticky="ew")
            row_frame.grid_columnconfigure(0, weight=1)

            prefix = "[Folder]" if item["mimeType"] == folder_mime else "[File]"
            label = f"{prefix} {item['name']}"

            checkbox = ctk.CTkCheckBox(row_frame, text=label)
            checkbox.grid(row=0, column=0, sticky="w")

            if item["mimeType"] == folder_mime:
                open_button = ctk.CTkButton(
                    row_frame,
                    text="Open",
                    width=70,
                    command=lambda folder=item: self.open_folder_callback(folder)
                )
                open_button.grid(row=0, column=1, padx=(10, 0))

            self.checkboxes.append((checkbox, item["id"], item))

    def get_selected_items(self):
        return [item for checkbox, _, item in self.checkboxes if checkbox.get() == 1]

    def select_all(self):
        for checkbox, _, _ in self.checkboxes:
            checkbox.select()

    def clear_all(self):
        for checkbox, _, _ in self.checkboxes:
            checkbox.deselect()

### APPEARANCE ###
class DriveApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Drive to SSD")
        self.geometry("1040x720")
        self.minsize(900, 600)

        self.creds = None
        self.service = None
        self.current_folder_id = "root"
        self.current_folder_name = "My Drive"
        self.folder_history = []
        self.current_items = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Overall Container #
        self.container = ctk.CTkFrame(self, corner_radius=16)
        self.container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(5, weight=1)


        # Title #
        self.title_label = ctk.CTkLabel(
            self.container,
            text="Google Drive Browser",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")


        # Top buttons Container #
        self.top_buttons = ctk.CTkFrame(self.container, fg_color="transparent")
        self.top_buttons.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Login Button #
        self.login_button = ctk.CTkButton(
            self.top_buttons,
            text="Sign in with Google",
            command=self.handle_login
        )
        self.login_button.grid(row=0, column=0, padx=(0, 10), pady=0)

        self.download_button = ctk.CTkButton(
            self.top_buttons,
            text="Download Selected",
            command=self.download_selected,
            state="disabled",
            fg_color="green"
        )
        self.download_button.grid(row=0, column=1, padx=(0, 10), pady=0)

        self.path_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.path_frame.grid(row=3, column=0, padx=20, pady=(0, 40), sticky="ew")
        self.path_frame.grid_columnconfigure(0, weight=1)

        self.path_entry = ctk.CTkEntry(
            self.path_frame,
            placeholder_text="Choose external SSD folder"
        )
        self.path_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.browse_button = ctk.CTkButton(
            self.path_frame,
            text="Browse",
            width=100,
            command=self.browse_folder
        )
        self.browse_button.grid(row=0, column=1)




        # Drive Bar Buttons #
        self.drive_bar_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.drive_bar_frame.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.drive_bar_frame.grid_columnconfigure(4, weight=1)

        self.back_button = ctk.CTkButton(
            self.drive_bar_frame,
            text="Back",
            width=90,
            command=self.go_back,
            state="disabled"
        )
        self.back_button.grid(row=0, column=0, padx=(0, 10))

        self.refresh_button = ctk.CTkButton(
            self.drive_bar_frame,
            text="Refresh",
            command=self.load_files,
            state="disabled",
            width=100
        )
        self.refresh_button.grid(row=0, column=1, padx=(0, 10), pady=0)

        self.select_all_button = ctk.CTkButton(
            self.drive_bar_frame,
            text="Select All",
            command=self.select_all_items,
            state="disabled",
            width=110
        )
        self.select_all_button.grid(row=0, column=2, padx=(0, 10), pady=0)

        self.clear_button = ctk.CTkButton(
            self.drive_bar_frame,
            text="Deselect",
            command=self.clear_items,
            state="disabled",
            width=90
        )
        self.clear_button.grid(row=0, column=3, padx=(0, 10), pady=0)

        self.folder_label = ctk.CTkLabel(
            self.drive_bar_frame,
            text="My Drive",
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.folder_label.grid(row=0, column=4, sticky="ew")



        self.item_picker = DriveItemPicker(self.container, open_folder_callback=self.open_folder)
        self.item_picker.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="nsew")

        self.status_label = ctk.CTkLabel(
            self.container,
            text="Not signed in",
            anchor="w"
        )
        self.status_label.grid(row=6, column=0, padx=20, pady=(0, 10), sticky="ew")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

    def handle_login(self):
        def task():
            try:
                self.set_status("Signing in... Check terminal for Google auth URL if needed.")
                self.creds = get_credentials()
                self.service = get_drive_service(self.creds)
                self.enable_controls()
                self.set_status("Signed in successfully")
                self.load_files()
            except Exception as e:
                self.set_status("Login failed")
                self.after(0, lambda: messagebox.showerror("Login Error", str(e)))

        threading.Thread(target=task, daemon=True).start()

    def enable_controls(self):
        self.after(0, lambda: self.refresh_button.configure(state="normal"))
        self.after(0, lambda: self.select_all_button.configure(state="normal"))
        self.after(0, lambda: self.clear_button.configure(state="normal"))
        self.after(0, lambda: self.download_button.configure(state="normal"))

    def set_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=text))

    def load_files(self):
        if not self.service:
            return

        try:
            self.current_items = list_folder(self.service, self.current_folder_id)
            self.after(0, lambda: self.item_picker.load_items(self.current_items, FOLDER_MIME))
            self.set_status(f"Loaded {len(self.current_items)} items from {self.current_folder_name}")
        except Exception as e:
            self.set_status("Failed to load files")
            self.after(0, lambda: messagebox.showerror("Load Error", str(e)))

    def open_folder(self, folder_item):
        self.folder_history.append((self.current_folder_id, self.current_folder_name))
        self.current_folder_id = folder_item["id"]
        self.current_folder_name = folder_item["name"]
        self.after(0, lambda: self.folder_label.configure(text=self.current_folder_name))
        self.after(0, lambda: self.back_button.configure(state="normal"))
        self.load_files()

    def go_back(self):
        if not self.folder_history:
            return

        self.current_folder_id, self.current_folder_name = self.folder_history.pop()
        self.folder_label.configure(text=self.current_folder_name)

        if not self.folder_history:
            self.back_button.configure(state="disabled")

        self.load_files()

    def select_all_items(self):
        self.item_picker.select_all()

    def clear_items(self):
        self.item_picker.clear_all()

    def report_progress(self, name, percent):
        self.set_status(f"Downloading {name}... {percent}%")

    def download_selected(self):
        selected_items = self.item_picker.get_selected_items()

        if not selected_items:
            messagebox.showwarning("No selection", "Select at least one file or folder.")
            return

        output_folder = self.path_entry.get().strip()
        if not output_folder:
            messagebox.showwarning("No destination", "Choose an SSD folder first.")
            return

        def task():
            try:
                total = len(selected_items)
                for idx, item in enumerate(selected_items, start=1):
                    self.set_status(f"Processing {idx}/{total}: {item['name']}")
                    if item["mimeType"] == FOLDER_MIME:download_folder_recursive(
                            self.service,
                            item["id"],
                            item["name"],
                            output_folder,
                            self.report_progress,
                        )
                    else:
                        download_file(
                            self.service,
                            item["id"],
                            item["name"],
                            output_folder,
                            item.get("mimeType"),
                            self.report_progress,
                        )

                self.set_status("Download complete")
                self.after(0, lambda: messagebox.showinfo("Done", "Selected items downloaded successfully."))
            except Exception as e:
                self.set_status("Download failed")
                self.after(0, lambda: messagebox.showerror("Download Error", str(e)))

        threading.Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    if not os.path.exists("credentials.json"):
        root = ctk.CTk()
        root.withdraw()
        messagebox.showerror("Missing credentials", "credentials.json was not found in this folder.")
        root.destroy()
    else:
        app = DriveApp()
        app.mainloop()