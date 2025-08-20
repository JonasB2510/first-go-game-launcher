import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import requests
import threading
import zipfile
import os
import yaml
import shutil
import subprocess
import time

# --- CONFIG ---
OWNER = "jonasb2510"       # Hardcoded repo owner
REPO = "first-go-game"   # Hardcoded repo name
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
stop_threads = False

def get_config_data():
    config_path = os.path.join(os.getenv("appdata"), "first-go-game-launcher")
    os.makedirs(config_path, exist_ok=True)
    config_file = os.path.join(config_path, "config.yml")
    if not os.path.exists(config_file):
        versions_path = os.path.join(config_path, "versions")
        os.makedirs(versions_path, exist_ok=True)
        data = {
            "settings": {"download_dir": versions_path, "version": os.listdir(versions_path)[-1]}
        }
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
    else:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    return data

def open_release_downloader(owner, repo):
    global root
    global windl
    releases = []
    versions = []

    def fetch_releases():
        # Clear previous releases
        listbox.delete(0, "end")
        releases.clear()
        
        # Disable button during fetch
        fetch_btn.configure(state="disabled", text="Fetching...")
        
        def do_fetch():
            try:
                res = requests.get(API_URL, headers={"Accept": "application/vnd.github+json"})
                res.raise_for_status()
                data = res.json()
                
                for release in data:
                    name = release["name"] or release["tag_name"]
                    zip_url = release["zipball_url"]
                    assets = release.get("assets", [])
                    releases.append((name, zip_url, assets))
                    listbox.insert("end", name)
                
                if not releases:
                    messagebox.showinfo("Info", "No releases found.", parent=windl)
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to fetch releases: {str(e)}", parent=windl)
            finally:
                # Re-enable button
                fetch_btn.configure(state="normal", text="Fetch Releases")
        
        # Run fetch in separate thread to avoid blocking UI
        threading.Thread(target=do_fetch, daemon=True).start()

    def download_all(save_dir):
        selection = listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Please select a release", parent=windl)
            return

        if selection[0] >= len(releases):
            messagebox.showerror("Error", "Invalid selection", parent=windl)
            return

        release_name, zip_url, assets = releases[selection[0]]
        #save_dir = filedialog.askdirectory(title="Select folder to save files")
        #os.makedirs("dl", exist_ok=True)
        #save_dir = os.path.join(os.getcwd(), "dl")
        if not save_dir:
            return

        # Disable download button during download
        download_btn.configure(state="disabled", text="Downloading...")

        def do_download():
            try:
                # Create release-specific directory
                #release_dir = os.path.join(save_dir, f"{release_name}_release")
                os.makedirs(save_dir, exist_ok=True)
                version_dir = os.path.join(save_dir, release_name)
                os.makedirs(version_dir, exist_ok=True)
                
                # --- Download and unzip source code ---
                zip_path = os.path.join(version_dir, f"{release_name}_source.zip")
                
                print(f"Downloading source code from: {zip_url}")
                with requests.get(zip_url, stream=True) as r:
                    r.raise_for_status()
                    with open(zip_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                # Extract source code
                source_dir = os.path.join(version_dir, "source")
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(source_dir)

                # Remove the zip file after extraction
                os.remove(zip_path)

                for a in os.listdir(source_dir):
                    if a.lower().startswith(OWNER + "-" + REPO): #"JonasB2510-first-go-game"
                        repo_folder = os.path.join(source_dir, a)
                        for b in os.listdir(repo_folder):
                            shutil.move(os.path.join(repo_folder, b), os.path.join(source_dir, b))
                        os.rmdir(repo_folder)

                # --- Download all assets ---
                if assets:
                    #assets_dir = os.path.join(version_dir, "assets")
                    #os.makedirs(assets_dir, exist_ok=True)
                    
                    for asset in assets:
                        asset_name = asset["name"]
                        asset_url = asset["browser_download_url"]
                        asset_path = os.path.join(source_dir, asset_name)
                        
                        print(f"Downloading asset: {asset_name}")
                        with requests.get(asset_url, stream=True) as r:
                            r.raise_for_status()
                            with open(asset_path, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    f.write(chunk)
                
                data = {
                    "metadata": {"version": release_name}
                }
                config_file = os.path.join(version_dir, "metadata.yml")
                with open(config_file, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, allow_unicode=True)

                messagebox.showinfo("Success", f"Downloaded release '{release_name}' to:\n{version_dir}", parent=windl)

            except Exception as e:
                messagebox.showerror("Error", f"Download failed: {str(e)}", parent=windl)
            finally:
                # Re-enable download button
                download_btn.configure(state="normal", text="Download")
                #windl.destroy()

        threading.Thread(target=do_download, daemon=True).start()

    def reload_downloaded_versions():
        versions.clear()
        listbox_manage.delete(0, "end")
        reload_version_folder_button.configure(state="disabled", text="Loading...")
        data = get_config_data()
        version_folder = data["settings"]["download_dir"]   
        if not os.path.exists(version_folder):
            reload_version_folder_button.configure(state="normal", text="Reload downloaded versions")
            return  
        downloaded_versions = os.listdir(version_folder)
        downloaded_versions.sort(reverse=True)
        for a in downloaded_versions:
            full_dir = os.path.join(version_folder, a)
            meta_data_file = os.path.join(full_dir, "metadata.yml") 
            if os.path.isdir(full_dir) and os.path.exists(meta_data_file):
                try:
                    with open(meta_data_file, "r") as f:
                        data = yaml.safe_load(f)
                    current_version = data["metadata"]["version"]
                    versions.append((a, current_version))
                    listbox_manage.insert("end", f"{a} - {current_version}")
                except Exception as e:
                    print(f"Error reading metadata for {a}: {e}")   
        reload_version_folder_button.configure(state="normal", text="Reload downloaded versions")

    def get_selected_version():
        """Get the currently selected version from the listbox"""
        selection = listbox_manage.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a version first.")
            return None

        selected_index = selection[0]
        if selected_index < len(versions):
            return versions[selected_index][0]  # Return folder name
        return None

    def rename_version():
        """Rename the selected version folder"""
        def do_rename(selected_folder, new_name):
            #selected_folder = get_selected_version()
            if not selected_folder:
                return
            
            if not new_name or new_name == selected_folder:
                return

            # Validate new name (basic validation)
            if not new_name.strip() or "/" in new_name or "\\" in new_name:
                messagebox.showerror("Invalid Name", "Invalid folder name. Avoid special characters.")
                return

            data = get_config_data()
            version_folder = data["settings"]["download_dir"]
            old_path = os.path.join(version_folder, selected_folder)
            new_path = os.path.join(version_folder, new_name.strip())

            # Check if new name already exists
            if os.path.exists(new_path):
                messagebox.showerror("Name Exists", f"A folder named '{new_name}' already exists.")
                return

            try:
                os.rename(old_path, new_path)
                messagebox.showinfo("Success", f"Renamed '{selected_folder}' to '{new_name}'")
                reload_downloaded_versions()  # Refresh the list
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename: {str(e)}")
        selected_version = get_selected_version()
        if not selected_version:
            return

        renamewin = ctk.CTkToplevel()
        renamewin.title(f"Rename Window")
        renamewin.geometry("200x150")
        renamewin.transient(root)  # Make it a child of main window
        renamewin.grab_set()       # Make it modal

        # Center the window
        renamewin.update_idletasks()
        x = (renamewin.winfo_screenwidth() // 2) - (600 // 2)
        y = (renamewin.winfo_screenheight() // 2) - (550 // 2)
        renamewin.geometry(f"200x150+{x}+{y}")

        renamewin_text = ctk.StringVar(renamewin, value=selected_version)
        renamewin_entry = ctk.CTkEntry(renamewin, textvariable=renamewin_text)
        renamewin_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        renamewin_button = ctk.CTkButton(renamewin, text="Rename", command=lambda: do_rename(selected_version, renamewin_text.get()))
        renamewin_button.grid(row=1, column=0, sticky="", padx=10, pady=10)

        renamewin.grid_columnconfigure(0, weight=1)

    def delete_version():
        """Delete the selected version folder"""
        selected_folder = get_selected_version()
        if not selected_folder:
            return

        # Confirm deletion
        response = messagebox.askyesno(
            "Confirm Delete", 
            f"Are you sure you want to delete '{selected_folder}'?\n\nThis action cannot be undone."
        )

        if not response:
            return

        data = get_config_data()
        version_folder = data["settings"]["download_dir"]
        folder_path = os.path.join(version_folder, selected_folder)

        try:
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
                messagebox.showinfo("Success", f"Deleted '{selected_folder}'")
                reload_downloaded_versions()  # Refresh the list
            else:
                messagebox.showwarning("Not Found", f"Folder '{selected_folder}' not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {str(e)}")

    # --- Create popup window ---
    windl = ctk.CTkToplevel()
    windl.title(f"Version Manager")
    windl.geometry("600x850")
    windl.transient(root)  # Make it a child of main window
    windl.grab_set()       # Make it modal

    # Center the window
    windl.update_idletasks()
    x = (windl.winfo_screenwidth() // 2) - (600 // 2)
    y = (windl.winfo_screenheight() // 2) - (550 // 2)
    windl.geometry(f"600x850+{x}+{y}")

    # Title label
    title_label = ctk.CTkLabel(windl, text=f"Releases for {owner}/{repo}", 
                              font=ctk.CTkFont(size=16, weight="bold"))
    title_label.pack(pady=(20, 10))

    list_manage = ctk.CTkFrame(windl)
    list_manage.pack(pady=10, padx=20, fill="both", expand=True)

    button_frame = ctk.CTkFrame(list_manage)  # Replace parent_frame with your actual parent
    button_frame.pack(pady=5)
    
    # Rename button
    rename_button = ctk.CTkButton(
        button_frame, 
        text="Rename", 
        command=rename_version,
        width=10
    )
    rename_button.pack(side="left", padx=5)
    
    # Delete button
    delete_button = ctk.CTkButton(
        button_frame, 
        text="Delete", 
        command=delete_version,
        width=10
    )
    delete_button.pack(side="left", padx=5)
    
    # Keep your existing reload button
    reload_version_folder_button = ctk.CTkButton(
        button_frame,
        text="Reload downloaded versions",
        command=reload_downloaded_versions,
        width=20
    )
    reload_version_folder_button.pack(side="left", padx=5)
    
    # Pack scrollbar FIRST on the right side
    scrollbar_manager = tk.Scrollbar(list_manage, orient="vertical")
    scrollbar_manager.pack(side="right", fill="y")

    listbox_manage = tk.Listbox(
        list_manage, 
        width=70, 
        height=15,
        bg="#212121",  # Dark background to match CTk theme
        fg="white",    # White text
        selectbackground="#1f538d",  # Blue selection
        selectforeground="white",
        relief="flat",
        borderwidth=0,
        font=("Segoe UI", 10),
        yscrollcommand=scrollbar_manager.set  # Connect scrollbar to listbox
    )
    listbox_manage.pack(side="left", fill="both", expand=True)

    # Fetch button
    fetch_btn = ctk.CTkButton(windl, text="Fetch Releases", command=fetch_releases, width=200)
    fetch_btn.pack(pady=10)

    # Listbox frame for better styling
    listbox_frame = ctk.CTkFrame(windl)
    listbox_frame.pack(pady=10, padx=20, fill="both", expand=True)

    # Pack scrollbar FIRST on the right side
    scrollbar = tk.Scrollbar(listbox_frame, orient="vertical")
    scrollbar.pack(side="right", fill="y")

    # Then pack the listbox, filling remaining space
    listbox = tk.Listbox(
        listbox_frame, 
        width=70, 
        height=15,
        bg="#212121",  # Dark background to match CTk theme
        fg="white",    # White text
        selectbackground="#1f538d",  # Blue selection
        selectforeground="white",
        relief="flat",
        borderwidth=0,
        font=("Segoe UI", 10),
        yscrollcommand=scrollbar.set  # Connect scrollbar to listbox
    )
    listbox.pack(side="left", fill="both", expand=True)

    # Configure scrollbar command
    scrollbar.config(command=listbox.yview)

    # Download button
    download_btn = ctk.CTkButton(windl, text="Download", 
                                command=lambda: download_all(get_config_data()["settings"]["download_dir"]), width=250, height=40)
    download_btn.pack(pady=(10, 20))

    reload_downloaded_versions()
    fetch_releases()

    return windl


def optionmenu_callback(choice):
    try:
        config_path = os.path.join(os.getenv("appdata"), "first-go-game-launcher")
        config_file = os.path.join(config_path, "config.yml")
        
        # Read existing config or create new structure
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
        
        # Ensure settings section exists
        if "settings" not in data:
            data["settings"] = {}
        
        data["settings"]["version"] = choice
        
        # Save back to file
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
        
        # Optional: Show success message or close window
        print("Configuration saved successfully!")  # Replace with proper notification
        # win.destroy()  # Uncomment to close window after saving
        
    except Exception as e:
        print(f"Error saving config: {e}")  # Replace with proper error handling

def config_configuration_screen():
    win = ctk.CTkToplevel()
    win.title("Config Configuration Screen")
    win.minsize(width=400, height=400)
    win.maxsize(width=800, height=800)
    win.geometry("600x250")
    win.transient(root)
    win.grab_set()

    win.update_idletasks()
    x = (win.winfo_screenwidth() // 2) - (600 // 2)
    y = (win.winfo_screenheight() // 2) - (550 // 2)
    win.geometry(f"600x250+{x}+{y}")

    # Create StringVar first
    version_dir_text = ctk.StringVar()
    
    version_dir_entry = ctk.CTkEntry(win, placeholder_text="Enter version directory", textvariable=version_dir_text)
    version_dir_entry.grid(row=0, column=0, sticky="we", padx=10, pady=10)

    def choose_version_folder():
        version_dir = filedialog.askdirectory(initialdir=version_dir_text.get())
        if version_dir:  # Only update if user didn't cancel
            version_dir_text.set(version_dir)
    
    def open_version_folder():
        version_folder_path = version_dir_text.get()
        if os.path.exists(version_folder_path):
            os.startfile(version_folder_path)

    choose_version_folder_button = ctk.CTkButton(win, text="Choose Folder", command=choose_version_folder)
    choose_version_folder_button.grid(row=0, column=1, sticky="e", padx=10, pady=10)

    open_version_folder_button = ctk.CTkButton(win, text="Open Folder", command=open_version_folder)
    open_version_folder_button.grid(row=1, column=1, sticky="e", padx=10, pady=10)

    win.grid_columnconfigure(0, weight=1)

    def save_config():
        try:
            config_path = os.path.join(os.getenv("appdata"), "first-go-game-launcher")
            config_file = os.path.join(config_path, "config.yml")
            
            # Read existing config or create new structure
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}
            
            # Ensure settings section exists
            if "settings" not in data:
                data["settings"] = {}
            
            # Update the download_dir with current entry value
            data["settings"]["download_dir"] = version_dir_text.get()
            
            # Create directory if it doesn't exist
            new_dir = version_dir_text.get()
            if new_dir and not os.path.exists(new_dir):
                os.makedirs(new_dir, exist_ok=True)
            
            # Save back to file
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)
            
            # Optional: Show success message or close window
            print("Configuration saved successfully!")  # Replace with proper notification
            # win.destroy()  # Uncomment to close window after saving
            
        except Exception as e:
            print(f"Error saving config: {e}")  # Replace with proper error handling

    save_button = ctk.CTkButton(win, text="Save", command=save_config)
    save_button.grid(row=1, column=0, sticky="")

    def load_config():
        
        data = get_config_data()
        # Now just set the StringVar value
        version_dir_text.set(data["settings"]["download_dir"])
    
    load_config()

def startgame(mode="host", arg="8080"):
    """
    Start the game with specified mode and arguments
    mode: "host" or "join"
    arg: port number for host mode, or join link for join mode
    """
    global root
    data = get_config_data()
    game_exe = os.path.join(data["settings"]["download_dir"], data["settings"]["version"], "source", "main.exe")
    game_dir = os.path.join(data["settings"]["download_dir"], data["settings"]["version"], "source")
    
    if not os.path.exists(game_exe):
        print(f"Game executable not found at: {game_exe}")
        messagebox.showerror("Error", f"Game executable not found at: {game_exe}.\nYou probably downloaded a version without a precompiled main.exe. You either download another version or compile it yourself by simply downloading golang and typing \n'go build main.go'\n in a console window in the source folder", parent=root)
        return
    
    # Method 1: Using subprocess (recommended)
    def run_game():
        try:
            # Build command with arguments
            if mode == "host":
                cmd = [game_exe, "host", str(arg)]
            elif mode == "join":
                cmd = [game_exe, "join", str(arg)]
            else:
                print(f"Invalid mode: {mode}")
                return
            
            print(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=game_dir, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Game exited with error code: {e.returncode}")
        except Exception as e:
            print(f"Error running game: {e}")
    
    game_thread = threading.Thread(target=run_game)
    game_thread.daemon = True  # Thread will close when main program closes
    game_thread.start()

def startgame_window():
    global startmode
    global port_text
    global port_entry

    data = get_config_data()
    if data["settings"]["version"] == "":
        return

    win = ctk.CTkToplevel()
    win.title("Start Screen")
    win.minsize(width=250, height=250)
    win.maxsize(width=250, height=250)
    win.geometry("250x250")
    win.transient(root)
    win.grab_set()

    win.update_idletasks()
    x = (win.winfo_screenwidth() // 2) - (600 // 2)
    y = (win.winfo_screenheight() // 2) - (550 // 2)
    win.geometry(f"250x250+{x}+{y}")

    """Create a customizable start menu based on version.yml configuration"""
    
    # Get configuration data
    download_dir_path = get_config_data()["settings"]["download_dir"]
    current_version = get_config_data()["settings"]["version"]
    full_path = os.path.join(download_dir_path, current_version, "source", "version.yml")

    if not os.path.exists(full_path):
        win.destroy()
        return

    with open(full_path, "r") as f:
        version_data = yaml.safe_load(f)

    # Get default mode from config
    startmode = version_data["version-data"]["standart-mode"]
    
    # Configure grid
    win.grid_columnconfigure(0, weight=1)
    
    # Storage for UI elements and their data
    ui_elements = {}
    current_entries = {}
    
    def update_entries_for_mode(selected_mode):
        """Update entry fields based on selected mode"""
        global startmode
        startmode = selected_mode
        
        # Clear existing entries
        for entry_widget in current_entries.values():
            #entry_widget.delete(0, 'end')#.destroy()
            if not isinstance(entry_widget, ctk.StringVar):
                entry_widget.destroy()
        current_entries.clear()
        
        # Find the start args configuration
        start_args_config = None
        for config_key, config_data in version_data["version-data"]["start-args"].items():
            if config_data["type"] == "optionmenu":
                start_args_config = config_data
                break
        
        if not start_args_config:
            return
            
        # Get args for the selected mode
        mode_args = start_args_config["args"].get(selected_mode, {})
        
        # Create entry fields for the selected mode
        row = 1
        for arg_key, arg_data in mode_args.items():
            if arg_data["type"] == "entry":
                # Create label
                label = ctk.CTkLabel(win, text=arg_data["name"])
                label.grid(row=row, column=0, sticky="w", padx=10, pady=(5, 0))
                
                # Create entry with default value
                entry_var = ctk.StringVar(win)
                entry_var.set(str(arg_data["standard"]))
                
                entry = ctk.CTkEntry(win, textvariable=entry_var, width=200)
                entry.grid(row=row+1, column=0, sticky="ew", padx=10, pady=(0, 10))
                
                # Store references
                current_entries[f"{selected_mode}_{arg_key}_label"] = label
                current_entries[f"{selected_mode}_{arg_key}_entry"] = entry
                current_entries[f"{selected_mode}_{arg_key}_var"] = entry_var
                
                row += 2
    
    def get_current_arg_value():
        """Get the current argument value based on selected mode"""
        for key, var in current_entries.items():
            if key.endswith("_var") and isinstance(var, ctk.StringVar):
                return var.get()
        return ""
    
    def start_game_wrapper():
        """Wrapper function to start the game with current settings"""
        arg_value = get_current_arg_value()
        startgame(startmode, arg_value)
    
    # Create the option menu for mode selection
    mode_options = []
    start_args_config = None
    
    # Find the optionmenu configuration and extract available modes
    for config_key, config_data in version_data["version-data"]["start-args"].items():
        if config_data["type"] == "optionmenu":
            start_args_config = config_data
            mode_options = list(config_data["args"].keys())
            break
    
    if mode_options:
        # Create mode selection dropdown
        mode_label = ctk.CTkLabel(win, text="Select Mode:")
        mode_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        mode_var = ctk.StringVar(win)
        mode_var.set(startmode)  # Set default mode
        
        mode_optionmenu = ctk.CTkOptionMenu(
            win, 
            values=mode_options,
            variable=mode_var,
            command=update_entries_for_mode,
            width=200
        )
        mode_optionmenu.grid(row=0, column=0, sticky="ew", padx=10, pady=(30, 10))
        
        # Initialize with default mode
        update_entries_for_mode(startmode)
        
        # Calculate the row for the start button (after all possible entries)
        max_entries = max(len(mode_config) for mode_config in start_args_config["args"].values())
        start_button_row = 1 + (max_entries * 2) + 1
        
        # Create start game button
        start_game_button = ctk.CTkButton(
            win, 
            text="Start Game", 
            command=start_game_wrapper,
            width=200,
            height=40
        )
        start_game_button.grid(row=start_button_row, column=0, padx=10, pady=20)
    


    #start_game_button = ctk.CTkButton(win, text="Start game", command=lambda: startgame(startmode, port_text.get()))
    #start_game_button.grid(row=2, column=0)

    win.mainloop()

def reload_available_versions():
    global optionmenu
    global optionmenu_var
    global stop_threads
    #global windl
    def save_config(value):
        try:
            config_path = os.path.join(os.getenv("appdata"), "first-go-game-launcher")
            config_file = os.path.join(config_path, "config.yml")
            
            # Read existing config or create new structure
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}
            
            # Ensure settings section exists
            if "settings" not in data:
                data["settings"] = {}

            data["settings"]["version"] = value#values[0]
            
            # Save back to file
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)
            
            # Optional: Show success message or close window
            print("Configuration saved successfully!")  # Replace with proper notification
            #windl.destroy()  # Uncomment to close window after saving
            
        except Exception as e:
            print(f"Error saving config: {e}")  # Replace with proper error handling
    while not stop_threads:
        values = os.listdir(get_config_data()["settings"]["download_dir"])
        if get_config_data()["settings"]["version"] in values:
            optionmenu_var.set(value=get_config_data()["settings"]["version"])
        if get_config_data()["settings"]["version"] not in values and values != []:
            optionmenu_var.set(value=values[-1])
            save_config(values[-1])
        if get_config_data()["settings"]["version"] not in values and values == []:
            optionmenu_var.set(value="")
            values.append("")
            if get_config_data()["settings"]["version"] != "":
                save_config("")
        #if optionmenu_var.get() not in values and get_config_data()["settings"]["version"] not in values:
        #    print("current selected and saved version not available")
        #    optionmenu_var.set(value=values[0])
        #if optionmenu_var.get() == "" and get_config_data()["settings"]["version"] in values:
        #    #optionmenu_var.set(values[0])
        #    optionmenu_var.set(get_config_data()["settings"]["version"])
        #    print("reloading save_config")
        #    save_config(get_config_data()["settings"]["version"])
        optionmenu.configure(values=values)
        time.sleep(1)
    print("thread-1 stopped (reload thread)")

def main():
    global optionmenu
    global optionmenu_var
    global root

    def on_closing():
        global stop_threads
        stop_threads = True
        reload_thread.join()
        root.quit()
    # --- Main window ---
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("First-go-game Installer")
    root.geometry("400x250")

    # Center the main window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (400 // 2)
    y = (root.winfo_screenheight() // 2) - (250 // 2)
    root.geometry(f"400x250+{x}+{y}")

    # Main title
    main_title = ctk.CTkLabel(root, text="First-go-game Installer", 
                             font=ctk.CTkFont(size=20, weight="bold"))
    main_title.pack(pady=(30, 20))

    menubar = tk.Menu(root)

    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Config", command=config_configuration_screen)
    file_menu.add_command(label="Versions", command=lambda: open_release_downloader(OWNER, REPO))
    file_menu.add_command(label="Port Forward")
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=on_closing) #root.quit
    menubar.add_cascade(label="File", menu=file_menu)

    root.config(menu=menubar)

    def reset_config():
        try:
            config_path = os.path.join(os.getenv("appdata"), "first-go-game-launcher")
            config_file = os.path.join(config_path, "config.yml")
            
            # Read existing config or create new structure
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}
            
            # Ensure settings section exists
            if "settings" not in data:
                data["settings"] = {}
            
            # Update the download_dir with current entry value
            data["settings"]["download_dir"] = os.path.join(os.getenv("appdata"), "first-go-game-launcher", "versions")
            
            # Save back to file
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)
            
            # Optional: Show success message or close window
            print("Configuration saved successfully!")  # Replace with proper notification
            # win.destroy()  # Uncomment to close window after saving
            
        except Exception as e:
            print(f"Error saving config: {e}")  # Replace with proper error handling


    # Repository info
    #repo_info = ctk.CTkLabel(root, text=f"Repository: {OWNER}/{REPO}", 
    #                        font=ctk.CTkFont(size=12), text_color="gray")
    #repo_info.pack(pady=(0, 30))
    try:
        version_values = os.listdir(get_config_data()["settings"]["download_dir"])
    except FileNotFoundError:
        version_values = os.path.join(os.getenv("appdata"), "first-go-game-launcher", "versions")
        os.makedirs(version_values, exist_ok=True)
        reset_config()
        messagebox.showerror("Error", f"Version folder got reseted to {version_values} because the custom folder could not be found!", parent=root)
    if version_values == []:
        version_values.append("")

    optionmenu_var = ctk.StringVar(value="")
    optionmenu = ctk.CTkOptionMenu(root, values=version_values,
                                         command=optionmenu_callback,
                                         variable=optionmenu_var)
    optionmenu.pack()

    #def on_version_select():
    #    open_release_downloader(OWNER, REPO)

    # Open button
    #open_btn = ctk.CTkButton(root, text="Open Release Downloader", 
    #                        command=on_version_select, width=250, height=40)
    #open_btn.pack(pady=20)

    # Footer
    #footer = ctk.CTkLabel(root, text="Select releases to download source code and assets", 
    #                     font=ctk.CTkFont(size=10), text_color="gray")
    #footer.pack(side="bottom", pady=(0, 20))
    start_game_button = ctk.CTkButton(root, text="Start game", command=startgame_window)
    start_game_button.pack()

    reload_thread = threading.Thread(target=reload_available_versions)
    reload_thread.start()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    root.mainloop()

if __name__ == "__main__":
    main()