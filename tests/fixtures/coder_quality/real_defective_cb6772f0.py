import tkinter as tk
from tkinter import messagebox

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("ماشین‌حساب")
        self.root.geometry("300x400")
        self.root.resizable(False, False)
        
        self.display_var = tk.StringVar()
        self.display_var.set("0")
        
        self.current_input = ""
        self.operator = ""
        self.previous_input = ""
        self.waiting_for_operator = False
        self.decimal_point_used = False
        
        self.create_widgets()
        
    def create_widgets(self):
        display_frame = tk.Frame(self.root)
        display_frame.pack(pady=10)
        
        display = tk.Entry(
            display_frame,
            textvariable=self.display_var,
            font=("Arial", 20),
            justify="right",
            state="readonly",
            bd=5,
            relief="sunken"
        )
        display.pack(ipadx=10, ipady=10)
        
        button_frame = tk.Frame(self.root)
        button_frame.pack()
        
        buttons = [
            'C', '←', '÷', '×',
            '7', '8', '9', '-',
            '4', '5', '6', '+',
            '1', '2', '3', '=',
            '0', '.', 'Escape'
        ]
        
        row = 0
        col = 0
        
        for button in buttons:
            if button == 'Escape':
                btn = tk.Button(button_frame, text=button, width=5, height=2, command=self.clear_all)
            elif button == '=':
                btn = tk.Button(button_frame, text=button, width=5, height=2, command=self.calculate)
            elif button == '←':
                btn = tk.Button(button_frame, text=button, width=5, height=2, command=self.backspace)
            elif button in ['+', '-', '×', '÷']:
                btn = tk.Button(button_frame, text=button, width=5, height=2, command=lambda b=button: self.set_operator(b))
            else:
                btn = tk.Button(button_frame, text=button, width=5, height=2, command=lambda b=button: self.input_number(b))
            
            btn.grid(row=row, column=col, padx=2, pady=2)
            
            col += 1
            if col > 3:
                col = 0
                row += 1
                
        self.root.bind('<Key>', self.key_press)
        
    def input_number(self, value):
        if self.waiting_for_operator and value not in ['.', '+', '-', '×', '÷']:
            self.current_input = ""
            self.waiting_for_operator = False
            
        if value == '.':
            if self.decimal_point_used:
                return
            self.decimal_point_used = True
            
        if self.current_input == "0" and value != ".":
            self.current_input = value
        else:
            self.current_input += value
            
        self.display_var.set(self.current_input)
        
    def set_operator(self, op):
        if not self.current_input:
            return
            
        if self.previous_input and self.operator:
            self.calculate()
            
        self.previous_input = self.current_input
        self.operator = op
        self.current_input = ""
        self.decimal_point_used = False
        self.waiting_for_operator = True
        
    def calculate(self):
        if not self.previous_input or not self.current_input or not self.operator:
            return
            
        try:
            prev = float(self.previous_input)
            curr = float(self.current_input)
            
            result = 0
            
            if self.operator == '+':
                result = prev + curr
            elif self.operator == '-':
                result = prev - curr
            elif self.operator == '×':
                result = prev * curr
            elif self.operator == '÷':
                if curr == 0:
                    messagebox.showerror("خطا", "تقسیم بر صفر ممکن نیست!")
                    self.clear_all()
                    return
                result = prev / curr
                
            # Convert to int if result is whole number
            if result.is_integer():
                result = int(result)
            else:
                result = round(result, 10)  # Prevent floating point errors
                
            self.display_var.set(str(result))
            self.current_input = str(result)
            self.previous_input = ""
            self.operator = ""
            self.decimal_point_used = False
            self.waiting_for_operator = False
            
        except Exception:
            messagebox.showerror("خطا", "محاسبه ناموفق!")
            self.clear_all()
            
    def backspace(self):
        if not self.current_input:
            return
            
        if len(self.current_input) == 1:
            self.current_input = "0"
        else:
            self.current_input = self.current_input[:-1]
            
        # Reset decimal point flag if last character was '.'
        if self.current_input.endswith('.'):
            self.decimal_point_used = False
            
        self.display_var.set(self.current_input)
        
    def clear_all(self):
        self.current_input = ""
        self.operator = ""
        self.previous_input = ""
        self.waiting_for_operator = False
        self.decimal_point_used = False
        self.display_var.set("0")
        
    def key_press(self, event):
        key = event.keysym
        
        if key == 'Escape':
            self.clear_all()
        elif key == 'BackSpace':
            self.backspace()
        elif key == 'Return' or key == 'equal':
            self.calculate()
        elif key in ['plus', 'minus', 'asterisk', 'slash']:
            op_map = {'plus': '+', 'minus': '-', 'asterisk': '×', 'slash': '÷'}
            self.set_operator(op_map[key])
        elif key in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
            self.input_number(key)
        elif key == 'period':
            self.input_number('.')
        elif key == 'c' or key == 'C':
            self.clear_all()

if __name__ == "__main__":
    root = tk.Tk()
    calc = Calculator(root)
    root.mainloop()
