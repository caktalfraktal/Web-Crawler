import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import threading
from collections import deque
import time

class WebCrawlerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Web Crawler")
        self.root.geometry("800x600")
        
        # Variables
        self.base_url = ""
        self.discovered_urls = set()
        self.crawling = False
        self.download_cancelled = False # Flag for cancelling downloads
        self.sort_reverse = {'Type': False, 'Size': False}  # Track sort direction for each column
        self.file_data = {}  # Store file data for sorting
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)  # Results frame gets the stretch
        
        # URL input
        ttk.Label(main_frame, text="Website URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=5)
        
        # Bind the Enter key to the start_crawling method
        self.url_entry.bind("<Return>", lambda event: self.start_crawling())
        
        # Create context menu for URL entry
        self.url_context_menu = tk.Menu(self.root, tearoff=0)
        self.url_context_menu.add_command(label="Paste", command=self.paste_url)
        self.url_context_menu.add_command(label="Clear", command=self.clear_url)
        
        # Bind right-click to URL entry
        self.url_entry.bind('<Button-3>', self.show_url_context_menu)
        self.url_entry.bind('<Button-2>', self.show_url_context_menu)  # Mac
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        
        self.crawl_button = ttk.Button(button_frame, text="Start Crawling", command=self.start_crawling)
        self.crawl_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_crawling, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = ttk.Button(button_frame, text="Clear Results", command=self.clear_results)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Discovered Files and Pages", padding="5")
        results_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Treeview for results
        self.tree = ttk.Treeview(results_frame, columns=('Type', 'Size'), show='tree headings', selectmode='extended')
        self.tree.heading('#0', text='URL/File')
        self.tree.heading('Type', text='Type', command=lambda: self.sort_by_column('Type'))
        self.tree.heading('Size', text='Size', command=lambda: self.sort_by_column('Size'))
        
        self.tree.column('#0', width=600, stretch=tk.YES)
        self.tree.column('Type', width=60, stretch=tk.NO, anchor=tk.W) #-------------------------
        self.tree.column('Size', width=70, stretch=tk.NO, anchor=tk.CENTER)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind double-click to download
        self.tree.bind('<Double-1>', self.on_item_double_click)
        
        # Create context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Download", command=self.download_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copy URL", command=self.copy_url)
        
        # Bind right-click to context menu
        self.tree.bind('<Button-3>', self.show_context_menu)
        self.tree.bind('<Button-2>', self.show_context_menu)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
    def start_crawling(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
            
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
            
        self.base_url = url
        self.crawling = True
        self.crawl_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress.start()
        self.status_var.set("Crawling...")
        
        threading.Thread(target=self.crawl_website, daemon=True).start()
        
    def stop_crawling(self):
        self.crawling = False
        self.crawl_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress.stop()
        self.status_var.set("Stopped")
        
    def clear_results(self):
        self.tree.delete(*self.tree.get_children())
        self.discovered_urls.clear()
        self.file_data.clear()
        self.status_var.set("Results cleared")
        
    def crawl_website(self):
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            to_visit = deque([self.base_url])
            visited = set()
            
            while to_visit and self.crawling:
                current_url = to_visit.popleft()
                
                if current_url in visited:
                    continue
                    
                visited.add(current_url)
                
                try:
                    response = session.get(current_url, timeout=10)
                    content_type = response.headers.get('content-type', '').lower()
                    
                    self.root.after(0, self.add_to_tree, current_url, content_type, len(response.content))
                    
                    if 'text/html' in content_type:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        for link in soup.find_all(['a', 'link', 'script', 'img']):
                            href = link.get('href') or link.get('src')
                            if href:
                                full_url = urljoin(current_url, href)
                                if self.same_domain(full_url, self.base_url) and full_url not in visited:
                                    to_visit.append(full_url)
                                    
                except requests.RequestException as e:
                    self.root.after(0, self.add_to_tree, current_url, f"Error: {str(e)}", 0)
                time.sleep(0.1)
                
            self.root.after(0, self.crawling_finished)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Crawling failed: {str(e)}"))
            self.root.after(0, self.crawling_finished)
            
    def same_domain(self, url1, url2):
        try:
            return urlparse(url1).netloc == urlparse(url2).netloc
        except:
            return False
            
    def add_to_tree(self, url, content_type, size):
        file_type = "Other"
        if 'text/html' in content_type: file_type = "HTML"
        elif 'image/' in content_type: file_type = "Image"
        elif 'text/css' in content_type: file_type = "CSS"
        elif 'javascript' in content_type: file_type = "JavaScript"
        elif 'application/pdf' in content_type: file_type = "PDF"
        elif 'Error:' in content_type: file_type = "Error"
        
        size_str = self.format_size(size) if size > 0 else "Unknown"
        self.file_data[url] = {'type': file_type, 'size': size, 'size_str': size_str, 'content_type': content_type}
        self.tree.insert('', 'end', text=url, values=(file_type, size_str))
        self.discovered_urls.add(url)
        self.status_var.set(f"Found {len(self.discovered_urls)} files/pages")
        
    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
        
    def crawling_finished(self):
        self.crawling = False
        self.crawl_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress.stop()
        self.status_var.set(f"Crawling complete. Found {len(self.discovered_urls)} files/pages")
        
    def on_item_double_click(self, event):
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            url = self.tree.item(item)['text']
            if self.tree.item(item)['values'][0] == "Error":
                messagebox.showwarning("Cannot Download", "This URL had an error and cannot be downloaded.")
                return
            self.download_file_with_progress(url)
    
    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)
        
        selection = self.tree.selection()
        if selection:
            if len(selection) == 1:
                self.context_menu.entryconfig(0, label="Download")
                self.context_menu.entryconfig(2, label="Copy URL")
            else:
                self.context_menu.entryconfig(0, label=f"Download {len(selection)} files")
                self.context_menu.entryconfig(2, label="Copy URLs")
            self.context_menu.post(event.x_root, event.y_root)
    
    def copy_url(self):
        selection = self.tree.selection()
        if selection:
            urls = [self.tree.item(item)['text'] for item in selection]
            self.root.clipboard_clear()
            self.root.clipboard_append('\n'.join(urls))
            self.status_var.set(f"{len(urls)} URL(s) copied to clipboard")
    
    def show_url_context_menu(self, event):
        self.url_context_menu.post(event.x_root, event.y_root)
    
    def paste_url(self):
        try:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, self.root.clipboard_get())
            self.status_var.set("URL pasted from clipboard")
        except tk.TclError:
            self.status_var.set("Nothing to paste")
    
    def clear_url(self):
        self.url_entry.delete(0, tk.END)
        self.status_var.set("URL field cleared")
    
    def sort_by_column(self, column):
        self.sort_reverse[column] = not self.sort_reverse[column]
        items = [(self.tree.item(item)['text'], self.tree.item(item)['values']) for item in self.tree.get_children()]
        
        sort_key = lambda x: (x[1][0] if column == 'Type' else self.file_data.get(x[0], {}).get('size', 0))
        items.sort(key=sort_key, reverse=self.sort_reverse[column])
        
        self.tree.delete(*self.tree.get_children())
        for url, values in items:
            self.tree.insert('', 'end', text=url, values=values)

    def download_selected(self):
        selection = self.tree.selection()
        if not selection: return

        urls_to_download = [self.tree.item(item)['text'] for item in selection if self.tree.item(item)['values'][0] != "Error"]
        if not urls_to_download:
            messagebox.showwarning("No Valid Files", "The selected item(s) resulted in errors and cannot be downloaded.")
            return

        if len(urls_to_download) == 1:
            self.download_file_with_progress(urls_to_download[0])
        else:
            download_dir = filedialog.askdirectory(title=f"Select Directory to Save {len(urls_to_download)} Files", initialdir=os.path.expanduser("~/Downloads"))
            if download_dir:
                self.download_batch(urls_to_download, download_dir)

    def download_file_with_progress(self, url, save_path=None):
        if save_path is None:
            filename = os.path.basename(urlparse(url).path) or "index.html"
            save_path = filedialog.asksaveasfilename(initialdir=os.path.expanduser("~/Downloads"), initialfile=filename, title="Save file as...")
            if not save_path:
                self.status_var.set("Download cancelled by user.")
                return
        self.download_batch([(url, save_path)], os.path.dirname(save_path))
    
    def download_batch(self, url_list, directory):
        progress_window = tk.Toplevel(self.root)
        progress_window.withdraw()  # Hide window until it's positioned
        progress_window.title("Download") # Set consistent title
        progress_window.geometry("500x220")
        progress_window.resizable(False, False)
        progress_window.transient(self.root)
        progress_window.grab_set()

        main_frame = ttk.Frame(progress_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Overall Progress:").pack(anchor=tk.W)
        overall_progress_var = tk.DoubleVar()
        overall_progress_bar = ttk.Progressbar(main_frame, variable=overall_progress_var, maximum=len(url_list), length=400)
        overall_progress_bar.pack(fill=tk.X, pady=(0, 10))

        current_file_label = ttk.Label(main_frame, text="Current File:", wraplength=450)
        current_file_label.pack(anchor=tk.W, pady=(10, 0))
        
        current_progress_var = tk.DoubleVar()
        current_progress_bar = ttk.Progressbar(main_frame, variable=current_progress_var, maximum=100, length=400)
        current_progress_bar.pack(fill=tk.X, pady=(0, 5))

        current_status_label = ttk.Label(main_frame, text="Waiting to start...")
        current_status_label.pack(anchor=tk.W)

        self.download_cancelled = False
        def cancel_action():
            if messagebox.askyesno("Confirm Cancel", "Are you sure you want to cancel the entire download?"):
                self.download_cancelled = True
                cancel_button.config(text="Cancelling...", state=tk.DISABLED)

        cancel_button = ttk.Button(main_frame, text="Cancel", command=cancel_action)
        cancel_button.pack(pady=(15, 0))
        
        progress_window.update_idletasks()
        main_win_x = self.root.winfo_x()
        main_win_y = self.root.winfo_y()
        main_win_width = self.root.winfo_width()
        main_win_height = self.root.winfo_height()
        prog_win_width = progress_window.winfo_width()
        prog_win_height = progress_window.winfo_height()
        center_x = main_win_x + (main_win_width // 2) - (prog_win_width // 2)
        center_y = main_win_y + (main_win_height // 2) - (prog_win_height // 2)
        progress_window.geometry(f"+{center_x}+{center_y}")
        
        progress_window.deiconify() # Reveal the window in its final position

        threading.Thread(
            target=self._execute_batch_download,
            args=(url_list, directory, progress_window, overall_progress_var, current_file_label, current_progress_var, current_status_label, cancel_button),
            daemon=True
        ).start()

    def _execute_batch_download(self, url_list, directory, progress_window, overall_var, file_label, current_var, status_label, cancel_btn):
        successful_downloads, failed_downloads = [], []
        total_files = len(url_list)
        i = 0

        for i, url_info in enumerate(url_list):
            if self.download_cancelled: break
            
            save_path = ""
            if isinstance(url_info, tuple):
                url, save_path = url_info
            else:
                url = url_info
                filename = os.path.basename(urlparse(url).path) or "index.html"
                save_path = os.path.join(directory, filename)
                if os.path.exists(save_path):
                    name, ext = os.path.splitext(filename)
                    save_path = os.path.join(directory, f"{name}_{int(time.time())}{ext}")

            self.root.after(0, file_label.config, {'text': f"Current File: {os.path.basename(save_path)}"})
            self.root.after(0, current_var.set, 0)
            self.root.after(0, overall_var.set, i)
            
            try:
                response = requests.get(url, stream=True, timeout=20)
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.download_cancelled:
                            raise OperationCanceledError("Download was cancelled by the user.")
                        
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        status_text = f"Downloaded {self.format_size(downloaded_size)}"
                        if total_size > 0:
                            percentage = (downloaded_size / total_size) * 100
                            self.root.after(0, current_var.set, percentage)
                            status_text += f" of {self.format_size(total_size)} ({percentage:.1f}%)"
                        self.root.after(0, status_label.config, {'text': status_text})
                
                successful_downloads.append(os.path.basename(save_path))
            
            except Exception as e:
                failed_downloads.append(os.path.basename(url))
                if os.path.exists(save_path):
                    try: os.remove(save_path)
                    except OSError: pass
                if self.download_cancelled: break

        def on_complete():
            is_single_file_success = total_files == 1 and not failed_downloads
            
            if self.download_cancelled:
                title_message = "Download Cancelled"
                final_message = f"{len(successful_downloads)} file(s) downloaded before cancellation."
            elif is_single_file_success:
                title_message = "Download Complete!"
                final_message = f"File saved to:\n{url_list[0][1]}"
            else:
                title_message = "Download Complete!"
                final_message = f"Successful: {len(successful_downloads)}, Failed: {len(failed_downloads)}\nSaved in directory: {directory}"
                if failed_downloads:
                    final_message += "\n(See console for a list of failed files.)"
                    print("Failed files:", failed_downloads)

            file_label.config(text=title_message)
            status_label.config(text=final_message, wraplength=450)
            overall_var.set(i + 1 if not self.download_cancelled and successful_downloads else i)
            current_var.set(100)
            
            cancel_btn.config(text="Close", state=tk.NORMAL, command=progress_window.destroy)
            
            self.status_var.set(f"Download complete. Success: {len(successful_downloads)}, Failed: {len(failed_downloads)}")
            progress_window.grab_release()

        self.root.after(0, on_complete)

class OperationCanceledError(Exception): pass

def main():
    root = tk.Tk()
    app = WebCrawlerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()