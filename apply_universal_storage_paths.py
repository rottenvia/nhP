
with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update DEFAULT_LIBRARY_DIR to be Cyrillic-free and universally writable C:\Users\Public\MinimalMediaPlayer on Windows
dir_old = """# Symmetrical Local Media Organizer Folder
DEFAULT_LIBRARY_DIR = os.path.join(os.path.expanduser("~"), "Videos", "MinimalMediaPlayer")
os.makedirs(DEFAULT_LIBRARY_DIR, exist_ok=True)"""

dir_new = """# Symmetrical Local Media Organizer Folder (Cyrillic-free, space-free, universally writable!)
if os.name == 'nt':
    DEFAULT_LIBRARY_DIR = r"C:\\Users\\Public\\MinimalMediaPlayer"
else:
    DEFAULT_LIBRARY_DIR = os.path.expanduser("~/Videos/MinimalMediaPlayer")
os.makedirs(DEFAULT_LIBRARY_DIR, exist_ok=True)"""

if dir_old in code:
    code = code.replace(dir_old, dir_new)
    print("DEFAULT_LIBRARY_DIR updated successfully to public Cyrillic-free path!")
else:
    print("Warning: dir_old pattern not found!")

# 2. Rewrite select_link_folder, select_link_file, and select_files with non-blocking threading.Thread workers
old_dialogs = """    def select_link_folder(self, mal_id, anime_title):
        \"\"\" Opens multi-file dialog, copies/remuxes files into anime's subfolder, and returns paths \"\"\"
        log_to_file(f"=== select_link_folder called for: {anime_title} ===")
        if not self.window:
            return
            
        try:
            file_types = (
                'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                'All Files (*.*)'
            )
            file_paths = self.window.create_file_dialog(
                dialog_type=webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=file_types
            )
            if not file_paths:
                return
                
            if isinstance(file_paths, (list, tuple)):
                file_paths = list(file_paths)
            else:
                file_paths = [file_paths]
                
            anime_title_str = str(anime_title or "Unknown")
            
            import re
            clean_title = re.sub(r'[\\\\/*?:"<>|]', "", anime_title_str).strip()
            anime_dir = os.path.join(DEFAULT_LIBRARY_DIR, clean_title)
            os.makedirs(anime_dir, exist_ok=True)
            
            results = []
            for fp in file_paths:
                original_name = os.path.basename(fp)
                original_selected_path = fp
                
                ep_match = re.search(r'(?:ep|episode|s\\d+e|series|серия|серии)?\\s*(\\d+)', original_name, re.IGNORECASE)
                if ep_match:
                    ep_num = int(ep_match.group(1))
                else:
                    ep_num = 1
                    
                ext = os.path.splitext(original_name)[1].lower()
                target_name = f"Episode_{ep_num}{ext}"
                if ext == '.ts':
                    target_name = f"Episode_{ep_num}.mp4"
                    
                target_path = os.path.join(anime_dir, target_name)
                
                try:
                    if ext == '.ts':
                        ffmpeg_bin = get_ffmpeg_path()
                        if ffmpeg_bin:
                            cmd = [ffmpeg_bin, "-y", "-i", fp, "-c", "copy", "-map_metadata", "0", target_path]
                            startupinfo = None
                            if os.name == 'nt':
                                startupinfo = subprocess.STARTUPINFO()
                                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
                            proc.communicate(timeout=15)
                            if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
                                results.append({
                                    'path': target_path,
                                    'name': target_name
                                })
                            else:
                                results.append({
                                    'path': original_selected_path,
                                    'name': original_name
                                })
                        else:
                            results.append({
                                'path': original_selected_path,
                                'name': original_name
                            })
                    else:
                        import shutil
                        shutil.copy2(fp, target_path)
                        results.append({
                            'path': target_path,
                            'name': target_name
                        })
                except Exception as e:
                    log_to_file(f"Folder copy/remux failed, fallback to original: {e}")
                    results.append({
                        'path': original_selected_path,
                        'name': original_name
                    })
                    
            import json
            js_code = f"completeMultipleEpisodesLinking({mal_id}, {json.dumps(results)});"
            self.window.evaluate_js(js_code)
        except Exception as e:
            log_to_file(f"Exception in select_link_folder: {e}")


    def select_link_file(self, mal_id, ep_num, anime_title):
        \"\"\" Opens file dialog, copies/remuxes file into anime's subfolder, and returns path \"\"\"
        log_to_file(f"=== select_link_file called for: {anime_title}, ep: {ep_num} ===")
        if not self.window:
            return
            
        try:
            file_types = (
                'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                'All Files (*.*)'
            )
            file_paths = self.window.create_file_dialog(
                dialog_type=webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=file_types
            )
            if not file_paths:
                return
                
            fp = file_paths[0] if isinstance(file_paths, (list, tuple)) else file_paths
            original_selected_path = fp
            original_name = os.path.basename(fp)
            
            anime_title_str = str(anime_title or "Unknown")
            
            import re
            clean_title = re.sub(r'[\\\\/*?:"<>|]', "", anime_title_str).strip()
            anime_dir = os.path.join(DEFAULT_LIBRARY_DIR, clean_title)
            os.makedirs(anime_dir, exist_ok=True)
            
            ext = os.path.splitext(original_name)[1].lower()
            target_name = f"Episode_{ep_num}{ext}"
            if ext == '.ts':
                target_name = f"Episode_{ep_num}.mp4"
                
            target_path = os.path.join(anime_dir, target_name)
            
            try:
                if ext == '.ts':
                    ffmpeg_bin = get_ffmpeg_path()
                    if ffmpeg_bin:
                        cmd = [ffmpeg_bin, "-y", "-i", fp, "-c", "copy", "-map_metadata", "0", target_path]
                        startupinfo = None
                        if os.name == 'nt':
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
                        proc.communicate(timeout=15)
                        if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
                            fp = target_path
                            original_name = target_name
                else:
                    import shutil
                    shutil.copy2(fp, target_path)
                    fp = target_path
                    original_name = target_name
            except Exception as e:
                log_to_file(f"Copying/remuxing failed, falling back to original path: {e}")
                fp = original_selected_path
                original_name = os.path.basename(fp)
                
            import json
            processed_file = {"path": fp, "name": original_name, "is_remuxed": (ext == '.ts')}
            js_code = f"completeEpisodeLinking({mal_id}, {ep_num}, {json.dumps(processed_file)});"
            self.window.evaluate_js(js_code)
        except Exception as e:
            log_to_file(f"Exception in select_link_file: {e}")

    def select_files(self):
        \"\"\" Opens a fully native OS file selection dialog directly on the API thread \"\"\"
        log_to_file("=== select_files called ===")
        if not self.window:
            return []
            
        try:
            file_types = (
                'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                'Audio Files (*.mp3;*.wav;*.ogg;*.m4a;*.aac;*.flac)',
                'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                'All Files (*.*)'
            )
            
            file_paths = self.window.create_file_dialog(
                dialog_type=webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=file_types
            )
            if not file_paths:
                return []
                
            if isinstance(file_paths, (list, tuple)):
                file_paths = list(file_paths)
            else:
                file_paths = [file_paths]
                
            results = []
            for fp in file_paths:
                name = os.path.basename(fp)
                results.append({
                    'path': fp,
                    'name': name
                })
            
            import json
            js_code = f"addFilesToPlaylist({json.dumps(results)});"
            self.window.evaluate_js(js_code)
        except Exception as e:
            log_to_file(f"Exception in select_files: {e}")
        return []"""

