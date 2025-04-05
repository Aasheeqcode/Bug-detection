import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import re
import ast
import time
import shutil

class CodeAnalyzer:
    """Class to analyze code for bugs without requiring a backend server"""
    
    def __init__(self):
        self.bug_patterns = {
            'Python': [
                # Pattern: (regex, bug_type, description, fix_template)
                (r'for\s+(\w+)\s+in\s+(\w+)(?!\s*:)', 'SyntaxError', 'Missing colon after for loop', 'for {0} in {1}:'),
                (r'if\s+(.+?)(?!\s*:)$', 'SyntaxError', 'Missing colon after if condition', 'if {0}:'),
                (r'else(?!\s*:)', 'SyntaxError', 'Missing colon after else', 'else:'),
                (r'(\w+)\s*=\s*(\w+)\s*/\s*len\((\w+)\)', 'LogicError', 'Potential division by zero', '{0} = {1} / len({2}) if len({2}) > 0 else 0'),
                (r'(\w+)\s*=\s*(\d+)\s*/\s*(\w+)', 'LogicError', 'Potential division by zero', '{0} = {1} / {2} if {2} != 0 else 0'),
                (r'(\w+)\s*==\s*"([^"]*)"', 'StyleWarning', 'String comparison could use single quotes', "{0} == '{1}'"),
                (r'print\s*\(\s*([^,)]*)\s*\)', 'DeprecationWarning', 'Consider using f-strings for cleaner output', 'print(f"{{{0}}}")'),
                (r'while\s+(.+?)(?!\s*:)$', 'SyntaxError', 'Missing colon after while condition', 'while {0}:'),
                (r'def\s+(\w+)\s*\(([^)]*)\)(?!\s*:)', 'SyntaxError', 'Missing colon after function definition', 'def {0}({1}):'),
                (r'except(?!\s+\w+:|:)', 'SyntaxError', 'Invalid except clause', 'except Exception:'),
                (r'(\w+)\s*\+=\s*(\w+)\s*\n\s*return\s+\1', 'LogicWarning', 'Assignment before return without effect', 'return {0} + {1}'),
                # Add more bug patterns here
            ],
            'Java': [
                (r'if\s*\(.+\)\s*([^{])', 'SyntaxError', 'Missing braces in if statement', 'if (...) {'),
                (r'for\s*\(.+\)\s*([^{])', 'SyntaxError', 'Missing braces in for loop', 'for (...) {'),
                # Add more Java patterns
            ],
            'C++': [
                (r'for\s*\(.+\)\s*([^{])', 'SyntaxError', 'Missing braces in for loop', 'for (...) {'),
                # Add more C++ patterns
            ],
            'JavaScript': [
                (r'if\s*\(.+\)\s*([^{])', 'SyntaxError', 'Missing braces in if statement', 'if (...) {'),
                (r'var\s+(\w+)', 'StyleWarning', 'Using var instead of let/const', 'const {0}'),
                # Add more JavaScript patterns
            ]
        }
        
        # AST-based bug detection for Python
        self.ast_checkers = {
            'Python': self.python_ast_check
        }
    
    def python_ast_check(self, code):
        """Use AST to find more complex bugs in Python code"""
        bugs = []
        try:
            tree = ast.parse(code)
            
            # Check for unused variables
            defined_vars = set()
            used_vars = set()
            
            # Simple AST visitor
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            defined_vars.add(target.id)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    used_vars.add(node.id)
            
            # Find unused variables
            unused = defined_vars - used_vars
            for var in unused:
                # Find the line number
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == var:
                                line_num = node.lineno
                                bugs.append({
                                    'type': 'StyleWarning',
                                    'line': line_num,
                                    'description': f"Unused variable '{var}'",
                                    'fix': f"# Remove or use the variable '{var}'"
                                })
            
            # Check for bare excepts
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    bugs.append({
                        'type': 'LogicWarning',
                        'line': node.lineno,
                        'description': "Bare except clause",
                        'fix': "except Exception as e:"
                    })
            
        except SyntaxError as e:
            # Handle syntax errors from ast
            bugs.append({
                'type': 'SyntaxError',
                'line': e.lineno or 0,
                'description': str(e),
                'fix': "# Fix the syntax error: " + str(e)
            })
        
        return bugs
    
    def detect_bugs(self, code, language):
        """Main method to detect bugs in code"""
        results = []
        
        # Process the code line by line for pattern-based bugs
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern, bug_type, description, fix_template in self.bug_patterns.get(language, []):
                match = re.search(pattern, line)
                if match:
                    # Get the original line for reference
                    original_line = line
                    
                    # Get matched groups for fix formatting
                    groups = match.groups()
                    fix = fix_template.format(*groups) if groups else fix_template
                    
                    results.append({
                        'type': bug_type,
                        'line': i,
                        'description': description,
                        'original': original_line,
                        'fix': fix
                    })
        
        # Use AST-based check if available for the language
        if language in self.ast_checkers:
            ast_bugs = self.ast_checkers[language](code)
            results.extend(ast_bugs)
        
        return {
            'bug_count': len(results),
            'bugs': results
        }
    
    def rectify_bug(self, code, bug):
        """Rectify a single bug in the code"""
        lines = code.split('\n')
        line_idx = bug['line'] - 1
        
        if 0 <= line_idx < len(lines):
            # Keep track of the original line
            original_line = lines[line_idx]
            # Replace with the fix
            lines[line_idx] = bug['fix']
            return '\n'.join(lines), original_line
        
        return code, None
    
    def apply_fixes(self, code, bugs):
        """Apply all suggested fixes to the code"""
        lines = code.split('\n')
        
        # Sort bugs by line number in descending order to avoid index shifting
        bugs_sorted = sorted(bugs, key=lambda x: x['line'], reverse=True)
        
        for bug in bugs_sorted:
            line_idx = bug['line'] - 1
            if 0 <= line_idx < len(lines):
                lines[line_idx] = bug['fix']
        
        return '\n'.join(lines)


class BugDetectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Code Bug Detector")
        self.root.geometry("900x750")
        self.root.configure(bg="#f0f0f0")
        
        # Initialize the code analyzer
        self.analyzer = CodeAnalyzer()
        
        # Variables
        self.language_var = tk.StringVar(value="Python")
        self.languages = ['Python', 'Java', 'C++', 'JavaScript']
        self.filename = None
        self.is_processing = False
        self.code_content = None
        self.detected_bugs = None
        self.current_bug_index = None
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main frame
        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="Code Bug Detection System", 
                             font=("Helvetica", 18, "bold"), bg="#f0f0f0")
        title_label.pack(pady=(0, 20))
        
        # File Selection Section
        file_frame = tk.LabelFrame(main_frame, text="File Selection", 
                                  padx=10, pady=10, bg="#f0f0f0")
        file_frame.pack(fill="x", pady=10)
        
        # File selection button and display
        file_button = tk.Button(file_frame, text="Select Code File",
                               command=self.select_file, 
                               bg="#4CAF50", fg="white",
                               padx=10, pady=5)
        file_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.file_label = tk.Label(file_frame, text="No file selected", 
                                  width=50, anchor="w", bg="#f0f0f0")
        self.file_label.grid(row=0, column=1, padx=5, pady=5)
        
        # Language Selection Section
        lang_frame = tk.LabelFrame(main_frame, text="Language Selection", 
                                  padx=10, pady=10, bg="#f0f0f0")
        lang_frame.pack(fill="x", pady=10)
        
        tk.Label(lang_frame, text="Programming Language:", 
                bg="#f0f0f0").grid(row=0, column=0, padx=5, pady=5)
        
        language_dropdown = ttk.Combobox(lang_frame, 
                                        textvariable=self.language_var,
                                        values=self.languages,
                                        state="readonly")
        language_dropdown.grid(row=0, column=1, padx=5, pady=5)
        
        # Action Buttons
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(fill="x", pady=10)
        
        self.detect_button = tk.Button(button_frame, text="Detect Bugs",
                                     command=self.start_detection,
                                     bg="#2196F3", fg="white",
                                     padx=20, pady=10,
                                     font=("Helvetica", 12),
                                     state=tk.DISABLED)
        self.detect_button.pack(side=tk.LEFT, padx=10)
        
        self.fix_all_button = tk.Button(button_frame, text="Fix All Bugs",
                                     command=self.apply_all_fixes,
                                     bg="#FF9800", fg="white",
                                     padx=20, pady=10,
                                     font=("Helvetica", 12),
                                     state=tk.DISABLED)
        self.fix_all_button.pack(side=tk.RIGHT, padx=10)
        
        # Progress bar
        self.progress_frame = tk.Frame(main_frame, bg="#f0f0f0")
        self.progress_frame.pack(fill="x", pady=10)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, 
                                           mode="indeterminate", length=700)
        self.status_label = tk.Label(self.progress_frame, text="", 
                                    bg="#f0f0f0")
        
        # Results Display Section
        results_frame = tk.LabelFrame(main_frame, text="Detected Bugs", 
                                     padx=10, pady=10, bg="#f0f0f0")
        results_frame.pack(fill="both", expand=True, pady=10)
        
        # Create results display with scrollbar
        text_frame = tk.Frame(results_frame)
        text_frame.pack(fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.results_text = tk.Text(text_frame, height=15, width=80, 
                                   yscrollcommand=scrollbar.set,
                                   font=("Consolas", 10))
        self.results_text.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.config(command=self.results_text.yview)
        
        # Individual Bug Fixing Section
        self.bug_fix_frame = tk.LabelFrame(main_frame, text="Quick Bug Fix", 
                                        padx=10, pady=10, bg="#f0f0f0")
        self.bug_fix_frame.pack(fill="x", pady=10)
        
        # Bug navigation
        nav_frame = tk.Frame(self.bug_fix_frame, bg="#f0f0f0")
        nav_frame.pack(fill="x", pady=5)
        
        self.prev_bug_button = tk.Button(nav_frame, text="◀ Previous Bug", 
                                      command=self.previous_bug,
                                      state=tk.DISABLED)
        self.prev_bug_button.pack(side=tk.LEFT, padx=5)
        
        self.bug_counter_label = tk.Label(nav_frame, text="Bug 0 of 0", 
                                       bg="#f0f0f0", width=15)
        self.bug_counter_label.pack(side=tk.LEFT, padx=20)
        
        self.next_bug_button = tk.Button(nav_frame, text="Next Bug ▶", 
                                      command=self.next_bug,
                                      state=tk.DISABLED)
        self.next_bug_button.pack(side=tk.LEFT, padx=5)
        
        # Bug details
        detail_frame = tk.Frame(self.bug_fix_frame, bg="#f0f0f0")
        detail_frame.pack(fill="x", pady=5)
        
        tk.Label(detail_frame, text="Line:", bg="#f0f0f0").grid(row=0, column=0, sticky="w", padx=5)
        self.bug_line_label = tk.Label(detail_frame, text="N/A", bg="#f0f0f0", width=5)
        self.bug_line_label.grid(row=0, column=1, sticky="w", padx=5)
        
        tk.Label(detail_frame, text="Type:", bg="#f0f0f0").grid(row=0, column=2, sticky="w", padx=5)
        self.bug_type_label = tk.Label(detail_frame, text="N/A", bg="#f0f0f0", width=15)
        self.bug_type_label.grid(row=0, column=3, sticky="w", padx=5)
        
        # Original code and fix
        code_frame = tk.Frame(self.bug_fix_frame, bg="#f0f0f0")
        code_frame.pack(fill="x", pady=5)
        
        tk.Label(code_frame, text="Original:", bg="#f0f0f0").grid(row=0, column=0, sticky="nw", padx=5)
        self.original_code_text = tk.Text(code_frame, height=2, width=80, font=("Consolas", 10))
        self.original_code_text.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.original_code_text.config(state=tk.DISABLED)
        
        tk.Label(code_frame, text="Fix:", bg="#f0f0f0").grid(row=1, column=0, sticky="nw", padx=5)
        self.fixed_code_text = tk.Text(code_frame, height=2, width=80, font=("Consolas", 10))
        self.fixed_code_text.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.fixed_code_text.config(state=tk.DISABLED)
        
        # Rectify button
        self.rectify_button = tk.Button(self.bug_fix_frame, text="Rectify Now",
                                     command=self.rectify_current_bug,
                                     bg="#4CAF50", fg="white",
                                     padx=20, pady=8,
                                     font=("Helvetica", 10, "bold"),
                                     state=tk.DISABLED)
        self.rectify_button.pack(pady=10)
        
        # Status bar
        self.status_bar = tk.Label(self.root, text="Ready", 
                                 bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def select_file(self):
        filetypes = [("All Code Files", "*.py;*.java;*.cpp;*.js")]
        if self.language_var.get() == "Python":
            filetypes.append(("Python Files", "*.py"))
        elif self.language_var.get() == "Java":
            filetypes.append(("Java Files", "*.java"))
        elif self.language_var.get() == "C++":
            filetypes.append(("C++ Files", "*.cpp"))
        elif self.language_var.get() == "JavaScript":
            filetypes.append(("JavaScript Files", "*.js"))
        
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self.filename = filename
            self.file_label.config(text=os.path.basename(filename))
            self.status_bar.config(text=f"Selected file: {os.path.basename(filename)}")
            self.detect_button.config(state=tk.NORMAL)
            
            # Reset results
            self.results_text.delete(1.0, tk.END)
            self.fix_all_button.config(state=tk.DISABLED)
            self.reset_bug_navigation()
    
    def start_detection(self):
        if not self.filename:
            messagebox.showerror("Error", "Please select a file first")
            return
        
        # Show progress bar and update status
        self.progress_bar.pack(pady=5)
        self.status_label.config(text="Detecting bugs...")
        self.status_label.pack(pady=5)
        self.progress_bar.start(10)
        
        # Disable detect button while processing
        self.detect_button.config(state=tk.DISABLED)
        self.status_bar.config(text="Processing...")
        
        # Reset bug navigation
        self.reset_bug_navigation()
        
        # Start detection in a separate thread
        self.is_processing = True
        thread = threading.Thread(target=self.detect_bugs)
        thread.daemon = True
        thread.start()
    
    def detect_bugs(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as file:
                self.code_content = file.read()
            
            # Update UI to show we're analyzing
            self.root.after(0, lambda: self.status_label.config(
                text="Analyzing code..."))
            
            # Actual bug detection
            language = self.language_var.get()
            results = self.analyzer.detect_bugs(self.code_content, language)
            
            # Add small delay to show progress (can be removed in production)
            time.sleep(0.5)
            
            # Save detected bugs
            self.detected_bugs = results['bugs']
            
            # Update UI with results
            self.root.after(0, lambda: self.display_results(results))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error analyzing code: {str(e)}"))
        finally:
            self.is_processing = False
            self.root.after(0, self.reset_ui)
    
    def display_results(self, results):
        self.results_text.delete(1.0, tk.END)
        
        # Change text color based on bug count
        if results['bug_count'] == 0:
            self.results_text.configure(foreground="green")
            self.results_text.insert(tk.END, "✓ No bugs detected! Your code looks good.\n")
            self.fix_all_button.config(state=tk.DISABLED)
        else:
            self.results_text.configure(foreground="black")
            self.results_text.insert(tk.END, f"⚠ Bugs Detected: {results['bug_count']}\n\n", "bug_count")
            self.results_text.tag_configure("bug_count", foreground="red", font=("Helvetica", 12, "bold"))
            
            for i, bug in enumerate(results['bugs'], 1):
                self.results_text.insert(tk.END, f"Bug #{i}: ", "bug_num")
                self.results_text.tag_configure("bug_num", foreground="red", font=("Helvetica", 10, "bold"))
                
                self.results_text.insert(tk.END, f"{bug['type']}\n", "bug_type")
                self.results_text.tag_configure("bug_type", foreground="darkred")
                
                self.results_text.insert(tk.END, f"Location: Line {bug['line']}\n")
                self.results_text.insert(tk.END, f"Description: {bug['description']}\n\n")
                
                self.results_text.insert(tk.END, "Suggested Fix:\n", "fix_header")
                self.results_text.tag_configure("fix_header", foreground="blue", font=("Helvetica", 10, "bold"))
                
                self.results_text.insert(tk.END, f"{bug['fix']}\n\n", "fix_code")
                self.results_text.tag_configure("fix_code", font=("Consolas", 10), background="#f0f8ff")
            
            # Enable fix button
            self.fix_all_button.config(state=tk.NORMAL)
            
            # Initialize bug navigation
            if self.detected_bugs:
                self.current_bug_index = 0
                self.update_bug_navigation()
    
    def reset_ui(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.status_label.pack_forget()
        self.detect_button.config(state=tk.NORMAL)
        self.status_bar.config(text="Ready")
    
    def apply_all_fixes(self):
        if not self.filename or not self.code_content or not self.detected_bugs:
            return
        
        try:
            # Create a backup of the original file
            backup_file = self.filename + '.bak'
            if not os.path.exists(backup_file):
                shutil.copy2(self.filename, backup_file)
            
            # Apply the fixes
            fixed_code = self.analyzer.apply_fixes(self.code_content, self.detected_bugs)
            
            # Write the fixed code
            with open(self.filename, 'w', encoding='utf-8') as f:
                f.write(fixed_code)
            
            messagebox.showinfo("Success", 
                             f"All fixes applied successfully!\nOriginal file backed up as {os.path.basename(backup_file)}")
            self.status_bar.config(text="All fixes applied successfully")
            
            # Update our stored code content
            self.code_content = fixed_code
            
            # Reset bug navigation and re-run detection
            self.reset_bug_navigation()
            self.fix_all_button.config(state=tk.DISABLED)
            
            # Re-run detection to see if bugs remain
            self.start_detection()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply fixes: {str(e)}")
    
    def reset_bug_navigation(self):
        """Reset bug navigation controls"""
        self.current_bug_index = None
        self.prev_bug_button.config(state=tk.DISABLED)
        self.next_bug_button.config(state=tk.DISABLED)
        self.rectify_button.config(state=tk.DISABLED)
        self.bug_counter_label.config(text="Bug 0 of 0")
        self.bug_line_label.config(text="N/A")
        self.bug_type_label.config(text="N/A")
        
        # Clear code display
        self.original_code_text.config(state=tk.NORMAL)
        self.original_code_text.delete(1.0, tk.END)
        self.original_code_text.config(state=tk.DISABLED)
        
        self.fixed_code_text.config(state=tk.NORMAL)
        self.fixed_code_text.delete(1.0, tk.END)
        self.fixed_code_text.config(state=tk.DISABLED)
    
    def update_bug_navigation(self):
        """Update bug navigation controls and display"""
        if not self.detected_bugs or self.current_bug_index is None:
            return
        
        total_bugs = len(self.detected_bugs)
        if total_bugs == 0:
            self.reset_bug_navigation()
            return
        
        # Update counter
        self.bug_counter_label.config(text=f"Bug {self.current_bug_index + 1} of {total_bugs}")
        
        # Update navigation buttons
        self.prev_bug_button.config(state=tk.NORMAL if self.current_bug_index > 0 else tk.DISABLED)
        self.next_bug_button.config(state=tk.NORMAL if self.current_bug_index < total_bugs - 1 else tk.DISABLED)
        
        # Get current bug
        bug = self.detected_bugs[self.current_bug_index]
        
        # Update bug details
        self.bug_line_label.config(text=str(bug['line']))
        self.bug_type_label.config(text=bug['type'])
        
        # Update code display
        self.original_code_text.config(state=tk.NORMAL)
        self.original_code_text.delete(1.0, tk.END)
        self.original_code_text.insert(tk.END, bug.get('original', 'Original code not available'))
        self.original_code_text.config(state=tk.DISABLED)
        
        self.fixed_code_text.config(state=tk.NORMAL)
        self.fixed_code_text.delete(1.0, tk.END)
        self.fixed_code_text.insert(tk.END, bug['fix'])
        self.fixed_code_text.config(state=tk.DISABLED)
        
        # Enable rectify button
        self.rectify_button.config(state=tk.NORMAL)
    
    def previous_bug(self):
        """Navigate to previous bug"""
        if self.current_bug_index is not None and self.current_bug_index > 0:
            self.current_bug_index -= 1
            self.update_bug_navigation()
    
    def next_bug(self):
        """Navigate to next bug"""
        if (self.current_bug_index is not None and 
            self.detected_bugs and 
            self.current_bug_index < len(self.detected_bugs) - 1):
            self.current_bug_index += 1
            self.update_bug_navigation()
    
    def rectify_current_bug(self):
        """Rectify the currently selected bug"""
        if (self.current_bug_index is None or 
            not self.detected_bugs or 
            self.current_bug_index >= len(self.detected_bugs)):
            return
        
        try:
            # Get the current bug
            bug = self.detected_bugs[self.current_bug_index]
            
            # Create a backup if none exists
            backup_file = self.filename + '.bak'
            if not os.path.exists(backup_file):
                shutil.copy2(self.filename, backup_file)
            
            # Apply this specific bug fix
            fixed_code, original_line = self.analyzer.rectify_bug(self.code_content, bug)
            
            # Write the fixed code
            with open(self.filename, 'w', encoding='utf-8') as f:
                f.write(fixed_code)
            
            # Update our stored code content
            self.code_content = fixed_code
            
            # Show success message
            self.status_bar.config(text=f"Fixed bug on line {bug['line']}")
            
            # Remove this bug from the list
            self.detected_bugs.pop(self.current_bug_index)
            
            # Update navigation
            if not self.detected_bugs:
                # No more bugs
                self.reset_bug_navigation()
                messagebox.showinfo("Success", "All bugs have been fixed!")
                self.fix_all_button.config(state=tk.DISABLED)
                
                # Re-run detection to confirm
                self.start_detection()
            else:
                # Adjust current index if needed
                if self.current_bug_index >= len(self.detected_bugs):
                    self.current_bug_index = len(self.detected_bugs) - 1
                
                # Update display
                self.update_bug_navigation()
                
                # Update the results display
                self.display_results({
                    'bug_count': len(self.detected_bugs),
                    'bugs': self.detected_bugs
                })
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rectify bug: {str(e)}")

def main():
    root = tk.Tk()
    app = BugDetectionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()