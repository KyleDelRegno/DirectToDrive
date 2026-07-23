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


# ---------------------------------------------------------------------------
# Color system
# Each value is a (light, dark) tuple, matching customtkinter's convention.
# ---------------------------------------------------------------------------
COLOR = {
    "bg": ("#E8EBF4", "#222831"),
    "surface": ("#FFFFFF", "#393E46"),
    "surface_alt": ("#DADEED", "#5D6573"),
    "border": ("#E2D9C9", "#595D63"),
    "text": ("#20232B", "#FFFFFF"),
    "text_muted": ("#18191C", "#858A9C"),
    "accent": ("#6E8FA8", "#7FA3BC"),
    "accent_hover": ("#5C7A90", "#6C90A8"),
    "success": ("#5FA86E", "#5FA86E"),
    "danger": ("#B4483F", "#C65A50"),
}

FONT_FAMILY = "Helvetica"
SIDEBAR_WIDTH = 320
SIDEBAR_PADX = 16


def font(size, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


# ---------------------------------------------------------------------------
# A single row in the file/folder list
# ---------------------------------------------------------------------------
class DriveItemRow(ctk.CTkFrame):
    def __init__(self, master, item, folder_mime, open_folder_callback):
        super().__init__(
            master,
            corner_radius=10,
            fg_color=COLOR["surface"],
            border_width=1,
            border_color=COLOR["border"],
        )
        self.item = item
        self.is_folder = item["mimeType"] == folder_mime

        self.grid_columnconfigure(1, weight=1)

        icon = "\U0001F4C1" if self.is_folder else "\U0001F4C4"
        self.icon_label = ctk.CTkLabel(self, text=icon, font=font(16), width=28)
        self.icon_label.grid(row=0, column=0, padx=(14, 4), pady=10, sticky="w")

        self.checkbox = ctk.CTkCheckBox(
            self,
            text=item["name"],
            font=font(13),
            text_color=COLOR["text"],
            fg_color=COLOR["accent"],
            hover_color=COLOR["accent_hover"],
            checkbox_width=18,
            checkbox_height=18,
        )
        self.checkbox.grid(row=0, column=1, padx=(0, 12), pady=10, sticky="w")

        if self.is_folder:
            self.open_button = ctk.CTkButton(
                self,
                text="Open  \u2192",
                width=74,
                height=28,
                corner_radius=8,
                font=font(12),
                fg_color=COLOR["surface_alt"],
                text_color=COLOR["text"],
                hover_color=COLOR["border"],
                command=lambda folder=item: open_folder_callback(folder),
            )
            self.open_button.grid(row=0, column=2, padx=(0, 12), pady=8)

        self._bind_hover(self)

    def _bind_hover(self, widget):
        widget.bind("<Enter>", lambda e: self.configure(fg_color=COLOR["surface_alt"]))
        widget.bind("<Leave>", lambda e: self.configure(fg_color=COLOR["surface"]))
        for child in widget.winfo_children():
            if child is not getattr(self, "open_button", None):
                self._bind_hover(child)

    def get(self):
        return self.checkbox.get() == 1

    def select(self):
        self.checkbox.select()

    def deselect(self):
        self.checkbox.deselect()


# ---------------------------------------------------------------------------
# Scrollable list container
# ---------------------------------------------------------------------------
class DriveItemPicker(ctk.CTkScrollableFrame):
    def __init__(self, master, open_folder_callback, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.rows = []
        self.open_folder_callback = open_folder_callback

    def load_items(self, items, folder_mime):
        for row in self.rows:
            row.destroy()
        self.rows.clear()

        if not items:
            empty = ctk.CTkLabel(
                self,
                text="This folder is empty.",
                font=font(13),
                text_color=COLOR["text_muted"],
            )
            empty.grid(row=0, column=0, pady=30)
            self.rows.append(empty)
            return

        for i, item in enumerate(items):
            row = DriveItemRow(self, item, folder_mime, self.open_folder_callback)
            row.grid(row=i, column=0, padx=2, pady=4, sticky="ew")
            self.rows.append(row)

    def get_selected_items(self):
        return [row.item for row in self.rows if isinstance(row, DriveItemRow) and row.get()]

    def select_all(self):
        for row in self.rows:
            if isinstance(row, DriveItemRow):
                row.select()

    def clear_all(self):
        for row in self.rows:
            if isinstance(row, DriveItemRow):
                row.deselect()


# ---------------------------------------------------------------------------
# Sidebar section header
# ---------------------------------------------------------------------------
def section_label(master, text):
    return ctk.CTkLabel(
        master,
        text=text.upper(),
        font=font(11, "bold"),
        text_color=COLOR["text_muted"],
        anchor="w",
    )


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------
class DriveApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Drive to SSD")
        self.geometry("1160x720")
        self.minsize(980, 600)
        self.configure(fg_color=COLOR["bg"])

        self.creds = None
        self.service = None
        self.current_folder_id = "root"
        self.current_folder_name = "My Drive"
        self.folder_history = []  # list of (id, name)
        self.current_items = []
        self.signed_in = False

        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_panel()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=COLOR["surface"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(9, weight=1)

        # Brand
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=SIDEBAR_PADX, pady=(26, 4), sticky="ew")
        ctk.CTkLabel(
            brand, text="Drive \u2192 SSD", font=font(20, "bold"), text_color=COLOR["text"]
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="Google Drive backup tool",
            font=font(12),
            text_color=COLOR["text_muted"],
        ).pack(anchor="w")

        # Account status card
        account_card = ctk.CTkFrame(sidebar, corner_radius=12, fg_color=COLOR["surface_alt"])
        account_card.grid(row=1, column=0, padx=SIDEBAR_PADX, pady=(18, 6), sticky="ew")
        account_card.grid_columnconfigure(1, weight=1)

        self.status_dot = ctk.CTkLabel(
            account_card, text="\u25CF", font=font(14), text_color=COLOR["danger"], width=16
        )
        self.status_dot.grid(row=0, column=0, padx=(14, 4), pady=12)

        self.status_label = ctk.CTkLabel(
            account_card,
            text="Not signed in",
            font=font(12),
            text_color=COLOR["text"],
            anchor="w",
        )
        self.status_label.grid(row=0, column=1, padx=(0, 14), pady=12, sticky="ew")

        self.login_button = ctk.CTkButton(
            sidebar,
            text="Sign in with Google",
            font=font(13, "bold"),
            height=38,
            corner_radius=10,
            fg_color=COLOR["accent"],
            hover_color=COLOR["accent_hover"],
            command=self.handle_login,
        )
        self.login_button.grid(row=2, column=0, padx=SIDEBAR_PADX, pady=(6, 18), sticky="ew")

        # Destination section
        section_label(sidebar, "Destination").grid(row=3, column=0, padx=SIDEBAR_PADX, pady=(4, 6), sticky="ew")

        self.path_entry = ctk.CTkEntry(
            sidebar,
            placeholder_text="Choose external SSD folder",
            font=font(12),
            height=34,
            corner_radius=8,
            border_color=COLOR["border"],
        )
        self.path_entry.grid(row=4, column=0, padx=SIDEBAR_PADX, pady=(0, 6), sticky="ew")

        self.browse_button = ctk.CTkButton(
            sidebar,
            text="Browse\u2026",
            font=font(12),
            height=32,
            corner_radius=8,
            fg_color=COLOR["surface_alt"],
            text_color=COLOR["text"],
            hover_color=COLOR["border"],
            command=self.browse_folder,
        )
        self.browse_button.grid(row=5, column=0, padx=SIDEBAR_PADX, pady=(0, 18), sticky="ew")

        # Actions section
        section_label(sidebar, "Actions").grid(row=6, column=0, padx=SIDEBAR_PADX, pady=(4, 6), sticky="ew")

        actions = ctk.CTkFrame(sidebar, fg_color="transparent")
        actions.grid(row=7, column=0, padx=SIDEBAR_PADX, pady=(0, 10), sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)

        def small_button(parent, text, command):
            return ctk.CTkButton(
                parent,
                text=text,
                font=font(12),
                height=32,
                corner_radius=8,
                fg_color=COLOR["surface_alt"],
                text_color=COLOR["text"],
                hover_color=COLOR["border"],
                state="disabled",
                command=command,
            )

        self.refresh_button = small_button(actions, "\u21BB Refresh", self.load_files)
        self.refresh_button.grid(row=0, column=0, columnspan=2, padx=0, pady=(0, 6), sticky="ew")

        self.select_all_button = small_button(actions, "Select All", self.select_all_items)
        self.select_all_button.grid(row=1, column=0, padx=(0, 4), sticky="ew")

        self.clear_button = small_button(actions, "Deselect", self.clear_items)
        self.clear_button.grid(row=1, column=1, padx=(4, 0), sticky="ew")

        # Download button pinned toward the bottom
        self.download_button = ctk.CTkButton(
            sidebar,
            text="\u2B07  Download Selected",
            font=font(13, "bold"),
            height=42,
            corner_radius=10,
            fg_color=COLOR["success"],
            hover_color=COLOR["accent_hover"],
            state="disabled",
            command=self.download_selected,
        )
        self.download_button.grid(row=10, column=0, padx=SIDEBAR_PADX, pady=(10, 22), sticky="sew")

    # ------------------------------------------------------------------
    # Main panel
    # ------------------------------------------------------------------
    def _build_main_panel(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, padx=24, pady=24, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # Breadcrumb / toolbar
        toolbar = ctk.CTkFrame(main, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        toolbar.grid_columnconfigure(1, weight=1)

        self.back_button = ctk.CTkButton(
            toolbar,
            text="\u2190",
            width=36,
            height=34,
            corner_radius=8,
            font=font(14),
            fg_color=COLOR["surface"],
            text_color=COLOR["text"],
            hover_color=COLOR["surface_alt"],
            border_width=1,
            border_color=COLOR["border"],
            state="disabled",
            command=self.go_back,
        )
        self.back_button.grid(row=0, column=0, padx=(0, 10))

        self.breadcrumb_label = ctk.CTkLabel(
            toolbar,
            text="My Drive",
            font=font(18, "bold"),
            text_color=COLOR["text"],
            anchor="w",
        )
        self.breadcrumb_label.grid(row=0, column=1, sticky="w")

        self.item_count_label = ctk.CTkLabel(
            toolbar, text="", font=font(12), text_color=COLOR["text_muted"]
        )
        self.item_count_label.grid(row=0, column=2, sticky="e", padx=(10, 0))

        # Divider
        divider = ctk.CTkFrame(main, height=1, fg_color=COLOR["border"])
        divider.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # File list
        self.item_picker = DriveItemPicker(main, open_folder_callback=self.open_folder)
        self.item_picker.grid(row=2, column=0, sticky="nsew")

        self._render_placeholder("Sign in with Google to browse your Drive.")

        # Status bar
        status_bar = ctk.CTkFrame(main, corner_radius=10, fg_color=COLOR["surface"])
        status_bar.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        status_bar.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            status_bar,
            height=6,
            corner_radius=3,
            progress_color=COLOR["accent"],
            fg_color=COLOR["surface_alt"],
        )
        self.progress_bar.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            status_bar,
            text="Not signed in",
            font=font(12),
            text_color=COLOR["text_muted"],
            anchor="w",
        )
        self.progress_label.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")

    def _render_placeholder(self, message):
        for row in self.item_picker.rows:
            row.destroy()
        self.item_picker.rows.clear()
        label = ctk.CTkLabel(
            self.item_picker,
            text=message,
            font=font(13),
            text_color=COLOR["text_muted"],
        )
        label.grid(row=0, column=0, pady=40)
        self.item_picker.rows.append(label)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

    def set_status(self, text):
        self.after(0, lambda: self.progress_label.configure(text=text))

    def set_progress(self, fraction):
        self.after(0, lambda: self.progress_bar.set(max(0.0, min(1.0, fraction))))

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def handle_login(self):
        self.login_button.configure(state="disabled", text="Signing in\u2026")

        def task():
            try:
                self.set_status("Signing in\u2026 check your browser to finish Google auth.")
                self.creds = get_credentials()
                self.service = get_drive_service(self.creds)
                self.signed_in = True
                self.after(0, self._on_signed_in)
                self.load_files()
            except Exception as e:
                self.after(0, lambda: self.login_button.configure(state="normal", text="Sign in with Google"))
                self.set_status("Sign-in failed")
                self.after(0, lambda: messagebox.showerror("Login Error", str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_signed_in(self):
        self.status_dot.configure(text_color=COLOR["success"])
        self.status_label.configure(text="Signed in")
        self.login_button.configure(text="Signed in \u2713", fg_color=COLOR["surface_alt"], text_color=COLOR["text"])
        for btn in (self.refresh_button, self.select_all_button, self.clear_button, self.download_button):
            btn.configure(state="normal")
        self.set_status("Ready")

    # ------------------------------------------------------------------
    # Browsing
    # ------------------------------------------------------------------
    def load_files(self):
        if not self.service:
            return

        try:
            self.current_items = list_folder(self.service, self.current_folder_id)
            self.after(0, lambda: self.item_picker.load_items(self.current_items, FOLDER_MIME))
            self.after(0, lambda: self.breadcrumb_label.configure(text=self.current_folder_name))
            count = len(self.current_items)
            self.after(0, lambda: self.item_count_label.configure(
                text=f"{count} item{'s' if count != 1 else ''}"
            ))
            self.set_status(f"Loaded {count} items from {self.current_folder_name}")
        except Exception as e:
            self.set_status("Failed to load files")
            self.after(0, lambda: messagebox.showerror("Load Error", str(e)))

    def open_folder(self, folder_item):
        self.folder_history.append((self.current_folder_id, self.current_folder_name))
        self.current_folder_id = folder_item["id"]
        self.current_folder_name = folder_item["name"]
        self.back_button.configure(state="normal")
        self.load_files()

    def go_back(self):
        if not self.folder_history:
            return

        self.current_folder_id, self.current_folder_name = self.folder_history.pop()
        self.breadcrumb_label.configure(text=self.current_folder_name)

        if not self.folder_history:
            self.back_button.configure(state="disabled")

        self.load_files()

    def select_all_items(self):
        self.item_picker.select_all()

    def clear_items(self):
        self.item_picker.clear_all()

    # ------------------------------------------------------------------
    # Downloading
    # ------------------------------------------------------------------
    def report_progress(self, name, percent):
        self.set_status(f"Downloading {name}\u2026 {percent}%")
        self.set_progress(percent / 100)

    def download_selected(self):
        selected_items = self.item_picker.get_selected_items()

        if not selected_items:
            messagebox.showwarning("No selection", "Select at least one file or folder.")
            return

        output_folder = self.path_entry.get().strip()
        if not output_folder:
            messagebox.showwarning("No destination", "Choose an SSD folder first.")
            return

        self.download_button.configure(state="disabled")

        def task():
            try:
                total = len(selected_items)
                for idx, item in enumerate(selected_items, start=1):
                    self.set_status(f"Processing {idx}/{total}: {item['name']}")
                    self.set_progress(0)
                    if item["mimeType"] == FOLDER_MIME:
                        download_folder_recursive(
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

                self.set_progress(1)
                self.set_status("Download complete")
                self.after(0, lambda: messagebox.showinfo("Done", "Selected items downloaded successfully."))
            except Exception as e:
                self.set_status("Download failed")
                self.after(0, lambda: messagebox.showerror("Download Error", str(e)))
            finally:
                self.after(0, lambda: self.download_button.configure(state="normal"))

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