new_dialogs = """    def select_link_folder(self, mal_id, anime_title):
        \"\"\" Opens multi-file dialog on a background thread to prevent deadlocks, copies/remuxes files safely \"\"\"
        log_to_file(f"=== select_link_folder called for: {anime_title} ===")
        if not self.window:
            return
            
        def worker():
            try:
                file_types = (
                    'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                    'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                    'All Files (*.*)'
                )
                file_paths = self.window.create_file_dialog(
                    dialog_type=webview.OPEN_DIALOG,
                    allow_multiple=True,
                    file_types=file_types
                )
                if not file_paths:
                    return
                    
                if isinstance(file_paths, (list, tuple)):
                    file_paths = list(file_paths)
                else:
                    file_paths = [file_paths]
                    
                anime_title_str = str(anime_title or "Unknown")
                import re
                clean_title = re.sub(r'[\\\\/*?:"<>|]', "", anime_title_str).strip()
                anime_dir = os.path.join(DEFAULT_LIBRARY_DIR, clean_title)
                os.makedirs(anime_dir, exist_ok=True)
                
                results = []
                for fp in file_paths:
                    original_name = os.path.basename(fp)
                    original_selected_path = fp
                    
                    ep_match = re.search(r'(?:ep|episode|s\\d+e|series|серия|серии)?\\s*(\\d+)', original_name, re.IGNORECASE)
                    if ep_match:
                        ep_num = int(ep_match.group(1))
                    else:
                        ep_num = 1
                        
                    ext = os.path.splitext(original_name)[1].lower()
                    target_name = f"Episode_{ep_num}{ext}"
                    if ext == '.ts':
                        target_name = f"Episode_{ep_num}.mp4"
                        
                    target_path = os.path.join(anime_dir, target_name)
                    
                    try:
                        if ext == '.ts':
                            ffmpeg_bin = get_ffmpeg_path()
                            if ffmpeg_bin:
                                cmd = [ffmpeg_bin, "-y", "-i", fp, "-c", "copy", "-map_metadata", "0", target_path]
                                startupinfo = None
                                if os.name == 'nt':
                                    startupinfo = subprocess.STARTUPINFO()
                                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
                                proc.communicate(timeout=15)
                                if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
                                    results.append({
                                        'path': target_path,
                                        'name': target_name
                                    })
                                else:
                                    results.append({
                                        'path': original_selected_path,
                                        'name': original_name
                                    })
                            else:
                                results.append({
                                    'path': original_selected_path,
                                    'name': original_name
                                })
                        else:
                            import shutil
                            shutil.copy2(fp, target_path)
                            results.append({
                                'path': target_path,
                                'name': target_name
                            })
                    except Exception as e:
                        log_to_file(f"Folder copy/remux failed, fallback to original: {e}")
                        results.append({
                            'path': original_selected_path,
                            'name': original_name
                        })
                        
                import json
                js_code = f"completeMultipleEpisodesLinking({mal_id}, {json.dumps(results)});"
                self.window.evaluate_js(js_code)
            except Exception as e:
                log_to_file(f"Exception in select_link_folder worker: {e}")
                
        threading.Thread(target=worker, daemon=True).start()


    def select_link_file(self, mal_id, ep_num, anime_title):
        \"\"\" Opens file dialog on a background thread to prevent deadlocks, copies/remuxes file safely, and returns path \"\"\"
        log_to_file(f"=== select_link_file called for: {anime_title}, ep: {ep_num} ===")
        if not self.window:
            return
            
        def worker():
            try:
                file_types = (
                    'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                    'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                    'All Files (*.*)'
                )
                file_paths = self.window.create_file_dialog(
                    dialog_type=webview.OPEN_DIALOG,
                    allow_multiple=False,
                    file_types=file_types
                )
                if not file_paths:
                    return
                    
                fp = file_paths[0] if isinstance(file_paths, (list, tuple)) else file_paths
                original_selected_path = fp
                original_name = os.path.basename(fp)
                
                anime_title_str = str(anime_title or "Unknown")
                import re
                clean_title = re.sub(r'[\\\\/*?:"<>|]', "", anime_title_str).strip()
                anime_dir = os.path.join(DEFAULT_LIBRARY_DIR, clean_title)
                os.makedirs(anime_dir, exist_ok=True)
                
                ext = os.path.splitext(original_name)[1].lower()
                target_name = f"Episode_{ep_num}{ext}"
                if ext == '.ts':
                    target_name = f"Episode_{ep_num}.mp4"
                    
                target_path = os.path.join(anime_dir, target_name)
                
                is_remuxed = False
                try:
                    if ext == '.ts':
                        ffmpeg_bin = get_ffmpeg_path()
                        if ffmpeg_bin:
                            cmd = [ffmpeg_bin, "-y", "-i", fp, "-c", "copy", "-map_metadata", "0", target_path]
                            startupinfo = None
                            if os.name == 'nt':
                                startupinfo = subprocess.STARTUPINFO()
                                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
                            proc.communicate(timeout=15)
                            if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
                                fp = target_path
                                original_name = target_name
                                is_remuxed = True
                    else:
                        import shutil
                        shutil.copy2(fp, target_path)
                        fp = target_path
                        original_name = target_name
                except Exception as e:
                    log_to_file(f"Copying/remuxing failed, fallback to original path: {e}")
                    fp = original_selected_path
                    original_name = os.path.basename(fp)
                    
                import json
                processed_file = {"path": fp, "name": original_name, "is_remuxed": is_remuxed}
                js_code = f"completeEpisodeLinking({mal_id}, {ep_num}, {json.dumps(processed_file)});"
                self.window.evaluate_js(js_code)
            except Exception as e:
                log_to_file(f"Exception in select_link_file worker: {e}")
                
        threading.Thread(target=worker, daemon=True).start()

    def select_files(self):
        \"\"\" Opens a fully native OS file selection dialog via a non-blocking thread to prevent deadlocks \"\"\"
        log_to_file("=== select_files called ===")
        if not self.window:
            return []
            
        def worker():
            try:
                log_to_file("Worker thread started for select_files.")
                file_types = (
                    'Media Files (*.mp3;*.wav;*.ogg;*.mp4;*.webm;*.mkv;*.m4a;*.aac;*.flac;*.ts)',
                    'Audio Files (*.mp3;*.wav;*.ogg;*.m4a;*.aac;*.flac)',
                    'Video Files (*.mp4;*.webm;*.mkv;*.ts)',
                    'All Files (*.*)'
                )
                
                file_paths = self.window.create_file_dialog(
                    dialog_type=webview.OPEN_DIALOG,
                    allow_multiple=True,
                    file_types=file_types
                )
                log_to_file(f"create_file_dialog returned: {file_paths}")
                
                if not file_paths:
                    return
                    
                if isinstance(file_paths, (list, tuple)):
                    file_paths = list(file_paths)
                else:
                    file_paths = [file_paths]
                    
                results = []
                for fp in file_paths:
                    name = os.path.basename(fp)
                    results.append({
                        'path': fp,
                        'name': name
                    })
                log_to_file(f"Selected files results: {results}")
                
                import json
                js_code = f"addFilesToPlaylist({json.dumps(results)});"
                self.window.evaluate_js(js_code)
            except Exception as e:
                log_to_file(f"Exception in select_files worker: {e}")
                
        threading.Thread(target=worker, daemon=True).start()
        return []"""

if old_dialogs in code:
    code = code.replace(old_dialogs, new_dialogs)
    print("select_link_folder and select_link_file successfully restored to thread-safe non-blocking workers!")
else:
    # Safe regex fallback
    import re
    code = re.sub(r'def select_link_folder[\s\S]*?except Exception as e:[\s\S]*?log_to_file\(f"Exception in select_link_file: \{e\}"\)\s+return \[\]', new_dialogs, code)
    print("app.py dialogs updated with thread-safe regex!")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code)
